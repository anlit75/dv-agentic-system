# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Wiki query service — reads wiki knowledge for PromptLoader injection.

All public methods are **synchronous** and safe to call from
``PromptLoader._gather_context()`` (which runs on the main thread).

Every method degrades gracefully:
  * Empty wiki        → returns ``""`` (never raises)
  * Missing directory → returns ``""``
  * Malformed page    → skipped with DEBUG log

Phase A exports:
  ``get_known_error_patterns()``  — for ``{{KNOWN_ERROR_PATTERNS}}``
  ``get_pattern_summary()``       — for ``{{WIKI_PATTERN_SUMMARY}}``
  ``get_pattern_page()``          — direct lookup by failure_subtype

Phase B stubs (return ``""`` until implemented):
  ``get_known_rtl_bugs()``        — for ``{{KNOWN_RTL_BUGS}}``

Phase C stubs:
  ``get_coverage_history()``      — for ``{{COVERAGE_HOLE_HISTORY}}``
"""

from __future__ import annotations

import logging
from typing import Any

from .manager import WikiConfig, parse_page

logger = logging.getLogger(__name__)

# Conservative chars-per-token for context budget estimation
_CHARS_PER_TOKEN = 4


def _budget_chars(tokens: int) -> int:
    return tokens * _CHARS_PER_TOKEN


class WikiQueryService:
    """Reads wiki pages and formats them for prompt injection.

    Args:
        wiki_config: Wiki integration configuration.
    """

    def __init__(self, wiki_config: WikiConfig) -> None:
        self.cfg = wiki_config

    # ------------------------------------------------------------------
    # Phase A: pattern queries (used by PromptLoader in Phase A)
    # ------------------------------------------------------------------

    def get_known_error_patterns(
        self,
        error_class: str | None = None,
        failure_subtype: str | None = None,
        top_k: int = 5,
    ) -> str:
        """Return a formatted summary of known error patterns.

        Reads ``patterns/*.md``, sorts by ``hit_count`` descending, and
        formats the top *top_k* entries within the configured token budget.

        Args:
            error_class: Optional filter — only include patterns whose
                ``error_class`` frontmatter field matches this value.
            failure_subtype: Optional filter — only include an exact
                ``failure_subtype`` match.
            top_k: Maximum number of patterns to include.

        Returns:
            Markdown-formatted text block ready for ``{{KNOWN_ERROR_PATTERNS}}``,
            or an empty string if the wiki has no pattern pages.

        Example output::

            ### Known Error Patterns (from DV Wiki)

            **missing_timescale** (error_class: compile_error, hit_count: 7, fix_rate: 100%)
              → Check: patterns/missing_timescale.md for fix template.
        """
        entries = self._load_pattern_entries(error_class, failure_subtype)
        if not entries:
            return ""

        entries.sort(key=lambda e: int(e.get("hit_count", 0)), reverse=True)
        entries = entries[:top_k]

        header = "### Known Error Patterns (from DV Wiki)"
        char_budget = _budget_chars(self.cfg.pattern_context_tokens) - len(header)
        blocks: list[str] = [header]

        for entry in entries:
            block = self._format_pattern_entry(entry)
            if char_budget - len(block) < 0:
                blocks.append("*(additional patterns omitted — token budget reached)*")
                break
            blocks.append(block)
            char_budget -= len(block)

        return "\n\n".join(blocks)

    def get_pattern_summary(self) -> str:
        """Return a compact statistics table of all patterns.

        Used for ``{{WIKI_PATTERN_SUMMARY}}`` injection into
        ``code_generator`` prompts so the agent is aware of recurring
        compile failure patterns.

        Returns:
            A Markdown table or empty string if no pattern pages exist.
        """
        entries = self._load_pattern_entries()
        if not entries:
            return ""

        entries.sort(key=lambda e: int(e.get("hit_count", 0)), reverse=True)

        rows = [
            "| Pattern | Error Class | Hits | Fix Rate |",
            "|---------|-------------|------|----------|",
        ]
        for e in entries:
            rate = e.get("fix_success_rate")
            rate_str = f"{rate:.0%}" if isinstance(rate, int | float) else "N/A"
            rows.append(
                f"| {e.get('pattern_id', '?')} "
                f"| {e.get('error_class', '?')} "
                f"| {e.get('hit_count', 0)} "
                f"| {rate_str} |"
            )

        return "### Wiki Pattern Statistics\n" + "\n".join(rows)

    def get_pattern_page(self, failure_subtype: str) -> str | None:
        """Return the raw content of a specific pattern page.

        Args:
            failure_subtype: Exact identifier (e.g. ``"missing_timescale"``).

        Returns:
            Full page content, or ``None`` if the page does not exist.
        """
        page = self.cfg.wiki_dir / "patterns" / f"{failure_subtype}.md"
        if not page.exists():
            return None
        try:
            return page.read_text(encoding="utf-8")
        except OSError:
            return None

    # ------------------------------------------------------------------
    # Phase B stub
    # ------------------------------------------------------------------

    def get_known_rtl_bugs(
        self,
        ip_type: str | None = None,
        status: str = "open",
        top_k: int = 5,
    ) -> str:
        """Return open RTL bug summaries for ``{{KNOWN_RTL_BUGS}}``.

        Reads ``bugs/*.md``, filters by ``type == 'RTL_BUG'``, ``status``,
        and optionally ``ip_type``. Sorts by ``confidence`` descending
        and formats the top *top_k* entries within the configured token budget.
        """
        bugs_dir = self.cfg.wiki_dir / "bugs"
        if not bugs_dir.is_dir():
            return ""

        entries: list[dict[str, Any]] = []
        for md in sorted(bugs_dir.glob("*.md")):
            if md.name.startswith("_"):
                continue
            try:
                fm, _ = parse_page(md.read_text(encoding="utf-8"))
                if not fm or fm.get("type") != "RTL_BUG":
                    continue
                if fm.get("status") != status:
                    continue
                if ip_type and fm.get("ip_type") != ip_type:
                    continue
                entries.append(fm)
            except Exception:
                logger.debug("WikiQueryService: could not read %s", md)

        if not entries:
            return ""

        # Sort by confidence descending
        entries.sort(key=lambda e: float(e.get("confidence", 0.0)), reverse=True)
        entries = entries[:top_k]

        header = "### Known RTL Bugs (from DV Wiki)"
        char_budget = _budget_chars(self.cfg.bug_context_tokens) - len(header)
        blocks: list[str] = [header]

        for entry in entries:
            block = self._format_bug_entry(entry)
            if char_budget - len(block) < 0:
                blocks.append("*(additional bugs omitted — token budget reached)*")
                break
            blocks.append(block)
            char_budget -= len(block)

        return "\n\n".join(blocks)

    # ------------------------------------------------------------------
    # Phase C stub
    # ------------------------------------------------------------------

    def get_coverage_history(
        self,
        covergroup: str | None = None,
        top_k: int = 5,
    ) -> str:
        """Return coverage hole history for ``{{COVERAGE_HOLE_HISTORY}}``.

        Reads ``coverage/*.md``, filters optionally by ``covergroup``,
        and formats the top *top_k* entries within token budget.
        """
        cov_dir = self.cfg.wiki_dir / "coverage"
        if not cov_dir.is_dir():
            return ""

        entries: list[dict[str, Any]] = []
        for md in sorted(cov_dir.glob("*.md")):
            if md.name.startswith("_"):
                continue
            try:
                fm, _ = parse_page(md.read_text(encoding="utf-8"))
                if not fm or fm.get("type") != "COVERAGE_HOLE":
                    continue
                if covergroup and fm.get("covergroup") != covergroup:
                    continue
                entries.append(fm)
            except Exception:
                logger.debug("WikiQueryService: could not read %s", md)

        if not entries:
            return ""

        # Prioritize actionable holes first, then by bin name
        def _sort_key(e: dict[str, Any]) -> tuple[int, str]:
            aclass = e.get("action_class", "")
            # actionable -> 0, others -> 1
            rank = 0 if aclass == "actionable" else 1
            return (rank, e.get("bin", ""))

        entries.sort(key=_sort_key)
        entries = entries[:top_k]

        header = "### Coverage History"
        char_budget = _budget_chars(self.cfg.coverage_context_tokens) - len(header)
        blocks: list[str] = [header]

        for entry in entries:
            block = self._format_coverage_entry(entry)
            if char_budget - len(block) < 0:
                blocks.append("*(additional coverage omitted — token budget reached)*")
                break
            blocks.append(block)
            char_budget -= len(block)

        return "\n\n".join(blocks)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_pattern_entries(
        self,
        error_class: str | None = None,
        failure_subtype: str | None = None,
    ) -> list[dict[str, Any]]:
        """Scan ``patterns/`` and return parsed frontmatter dicts."""
        patterns_dir = self.cfg.wiki_dir / "patterns"
        if not patterns_dir.is_dir():
            return []

        entries: list[dict[str, Any]] = []
        for md in sorted(patterns_dir.glob("*.md")):
            if md.name.startswith("_"):
                continue
            try:
                fm, _ = parse_page(md.read_text(encoding="utf-8"))
                if not fm:
                    continue
                if error_class and fm.get("error_class") != error_class:
                    continue
                if failure_subtype and fm.get("failure_subtype") != failure_subtype:
                    continue
                entries.append(fm)
            except Exception:
                logger.debug("WikiQueryService: could not read %s", md)
        return entries

    @staticmethod
    def _format_pattern_entry(fm: dict[str, Any]) -> str:
        """Format one pattern frontmatter into a prompt-injectable block."""
        pid = fm.get("pattern_id", "unknown")
        ec = fm.get("error_class", "unknown")
        hits = fm.get("hit_count", 0)
        rate = fm.get("fix_success_rate")
        rate_str = f"{rate:.0%}" if isinstance(rate, int | float) else "N/A"
        return (
            f"**{pid}** "
            f"(error_class: {ec}, hit_count: {hits}, fix_rate: {rate_str})\n"
            f"  → Fix template: patterns/{pid}.md"
        )

    @staticmethod
    def _format_bug_entry(fm: dict[str, Any]) -> str:
        """Format one bug frontmatter into a prompt-injectable block."""
        bug_id = fm.get("id", "unknown")
        ec = fm.get("error_class", "unknown")
        fs = fm.get("failure_subtype", "unknown")
        conf = fm.get("confidence", 0.0)
        return (
            f"**{bug_id}** "
            f"(error_class: {ec}, subtype: {fs}, confidence: {conf})\n"
            f"  → Check: bugs/{bug_id}.md"
        )

    @staticmethod
    def _format_coverage_entry(fm: dict[str, Any]) -> str:
        """Format one coverage hole frontmatter into a prompt-injectable block."""
        cg = fm.get("covergroup", "unknown")
        bname = fm.get("bin", "unknown")
        aclass = fm.get("action_class", "unknown")
        filled = fm.get("filled", False)
        return (
            f"**{cg}_{bname}** "
            f"(action_class: {aclass}, filled: {filled})\n"
            f"  → Check: coverage/{cg}_{bname}.md"
        )
