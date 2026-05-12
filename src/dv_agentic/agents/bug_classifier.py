# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Bug classification agent.

Classifies a simulation failure as a testbench bug (TB_BUG) or an RTL
bug (RTL_BUG), and assigns a confidence score.  When confidence is below
the project threshold the agent requests human review rather than guessing.

Workflow
--------
1. Build a prompt from the failure summary (and optional spec/code context).
2. Call the LLM; parse BUG_TYPE, CONFIDENCE, and EVIDENCE from the response.
3. If confidence >= threshold → done.
4. If confidence < threshold → feed the open questions back and retry.
5. If budget exhausted → mark ``requires_human_review = True``.
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


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ClassificationResult:
    """Structured output from :class:`BugClassifierAgent`."""

    bug_type: str  # "TB_BUG" | "RTL_BUG" | "UNKNOWN"
    confidence: float  # 0.0 - 1.0
    evidence: list[str]  # bullet points extracted from LLM response
    summary: str
    requires_human_review: bool
    human_review_reason: str = ""
    iterations: int = 1

    def to_str(self) -> str:
        lines = [
            "### Bug Classification",
            f"bug_type   : {self.bug_type}",
            f"confidence : {self.confidence:.2f}",
            f"iterations : {self.iterations}",
            f"human_review: {'YES' if self.requires_human_review else 'NO'}",
        ]
        if self.human_review_reason:
            lines.append(f"review_reason: {self.human_review_reason}")
        if self.evidence:
            lines.append("EVIDENCE   :")
            for e in self.evidence:
                lines.append(f"  - {e.strip()}")
        if self.summary:
            lines += ["", "### Summary", self.summary]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class BugClassifierAgent(BaseAgent):
    """Classifies a simulation failure as a TB bug or RTL bug.

    Args:
        config: Agent configuration (``budget`` caps LLM call count).
        llm: LLM client to use for classification.
        confidence_threshold: Minimum confidence to accept a classification
            without flagging for human review.  Defaults to 0.75.
        project_config: Optional context for PromptLoader enrichment.
        session: Optional session state injected into the system prompt.
        prompts_dir: Directory containing ``bug_classifier.md``.
    """

    _BUG_TYPE_RE = re.compile(r"BUG_TYPE\s*:\s*(TB_BUG|RTL_BUG|UNKNOWN)", re.IGNORECASE)
    _CONFIDENCE_RE = re.compile(r"CONFIDENCE\s*:\s*([0-9]*\.?[0-9]+)", re.IGNORECASE)
    _EVIDENCE_RE = re.compile(
        r"EVIDENCE\s*:(.*?)(?=\n###|\n[A-Z_]+\s*:|\Z)", re.DOTALL | re.IGNORECASE
    )

    def __init__(
        self,
        config: AgentConfig,
        llm: BaseLLMClient,
        confidence_threshold: float = 0.75,
        project_config: ProjectContext | None = None,
        session: SessionState | None = None,
        prompts_dir: str | Path | None = None,
    ) -> None:
        super().__init__(config)
        self.llm = llm
        self.confidence_threshold = confidence_threshold
        self.project_config = project_config
        self.session = session
        self.prompts_dir = prompts_dir

    # ------------------------------------------------------------------
    # BaseAgent ABC
    # ------------------------------------------------------------------

    async def run(self, task_input: str) -> str:
        """Classify the failure described in *task_input*.

        Args:
            task_input: Failure summary text (e.g. ``FailureSummary.to_str()``),
                optionally followed by spec excerpts or relevant code snippets.

        Returns:
            A formatted :class:`ClassificationResult` string.
        """
        if not task_input or not isinstance(task_input, str):
            raise ValueError("task_input must be a non-empty string")

        system_prompt = self._load_system_prompt()

        if not system_prompt:
            raise RuntimeError("System prompt must not be empty")
        if self.iteration != 0:
            raise RuntimeError(f"Agent must start at iteration 0 (current: {self.iteration})")

        history: list[dict[str, str]] = [{"role": "user", "content": task_input}]
        last: ClassificationResult | None = None

        while await self.step():
            response = await self.llm.complete(system_prompt, history, max_tokens=2000)
            history.append({"role": "assistant", "content": response})

            last = self._parse_response(response, self.iteration)
            logger.info(
                "BugClassifier iter=%d type=%s confidence=%.2f",
                self.iteration,
                last.bug_type,
                last.confidence,
            )

            if last.confidence >= self.confidence_threshold and last.bug_type != "UNKNOWN":
                return last.to_str()

            # Low confidence → ask for more evidence
            history.append({"role": "user", "content": self._follow_up(last)})

        # Budget exhausted — return best guess with human review flag
        if last is None:
            last = ClassificationResult(
                bug_type="UNKNOWN",
                confidence=0.0,
                evidence=[],
                summary="Budget exhausted before any LLM response.",
                requires_human_review=True,
                human_review_reason="No LLM response received.",
                iterations=self.iteration,
            )
        else:
            last.requires_human_review = True
            last.human_review_reason = (
                f"Confidence {last.confidence:.2f} below threshold "
                f"{self.confidence_threshold:.2f} after {self.iteration} iterations."
            )
        return last.to_str()

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
            return loader.load("bug_classifier")
        except (FileNotFoundError, RuntimeError) as exc:
            logger.warning("PromptLoader unavailable (%s); using fallback.", exc)
            return (
                "You are a hardware verification bug classification specialist. "
                "Given a simulation failure summary, classify the root cause as "
                "TB_BUG (testbench / verification code issue) or RTL_BUG (design bug). "
                "Always respond with:\n"
                "BUG_TYPE: TB_BUG | RTL_BUG | UNKNOWN\n"
                "CONFIDENCE: 0.0-1.0\n"
                "EVIDENCE:\n- bullet point evidence\n"
                "### Summary\n"
                "One-paragraph explanation."
            )

    def _parse_response(self, response: str, iteration: int) -> ClassificationResult:
        if not response or not isinstance(response, str):
            raise ValueError("LLM response must be a non-empty string")

        bug_type = "UNKNOWN"
        m = self._BUG_TYPE_RE.search(response)
        if m:
            bug_type = m.group(1).upper()

        confidence = 0.0
        m = self._CONFIDENCE_RE.search(response)
        if m:
            raw = float(m.group(1))
            # Accept both 0-1 and 0-100 scales
            confidence = raw / 100.0 if raw > 1.0 else raw

        evidence: list[str] = []
        m = self._EVIDENCE_RE.search(response)
        if m:
            block = m.group(1)
            evidence = [
                line.lstrip("-• ").strip()
                for line in block.splitlines()
                if line.strip().lstrip("-• ")
            ]

        # Extract summary (text after last ### Summary or whole response as fallback)
        summary = ""
        if "### Summary" in response:
            summary = response.split("### Summary", 1)[1].strip()
        elif "### summary" in response.lower():
            summary = re.split(r"###\s+summary", response, flags=re.IGNORECASE)[1].strip()

        requires_review = confidence < self.confidence_threshold or bug_type == "UNKNOWN"
        return ClassificationResult(
            bug_type=bug_type,
            confidence=confidence,
            evidence=evidence,
            summary=summary,
            requires_human_review=requires_review,
            iterations=iteration,
        )

    @staticmethod
    def _follow_up(result: ClassificationResult) -> str:
        return (
            f"Your classification confidence was {result.confidence:.2f}, "
            f"which is below the required threshold. "
            "Please review the failure evidence more carefully and provide:\n"
            "1. Additional evidence from the log that supports or contradicts each bug type.\n"
            "2. A revised BUG_TYPE and CONFIDENCE.\n"
            "3. Specific RTL signals or testbench components that would confirm the root cause."
        )
