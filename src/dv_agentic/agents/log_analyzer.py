# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Simulation log analysis agent.

Classifies simulation failures by matching known error patterns with
regular expressions.  Falls back to ``unknown`` when no pattern matches
and sets ``debug_required = True`` so the Orchestrator can request a
debug-mode re-run.

Unknown-class handling can be handled by an LLM-powered agent.
analysis) — this agent never speculates on root cause.
"""

import asyncio
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .base import AgentConfig, BaseAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pattern table
# Order matters: more-specific / higher-severity patterns come first.
# ---------------------------------------------------------------------------

# (compiled_regex, error_class)
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Xcelium compile / elaboration errors
    (re.compile(r"\*[EF],\w+", re.IGNORECASE), "compile_error"),
    (re.compile(r"xmelab.*error", re.IGNORECASE), "compile_error"),
    # GHDL compile errors
    (re.compile(r"ghdl:\s+error:", re.IGNORECASE), "compile_error"),
    # UVM fatal (highest severity runtime error)
    (re.compile(r"UVM_FATAL", re.IGNORECASE), "uvm_fatal"),
    # Protocol / assertion failures
    (re.compile(r"assertion failed|report.*severity failure", re.IGNORECASE), "sim_assertion"),
    # cocotb / pyuvm Python-level failures
    (re.compile(r"AssertionError|TestFailure", re.IGNORECASE), "cocotb_error"),
    # Scoreboard mismatch (check before generic uvm_error)
    (
        re.compile(r"scoreboard.*mismatch|mismatch.*scoreboard", re.IGNORECASE),
        "scoreboard_mismatch",
    ),
    # X/Z propagation
    (re.compile(r"\bX\b.*propagat|x_prop", re.IGNORECASE), "x_propagation"),
    # Generic UVM error
    (re.compile(r"UVM_ERROR", re.IGNORECASE), "uvm_error"),
    # Timeouts
    (re.compile(r"SimTimeoutError|Timeout|timed?\s*out", re.IGNORECASE), "timeout"),
]

# Classes where a debug re-run is unlikely to help
_NO_DEBUG_CLASSES = frozenset({"compile_error"})

# ---------------------------------------------------------------------------
# Granular sub-type patterns (CVDP-informed failure clusters)
# ---------------------------------------------------------------------------
# Checked against the matched line after the top-level error_class is
# determined.  The Orchestrator uses failure_subtype to detect when the
# failure *kind* shifts between iterations and escalate early instead of
# burning the whole token budget on a shifting error space.

_COMPILE_SUBTYPE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"`timescale|no\s+timescale|timescale\s+not|missing.*timescale", re.IGNORECASE),
        "missing_timescale",
    ),
    (
        re.compile(
            r"unmatched|unexpected\s+end\b|missing\s+end\b|begin\s+without|"
            r"fork\s+without|endmodule.*without",
            re.IGNORECASE,
        ),
        "unmatched_block",
    ),
    (
        re.compile(r"blocking.*non.?blocking|non.?blocking.*blocking|mixed.*assign", re.IGNORECASE),
        "mixed_assignment",
    ),
    (
        re.compile(
            r"multiple\s+driver|driven\s+by\s+multiple|already\s+driven|multiple.*drive",
            re.IGNORECASE,
        ),
        "multiple_drivers",
    ),
    (
        re.compile(r"width\s+mismatch|bit.width|size\s+mismatch|truncat", re.IGNORECASE),
        "width_mismatch",
    ),
    (
        re.compile(
            r"port\s+not\s+found|undefined\s+port|port\s+mismatch|"
            r"interface\s+mismatch|connection\s+error",
            re.IGNORECASE,
        ),
        "interface_mismatch",
    ),
]

_SIM_SUBTYPE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"scoreboard", re.IGNORECASE), "scoreboard_fail"),
    (
        re.compile(r"coverage|covergroup|0\s+hit|bin.*not.*hit|bin.*miss", re.IGNORECASE),
        "coverage_miss",
    ),
    (
        re.compile(r"timing|synchroni[sz]|clock.*edge|cycle.*off|latency.*exceed", re.IGNORECASE),
        "timing_offset",
    ),
    (
        re.compile(r"interface|port\s+mismatch|signal.*mismatch|connection.*fail", re.IGNORECASE),
        "interface_mismatch",
    ),
    (
        re.compile(r"protocol|sva\b|property.*fail|assertion.*fail", re.IGNORECASE),
        "protocol_violation",
    ),
]


@dataclass
class FailureSummary:
    """Structured result produced by :class:`LogAnalyzerAgent`.

    Granular sub-category within *error_class*.

    Used by the Orchestrator's dynamic escalation logic: when the
    *failure_subtype* shifts between consecutive log-analyzer calls the
    Orchestrator escalates immediately instead of continuing to iterate,
    saving token budget on a shifting error space.

    Compile-error subtypes (CVDP cluster-informed):
      ``missing_timescale``, ``unmatched_block``, ``mixed_assignment``,
      ``multiple_drivers``, ``width_mismatch``, ``interface_mismatch``,
      ``syntax_general``

    Sim-error subtypes:
      ``scoreboard_fail``, ``coverage_miss``, ``timing_offset``,
      ``interface_mismatch``, ``protocol_violation``, ``sim_general``
    """

    error_class: str
    first_occurrence: str  # "line N" or "N/A"
    message: str  # first matching line, trimmed to 120 chars
    failure_subtype: str = "unknown"
    context_lines: list[str] = field(default_factory=list)
    debug_required: bool = False
    next_step: str = ""

    def to_str(self) -> str:
        ctx = "\n".join(self.context_lines) or "(none)"
        debug = f"YES — {self.next_step}" if self.debug_required else "NO  — log is sufficient"
        return (
            f"### Failure Summary\n"
            f"error_class      : {self.error_class}\n"
            f"failure_subtype  : {self.failure_subtype}\n"
            f"first_occurrence : {self.first_occurrence}\n"
            f"message          : {self.message}\n\n"
            f"### Context Window\n{ctx}\n\n"
            f"### Debug Mode Required\n{debug}\n\n"
            f"### Recommended Next Step\n{self.next_step}"
        )


class LogAnalyzerAgent(BaseAgent):
    """Parses simulation logs and returns a structured :class:`FailureSummary`.

    Does not require LLM access.  Analysis is purely regex-based.
    An LLM agent can provide reasoning for ``unknown`` class failures.

    Args:
        config: Agent configuration (budget is not consumed by this agent,
            but is required by the ABC).
    """

    def __init__(self, config: AgentConfig) -> None:
        super().__init__(config)

    # ------------------------------------------------------------------
    # BaseAgent ABC
    # ------------------------------------------------------------------

    async def run(self, task_input: str) -> str:
        """Analyse a log file or log content string.

        Args:
            task_input: Path to a log file *or* raw log content.
                If the string resolves to an existing file, the file is read;
                otherwise the string itself is treated as log content.

        Returns:
            A formatted :class:`FailureSummary` string.
        """
        if not task_input or not isinstance(task_input, str):
            raise ValueError("task_input must be a non-empty string")

        if self.iteration != 0:
            raise RuntimeError(f"Agent must start at iteration 0 (current: {self.iteration})")

        await self.step()  # Deterministic agent, one iteration per run
        summary = await asyncio.to_thread(self.analyze, task_input)
        return summary.to_str()

    # ------------------------------------------------------------------
    # Public helpers (useful for unit tests and downstream agents)
    # ------------------------------------------------------------------

    def analyze(self, content_or_path: str) -> FailureSummary:
        """Return a :class:`FailureSummary` for the given log content or file path."""
        return self._analyze(self._get_lines(content_or_path))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _get_lines(task_input: str) -> Iterator[str]:
        p = Path(task_input)
        if p.exists() and p.is_file():
            logger.info("LogAnalyzerAgent reading log from %s", p)
            with p.open(encoding="utf-8", errors="replace") as f:
                for line in f:
                    yield line.rstrip("\r\n")
        else:
            yield from task_input.splitlines()

    def _analyze(self, lines_iter: Iterator[str]) -> FailureSummary:
        prev_line: str | None = None

        for i, line in enumerate(lines_iter):
            for pattern, error_class in _PATTERNS:
                if pattern.search(line):
                    # Found match. Capture 1 line before, current, and 2 lines after.
                    context = []
                    if prev_line is not None:
                        context.append(prev_line)
                    context.append(line)

                    # Try to grab up to 2 more lines
                    for _ in range(2):
                        try:
                            context.append(next(lines_iter).rstrip("\r\n"))
                        except StopIteration:
                            break

                    debug_required = self._needs_debug(error_class, context, lines_iter)
                    failure_subtype = self._classify_subtype(error_class, "\n".join(context))
                    return FailureSummary(
                        error_class=error_class,
                        first_occurrence=f"line {i + 1}",
                        message=line[:120].strip(),
                        failure_subtype=failure_subtype,
                        context_lines=context,
                        debug_required=debug_required,
                        next_step=self._recommend(error_class, debug_required),
                    )
            prev_line = line

        # No pattern matched
        return FailureSummary(
            error_class="unknown",
            first_occurrence="N/A",
            message="No recognisable error pattern found.",
            failure_subtype="unknown",
            context_lines=[],
            debug_required=True,
            next_step="Re-run in debug mode with +UVM_VERBOSITY=UVM_HIGH.",
        )

    @staticmethod
    def _classify_subtype(error_class: str, text: str) -> str:
        """Return a granular failure sub-type for dynamic escalation tracking.

        Matches the combined text of the matched line plus its context window
        against the CVDP-informed sub-type pattern tables.

        Args:
            error_class: Top-level class already determined by :attr:`_PATTERNS`.
            text: Concatenated matched line + context lines to search.

        Returns:
            A sub-type string such as ``"missing_timescale"`` or
            ``"scoreboard_fail"``.  Falls back to ``"syntax_general"`` for
            compile errors and ``"sim_general"`` for runtime errors when no
            sub-type pattern matches.
        """
        if error_class == "compile_error":
            for pattern, subtype in _COMPILE_SUBTYPE_PATTERNS:
                if pattern.search(text):
                    return subtype
            return "syntax_general"

        if error_class in (
            "uvm_fatal",
            "uvm_error",
            "cocotb_error",
            "scoreboard_mismatch",
            "sim_assertion",
            "x_propagation",
            "timeout",
        ):
            for pattern, subtype in _SIM_SUBTYPE_PATTERNS:
                if pattern.search(text):
                    return subtype
            return "sim_general"

        # For "unknown" and any future classes, echo the class itself so the
        # Orchestrator can still track shifts (unknown→unknown is stable).
        return error_class

    @staticmethod
    def _needs_debug(error_class: str, context: list[str], remaining_lines: Iterator[str]) -> bool:
        """Return True when a debug-mode re-run would provide more information."""
        if error_class in _NO_DEBUG_CLASSES:
            return False

        # Multiple UVM_ERRORs but log may be truncated
        if error_class == "uvm_error":
            # Check context first (already consumed from iterator)
            if sum(1 for line in context if "UVM_ERROR" in line) > 1:
                return True
            # Then check remaining lines
            return any("UVM_ERROR" in line for line in remaining_lines)

        # Unknown class always needs more info
        return error_class == "unknown"

    @staticmethod
    def _recommend(error_class: str, debug_required: bool) -> str:
        if error_class == "compile_error":
            return "Compile error — pass to Code Generator for fix."
        if debug_required:
            return "Re-run in debug mode with +UVM_VERBOSITY=UVM_HIGH."
        if error_class in {"uvm_fatal", "sim_assertion", "cocotb_error"}:
            return "Pass to Bug Classifier with the above summary."
        return "Pass to Bug Classifier with the above summary."
