# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""SV/UVM testbench code generation agent.

Scope boundary
--------------
This agent operates exclusively on **testbench** files (sequences, scoreboards,
coverage groups, monitors, drivers, agents, env).  RTL source files are
strictly read-only — this agent must never create or modify them.

The ``allowed_dirs`` constructor parameter enforces this at write time.  When
set, any file path whose top-level directory is not in the whitelist raises a
``ValueError`` before a byte is written to disk.  ``..`` traversal is always
blocked regardless of ``allowed_dirs``.

Workflow
--------
1. Load the enriched ``code_generator`` system prompt via ``PromptLoader``.
2. Send the task description as the first user message.
3. Parse the LLM response for ``### Compile Confidence``.
4. **HIGH or MEDIUM** → extract code, write files, return report.
5. **LOW or UNKNOWN** → append open questions as a follow-up user message,
   repeat from step 3.
6. Stop when confidence passes or ``AgentConfig.budget`` is exhausted.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..prompts.context import ProjectContext, SessionState
from ..prompts.prompt_loader import PromptLoader
from ..tools.llm.interface import BaseLLMClient
from .base import AgentConfig, BaseAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TB directory whitelist (used by CLI; not enforced when allowed_dirs=None)
# ---------------------------------------------------------------------------

#: Default set of top-level directories considered testbench territory.
#: Paths whose first component is not in this set are rejected when
#: ``allowed_dirs`` is explicitly provided to :class:`CodeGeneratorAgent`.
DEFAULT_TB_ALLOWED_DIRS: frozenset[str] = frozenset(
    {
        "tb",
        "tests",
        "env",
        "sequences",
        "agents",
        "scoreboards",
        "monitors",
        "drivers",
        "coverage",
        "checkers",
        "assertions",
    }
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FileSpec:
    """A file path and its full content, ready to write to disk.

    Attributes:
        path: Relative or absolute destination path for the file.
        content: Full text content of the file.
    """

    path: str
    content: str


@dataclass
class ParsedResponse:
    """Structured fields extracted from one LLM response.

    Attributes:
        summary: Executive summary of the changes made by the LLM.
        changed_file_paths: List of paths identified in the 'Changed Files' section.
        file_specs: List of :class:`FileSpec` objects ready to be written to disk.
        open_questions: Feedback or questions from the LLM if confidence is low.
        confidence: Self-reported compile confidence ("HIGH", "MEDIUM", "LOW").
        confidence_reason: Detailed justification for the confidence rating.
        raw: The original raw string response from the LLM.
    """

    summary: str
    changed_file_paths: list[str]  # paths from ### Changed Files
    file_specs: list[FileSpec]  # paths + content ready to write
    open_questions: str
    confidence: str  # "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN"
    confidence_reason: str
    raw: str


@dataclass
class CodeTask:
    """Input specification for a single CodeGeneratorAgent run.

    Attributes:
        task_id: Unique identifier used in log messages and reports.
        description: Natural-language task for the LLM, e.g.
            ``"Generate a sequence targeting the back-pressure bin in
            axi_write_cov.hit_max_outstanding"``.
    """

    task_id: str
    description: str


@dataclass
class CodeReport:
    """Structured output from a completed :class:`CodeGeneratorAgent` run.

    Attributes:
        task_id: Unique identifier for the code generation task.
        final_status: Termination state ("pass" or "budget_exhausted").
        iterations: Total number of LLM calls made.
        files_written: List of absolute paths to the files written to disk.
        confidence: Final self-reported confidence from the LLM.
        summary: Final summary of the changes implemented.
        open_questions: Remaining questions or issues if status is not "pass".
    """

    task_id: str
    final_status: str  # "pass" | "budget_exhausted"
    iterations: int
    files_written: list[str] = field(default_factory=list)
    confidence: str = "UNKNOWN"
    summary: str = ""
    open_questions: str = ""

    def to_str(self) -> str:
        status_note = "✓" if self.final_status == "pass" else "⚠ budget exhausted"
        lines = [
            "### Code Generation Report",
            f"task_id      : {self.task_id}",
            f"final_status : {self.final_status}  {status_note}",
            f"iterations   : {self.iterations}",
            f"confidence   : {self.confidence}",
        ]
        if self.files_written:
            lines.append("files_written :")
            for f in self.files_written:
                lines.append(f"  - {f}")
        if self.summary:
            lines += ["", "### Summary", self.summary]
        if self.open_questions:
            lines += ["", "### Open Questions", self.open_questions]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class CodeGeneratorAgent(BaseAgent):
    """Generates and modifies SV/UVM **testbench** code through multi-turn LLM dialogue.

    Terminates when the LLM reports HIGH or MEDIUM compile confidence or when
    ``AgentConfig.budget`` iterations are exhausted.

    Args:
        config: Agent configuration.
        llm: Any :class:`BaseLLMClient`.
        project_config: Optional project context for PromptLoader enrichment.
        session: Optional session state injected into the system prompt.
        prompts_dir: Directory containing ``code_generator.md``.
        workspace_dir: Root directory where generated files are written.
        allowed_dirs: Whitelist of top-level directory names the agent may
            write into.  ``None`` (default) disables the check — use
            :data:`DEFAULT_TB_ALLOWED_DIRS` in production.  ``..`` traversal
            is always blocked regardless of this setting.
    """

    #: Confidence levels that signal a passing self-review.
    PASS_CONFIDENCE: frozenset[str] = frozenset({"HIGH", "MEDIUM"})

    _SECTION_RE = re.compile(r"^###\s+(.+)$", re.MULTILINE)
    _CODE_BLOCK_RE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)
    _CONFIDENCE_RE = re.compile(r"\b(HIGH|MEDIUM|LOW)\b", re.IGNORECASE)
    _FILE_PATH_RE = re.compile(r"`([^`]+\.[a-zA-Z]+)`")
    _FILE_MARKER_RE = re.compile(
        r"^(?://|#)\s*(?:file:|===)\s*(.+?)(?:\s*===)?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    def __init__(
        self,
        config: AgentConfig,
        llm: BaseLLMClient,
        project_config: ProjectContext | None = None,
        session: SessionState | None = None,
        prompts_dir: Path | str | None = None,
        workspace_dir: str = ".",
        allowed_dirs: frozenset[str] | set[str] | None = None,
    ) -> None:
        super().__init__(config)
        self.llm = llm
        self.project_config = project_config
        self.session = session
        self.prompts_dir = Path(prompts_dir) if prompts_dir else None
        self.workspace_dir = Path(workspace_dir)
        # Freeze for safety; None means "no restriction" (test / custom use)
        self.allowed_dirs: frozenset[str] | None = (
            frozenset(allowed_dirs) if allowed_dirs is not None else None
        )

    # ------------------------------------------------------------------
    # BaseAgent ABC
    # ------------------------------------------------------------------

    async def run(self, task_input: str | CodeTask) -> str:
        """Run the code generation loop.

        Args:
            task_input: A :class:`CodeTask` or a plain string description.
                When a plain string is given, ``task_id`` defaults to
                ``"codegen_task"``.

        Returns:
            A formatted :class:`CodeReport` string.
        """
        if not task_input or not isinstance(task_input, str | CodeTask):
            raise ValueError("task_input must be a non-empty string or CodeTask")

        task = self._parse_task(task_input)
        system_prompt = self._load_system_prompt()

        if not system_prompt:
            raise RuntimeError("System prompt must not be empty")
        if self.iteration != 0:
            raise RuntimeError(f"Agent must start at iteration 0 (current: {self.iteration})")

        history: list[dict[str, str]] = [{"role": "user", "content": task.description}]
        files_written: list[str] = []
        last_parsed: ParsedResponse | None = None

        while await self.step():
            logger.info("CodeGenerator iter=%d task_id=%s", self.iteration, task.task_id)
            response = await self.llm.complete(system_prompt, history, max_tokens=4000)
            history.append({"role": "assistant", "content": response})

            last_parsed = self._parse_response(response)
            logger.info("Confidence=%s iter=%d", last_parsed.confidence, self.iteration)

            if last_parsed.confidence in self.PASS_CONFIDENCE:
                written = self._write_files(last_parsed.file_specs, str(self.workspace_dir))
                files_written.extend(written)
                return CodeReport(
                    task_id=task.task_id,
                    final_status="pass",
                    iterations=self.iteration,
                    files_written=files_written,
                    confidence=last_parsed.confidence,
                    summary=last_parsed.summary,
                    open_questions=last_parsed.open_questions,
                ).to_str()

            # LOW / UNKNOWN: feed open questions back as a follow-up
            history.append({"role": "user", "content": self._build_follow_up(last_parsed)})

        # Budget exhausted — persist whatever the last iteration produced
        if last_parsed and last_parsed.file_specs:
            written = self._write_files(last_parsed.file_specs, str(self.workspace_dir))
            files_written.extend(written)

        return CodeReport(
            task_id=task.task_id,
            final_status="budget_exhausted",
            iterations=self.iteration,
            files_written=files_written,
            confidence=last_parsed.confidence if last_parsed else "UNKNOWN",
            summary=last_parsed.summary if last_parsed else "",
            open_questions=last_parsed.open_questions if last_parsed else "",
        ).to_str()

    # ------------------------------------------------------------------
    # Private — task parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_task(task_input: str | CodeTask) -> CodeTask:
        if isinstance(task_input, CodeTask):
            return task_input
        return CodeTask(task_id="codegen_task", description=task_input)

    # ------------------------------------------------------------------
    # Private — system prompt
    # ------------------------------------------------------------------

    def _load_system_prompt(self) -> str:
        """Load and enrich the code_generator prompt; fall back if unavailable."""
        try:
            loader = PromptLoader(
                prompts_dir=self.prompts_dir,
                project_config=self.project_config,
                session=self.session,
            )
            return loader.load("code_generator")
        except (FileNotFoundError, RuntimeError) as exc:
            logger.warning("PromptLoader unavailable (%s); using minimal fallback prompt.", exc)
            return (
                "You are a SystemVerilog / UVM testbench code generation specialist. "
                "Generate correct, simulation-ready SV/UVM testbench code. "
                "Never modify RTL source files. "
                "Always end your response with:\n"
                "### Compile Confidence\n"
                "HIGH | MEDIUM | LOW — brief justification."
            )

    # ------------------------------------------------------------------
    # Private — response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, response: str) -> ParsedResponse:
        """Extract structured fields from one LLM response."""
        if not response or not isinstance(response, str):
            raise ValueError("LLM response must be a non-empty string")

        sections = self._split_sections(response)

        summary = sections.get("Summary", "").strip()
        changed_files_text = sections.get("Changed Files", "")
        code_text = sections.get("Code", "")
        open_questions = sections.get("Open Questions", "").strip()
        confidence_text = sections.get("Compile Confidence", "")

        m = self._CONFIDENCE_RE.search(confidence_text)
        confidence = m.group(1).upper() if m else "UNKNOWN"
        file_paths = self._FILE_PATH_RE.findall(changed_files_text)
        file_specs = self._extract_file_specs(code_text, file_paths)

        parsed = ParsedResponse(
            summary=summary,
            changed_file_paths=file_paths,
            file_specs=file_specs,
            open_questions=open_questions,
            confidence=confidence,
            confidence_reason=confidence_text.strip(),
            raw=response,
        )

        if parsed.confidence not in ("HIGH", "MEDIUM", "LOW", "UNKNOWN"):
            raise ValueError(f"Invalid confidence level extracted: {parsed.confidence}")
        if not isinstance(parsed.file_specs, list):
            raise TypeError("file_specs must be a list")
        return parsed

    def _split_sections(self, text: str) -> dict[str, str]:
        """Split a response string by ``### `` headers."""
        result: dict[str, str] = {}
        matches = list(self._SECTION_RE.finditer(text))
        for i, match in enumerate(matches):
            name = match.group(1).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            result[name] = text[start:end]
        return result

    def _extract_file_specs(self, code_text: str, file_paths: list[str]) -> list[FileSpec]:
        """Map code blocks to :class:`FileSpec` objects.

        Tries three strategies in order:

        1. **N blocks : N paths** — one code block per changed file path.
        2. **File markers** — single block with ``// file: path`` markers.
        3. **Fallback** — single block assigned to the first changed file path.
        """
        code_blocks = self._CODE_BLOCK_RE.findall(code_text)
        if not code_blocks:
            return []

        # Strategy 1: one block per path
        if len(code_blocks) == len(file_paths) and file_paths:
            return [
                FileSpec(path=p, content=c.strip())
                for p, c in zip(file_paths, code_blocks, strict=True)
            ]

        # Strategy 2: file markers inside a single block
        specs = self._split_by_markers(code_blocks[0])
        if specs:
            return specs

        # Strategy 3: fallback
        if file_paths:
            return [FileSpec(path=file_paths[0], content=code_blocks[0].strip())]

        return []

    def _split_by_markers(self, code: str) -> list[FileSpec]:
        """Split *code* on ``// file: path`` or ``// === path ===`` markers."""
        # re.split with a capturing group → [pre, path, content, path, content, ...]
        parts = self._FILE_MARKER_RE.split(code)
        if len(parts) < 3:  # no marker found
            return []

        specs: list[FileSpec] = []
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                specs.append(FileSpec(path=parts[i].strip(), content=parts[i + 1].strip()))
        return specs

    # ------------------------------------------------------------------
    # Private — path validation  ← NEW
    # ------------------------------------------------------------------

    def _validate_path(self, spec_path: str) -> None:
        """Validate that *spec_path* is safe to write.

        Two rules, applied unconditionally:

        1. **No traversal**: ``..`` anywhere in the path is rejected.
        2. **Whitelist** (only when ``self.allowed_dirs`` is set): the
           top-level directory component must be in the whitelist.  Flat
           paths (no directory component) are always allowed.

        Args:
            spec_path: Relative path as returned by the LLM.

        Raises:
            ValueError: If the path fails either check.
        """
        p = Path(spec_path)

        # Check for Windows drive specifier (e.g. C:) even on non-Windows/Linux hosts
        has_win_drive = len(spec_path) >= 2 and spec_path[1] == ":" and spec_path[0].isalpha()

        # Rule 1: block traversal and absolute paths regardless of whitelist
        if (
            p.is_absolute()
            or spec_path.startswith("/")
            or spec_path.startswith("\\")
            or has_win_drive
            or ".." in p.parts
        ):
            raise ValueError(
                f"Absolute paths and path traversal are not allowed: '{spec_path}'. "
                "The LLM must use relative paths within the workspace and "
                "not use '..' to escape it."
            )

        # Rule 2: whitelist check (only when configured)
        if self.allowed_dirs is not None and len(p.parts) > 1:
            top = p.parts[0]
            if top not in self.allowed_dirs:
                raise ValueError(
                    f"Path '{spec_path}' targets directory '{top}' which is outside "
                    f"the allowed testbench directories: {sorted(self.allowed_dirs)}. "
                    "RTL source files are read-only — this agent must not modify them."
                )

    # ------------------------------------------------------------------
    # Private — follow-up message + file writing
    # ------------------------------------------------------------------

    @staticmethod
    def _build_follow_up(parsed: ParsedResponse) -> str:
        lines = [
            "Your compile confidence was LOW or could not be determined. "
            "Please revise the code to address the following issues:",
            "",
            parsed.open_questions
            if parsed.open_questions
            else (
                "Review against the self-review checklist in the system prompt "
                "and fix any outstanding issues."
            ),
            "",
            "Provide the complete revised code with the same output format "
            "and a new ### Compile Confidence assessment.",
        ]
        return "\n".join(lines)

    def _write_files(self, file_specs: list[FileSpec], workspace_dir: str) -> list[str]:
        """Write *file_specs* under *workspace_dir*; return written paths.

        Every path is validated via :meth:`_validate_path` before any file
        system operation takes place.
        """
        if not workspace_dir:
            raise ValueError("workspace_dir must not be empty")
        if not isinstance(file_specs, list):
            raise TypeError("file_specs must be a list")

        base = Path(workspace_dir)
        if not base.exists():
            raise FileNotFoundError(f"Workspace directory {base} must exist")

        written: list[str] = []
        for spec in file_specs:
            if not spec.path:
                raise ValueError("File spec must have a path")
            if spec.content is None:
                raise ValueError(f"File spec {spec.path} must have content")

            self._validate_path(spec.path)

            target = base / spec.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(spec.content, encoding="utf-8")
            logger.info("Wrote %s (%d chars)", target, len(spec.content))
            written.append(str(target))

        if len(written) != len(file_specs):
            msg = f"File write mismatch: {len(written)} written, {len(file_specs)} expected"
            raise RuntimeError(msg)
        return written
