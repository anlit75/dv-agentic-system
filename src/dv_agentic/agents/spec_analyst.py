# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Spec analysis agent.

Parses a specification document (plain text or pre-extracted PDF content)
and generates a structured verification plan (vplan) in YAML format.

Workflow
--------
1. Send the spec text to the LLM with the spec_analyst system prompt.
2. Parse the YAML block from the response.
3. If a complete YAML block is found → write to disk and return VplanResult.
4. If incomplete or no YAML → ask the LLM to produce a complete plan and retry.
5. Stop when a valid vplan is extracted or budget is exhausted.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from ..prompts.context import ProjectContext, SessionState
from ..prompts.prompt_loader import PromptLoader
from ..tools.llm.interface import BaseLLMClient
from .base import AgentConfig, BaseAgent

logger = logging.getLogger(__name__)

_YAML_BLOCK_RE = re.compile(r"```ya?ml\n(.*?)```", re.DOTALL)
_FEATURE_RE = re.compile(r"^\s*-\s+name\s*:", re.MULTILINE)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class VplanResult:
    """Structured output from :class:`SpecAnalystAgent`."""

    vplan_yaml: str
    feature_count: int
    output_path: str  # path where vplan.yaml was written ("" if not written)
    summary: str
    iterations: int

    def to_str(self) -> str:
        lines = [
            "### Vplan Result",
            f"feature_count : {self.feature_count}",
            f"iterations    : {self.iterations}",
            f"output_path   : {self.output_path or '(not written)'}",
            "",
            "### Summary",
            self.summary,
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class SpecAnalystAgent(BaseAgent):
    """Parses a spec document and produces a structured vplan.yaml.

    Args:
        config: Agent configuration (``budget`` caps LLM call count).
        llm: LLM client.
        output_path: Where to write the generated vplan.yaml.  Pass ``None``
            to skip writing (useful in tests or preview mode).
        project_config: Optional context for PromptLoader enrichment.
        session: Optional session state.
        prompts_dir: Directory containing ``spec_analyst.md``.
    """

    _YAML_RE = _YAML_BLOCK_RE

    def __init__(
        self,
        config: AgentConfig,
        llm: BaseLLMClient,
        output_path: str | None = ".agent/vplan.yaml",
        project_config: ProjectContext | None = None,
        session: SessionState | None = None,
        prompts_dir: str | Path | None = None,
    ) -> None:
        super().__init__(config)
        self.llm = llm
        self.output_path = output_path
        self.project_config = project_config
        self.session = session
        self.prompts_dir = prompts_dir

    # ------------------------------------------------------------------
    # BaseAgent ABC
    # ------------------------------------------------------------------

    async def run(self, task_input: str) -> str:
        """Parse specifications and generate a verification plan.

        Args:
            task_input: Natural language description of the verification
                scope or paths to spec documents.

        Returns:
            A string containing the generated vplan (YAML format).
        """
        if not task_input or not isinstance(task_input, str):
            raise ValueError("task_input must be a non-empty string")

        system_prompt = self._load_system_prompt()

        if not system_prompt:
            raise RuntimeError("System prompt must not be empty")
        if self.iteration != 0:
            raise RuntimeError(f"Agent must start at iteration 0 (current: {self.iteration})")

        history: list[dict[str, str]] = [{"role": "user", "content": task_input}]
        last_yaml = ""

        while await self.step():
            response = await self.llm.complete(system_prompt, history, max_tokens=4000)
            history.append({"role": "assistant", "content": response})

            yaml_block = self._extract_yaml(response)
            # Only count as 'last_yaml' if it was specifically extracted as a block
            if self._YAML_RE.search(response):
                last_yaml = yaml_block
                logger.info("SpecAnalyst iter=%d: vplan YAML extracted", self.iteration)
                break

            # No valid YAML yet — ask the LLM to produce a complete one
            logger.info("SpecAnalyst iter=%d: no YAML found, retrying", self.iteration)
            history.append({"role": "user", "content": self._follow_up()})

        if not last_yaml:
            return VplanResult(
                vplan_yaml="",
                feature_count=0,
                output_path="",
                summary="Budget exhausted before a valid vplan was extracted.",
                iterations=self.iteration,
            ).to_str()

        feature_count = len(_FEATURE_RE.findall(last_yaml))
        written_path = self._write_vplan(last_yaml)
        summary = self._extract_summary(history)

        return VplanResult(
            vplan_yaml=last_yaml,
            feature_count=feature_count,
            output_path=written_path,
            summary=summary,
            iterations=self.iteration,
        ).to_str()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _load_system_prompt(self) -> str:
        try:
            loader = PromptLoader(
                prompts_dir=self.prompts_dir,
                project_config=self.project_config,
                session=self.session,
            )
            return loader.load("spec_analyst")
        except (FileNotFoundError, RuntimeError) as exc:
            logger.warning("PromptLoader unavailable (%s); using fallback.", exc)
            return (
                "You are a hardware verification specification analyst. "
                "Given a specification document, extract all features and generate "
                "a structured verification plan in YAML format. "
                "Respond with a ```yaml block containing the vplan. "
                "Each feature must have: name, description, priority (mandatory/optional), "
                "and a list of coverage bins."
            )

    def _extract_yaml(self, response: str) -> str:
        """Extract the YAML vplan from the LLM response."""
        if not response or not isinstance(response, str):
            raise ValueError("LLM response must be a non-empty string")

        m = self._YAML_RE.search(response)
        if m:
            vplan = m.group(1).strip()
            if not vplan:
                raise ValueError("Extracted vplan must not be empty")
            return vplan

        return ""

    def _write_vplan(self, yaml_content: str) -> str:
        if not self.output_path:
            return ""
        target = Path(self.output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml_content, encoding="utf-8")
        logger.info("SpecAnalyst wrote vplan to %s", target)
        return str(target)

    @staticmethod
    def _follow_up() -> str:
        return (
            "Please provide the complete verification plan as a YAML code block. "
            "Use the format:\n"
            "```yaml\n"
            "features:\n"
            "  - name: feature_name\n"
            "    description: what it verifies\n"
            "    priority: mandatory\n"
            "    bins:\n"
            "      - bin_name\n"
            "```"
        )

    @staticmethod
    def _extract_summary(history: list[dict[str, str]]) -> str:
        """Extract a one-sentence summary from the last assistant message."""
        for msg in reversed(history):
            if msg["role"] == "assistant":
                content = msg["content"].strip()
                first_line = content.splitlines()[0] if content else ""
                return first_line[:200]
        return ""
