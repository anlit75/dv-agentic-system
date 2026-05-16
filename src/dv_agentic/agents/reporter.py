# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Session reporter agent.

Aggregates results from a completed agentic session and generates a
structured markdown report suitable for human review or ticket creation.

This agent is intentionally single-turn: the input is fully structured
and the LLM has everything it needs in one shot.  Budget > 1 is unused
in normal operation but respected for safety.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from ..prompts.context import ProjectContext, SessionState
from ..prompts.prompt_loader import PromptLoader
from ..tools.llm.interface import BaseLLMClient
from ..wiki.manager import WikiConfig
from .base import AgentConfig, BaseAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SessionReport:
    """Structured output from :class:`ReporterAgent`."""

    task_id: str
    markdown: str
    output_path: str  # path where report was written ("" if not written)

    def to_str(self) -> str:
        return self.markdown


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class ReporterAgent(BaseAgent):
    """Generates a structured markdown report from session results.

    Args:
        config: Agent configuration.
        llm: LLM client.
        output_path: Where to write the generated report.  Pass ``None``
            to skip writing.
        project_config: Optional context for PromptLoader enrichment.
        session: Optional session state.
        prompts_dir: Directory containing ``reporter.md``.
        wiki_config: Optional config to auto-ingest session results.
    """

    def __init__(
        self,
        config: AgentConfig,
        llm: BaseLLMClient,
        output_path: str | None = None,
        project_config: ProjectContext | None = None,
        session: SessionState | None = None,
        prompts_dir: str | Path | None = None,
        wiki_config: WikiConfig | None = None,
    ) -> None:
        super().__init__(config)
        self.llm = llm
        self.output_path = output_path
        self.project_config = project_config
        self.session = session
        self.prompts_dir = prompts_dir
        self.wiki_cfg = wiki_config

    # ------------------------------------------------------------------
    # BaseAgent ABC
    # ------------------------------------------------------------------

    async def run(self, task_input: str) -> str:
        """Aggregate results and generate a final report.

        Args:
            task_input: The history of agent interactions to summarize.

        Returns:
            A formatted markdown report string.
        """
        if not task_input or not isinstance(task_input, str):
            raise ValueError("task_input must be a non-empty string")

        system_prompt = self._load_system_prompt()

        if not system_prompt:
            raise RuntimeError("System prompt must not be empty")
        if self.iteration != 0:
            raise RuntimeError(f"Agent must start at iteration 0 (current: {self.iteration})")

        await self.step()  # consume one budget unit

        task_id = self._extract_task_id(task_input)
        response = await self.llm.complete(
            system_prompt,
            [{"role": "user", "content": task_input}],
            max_tokens=3000,
        )

        written_path = self._write_report(response, task_id)
        report = SessionReport(
            task_id=task_id,
            markdown=response,
            output_path=written_path,
        )
        logger.info("Reporter: generated report for task '%s'", task_id)

        if self.wiki_cfg and self.wiki_cfg.enabled:
            asyncio.create_task(  # noqa: RUF006
                asyncio.to_thread(self._auto_ingest_session, response, task_input, task_id)
            )

        return report.to_str()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _auto_ingest_session(self, response: str, task_input: str, task_id: str) -> None:
        try:
            from ..wiki.ingest import WikiIngestService

            if not self.wiki_cfg:
                return
            ingest_svc = WikiIngestService(self.wiki_cfg)
            # Heuristically parse the full session history for patterns, bugs, and coverage holes.
            ingest_svc.ingest_session(
                session_report=response,
                failure_summary=task_input,
                classification=task_input,
                coverage_summary=task_input,
                task_id=task_id,
            )
        except Exception:
            logger.debug("Reporter: auto-ingest failed (non-fatal)", exc_info=True)

    def _load_system_prompt(self) -> str:
        try:
            loader = PromptLoader(
                prompts_dir=self.prompts_dir,
                project_config=self.project_config,
                session=self.session,
            )
            return loader.load("reporter")
        except (FileNotFoundError, RuntimeError) as exc:
            logger.warning("PromptLoader unavailable (%s); using fallback.", exc)
            return (
                "You are a verification session reporter. "
                "Given the results from multiple agents in a session, produce a concise "
                "markdown report with these sections:\n"
                "## Summary\n## Simulation Results\n## Coverage\n## Issues Found\n"
                "## Recommended Next Steps\n"
                "Be factual and concise. Use tables where appropriate."
            )

    def _write_report(self, markdown: str, task_id: str) -> str:
        if not self.output_path:
            return ""
        path_str = self.output_path.replace("{task_id}", task_id)
        target = Path(path_str)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown, encoding="utf-8")
        logger.info("Reporter wrote report to %s", target)
        return str(target)

    @staticmethod
    def _extract_task_id(text: str) -> str:
        """Try to parse a task_id from the input; fall back to 'session'."""
        import re

        m = re.search(r"task[_\s]id\s*[:\s]+([a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
        return m.group(1) if m else "session"
