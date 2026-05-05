"""Orchestrator agent.

Routes tasks to the appropriate workflow and coordinates sub-agent handoffs.

Workflow model
--------------
The LLM acts as the decision maker; Python executes the decisions.

Each turn:
  1. LLM receives the accumulated history and returns a structured decision.
  2. Python parses: WORKFLOW, ACTION, INPUT, HUMAN_REVIEW.
  3. Python dispatches the action to the appropriate sub-agent.
  4. Sub-agent result is appended to history as a new user message.
  5. Repeat until ACTION is ``done`` / ``escalate``, or budget is exhausted.

Valid actions
-------------
``run_code_generator``, ``run_sim_controller``, ``run_log_analyzer``,
``run_coverage_analyst``, ``run_bug_classifier``, ``run_spec_analyst``,
``run_reporter``, ``done``, ``escalate``

Expected LLM response format::

    ### Decision
    WORKFLOW: 1
    ACTION: run_code_generator
    INPUT: Generate a targeted sequence for axi_burst bin

    ### Human Review Required
    NO
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from ..prompts.context import ProjectContext, SessionState
from ..prompts.loader import PromptLoader
from ..tools.llm.interface import BaseLLMClient
from .base import AgentConfig, BaseAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class _Decision:
    workflow: str  # "1" | "2" | "3" | "unknown"
    action: str  # one of VALID_ACTIONS
    input_text: str  # text to pass to the sub-agent
    human_review: bool
    human_review_reason: str = ""


@dataclass
class OrchestratorResult:
    """Structured output from :class:`OrchestratorAgent`.

    Attributes:
        task_id: Unique identifier for the orchestrated task.
        workflow: The detected workflow category ("1", "2", or "3").
        final_status: Termination state ("done", "escalated", or "budget_exhausted").
        steps: List of summary strings for each sub-agent dispatch.
        requires_human_review: True if the process stopped for manual intervention.
        human_review_reason: Explanation for why review is required.
    """

    task_id: str
    workflow: str
    final_status: str  # "done" | "escalated" | "budget_exhausted"
    steps: list[str] = field(default_factory=list)
    requires_human_review: bool = False
    human_review_reason: str = ""

    def to_str(self) -> str:
        lines = [
            "### Orchestrator Result",
            f"task_id      : {self.task_id}",
            f"workflow     : {self.workflow}",
            f"final_status : {self.final_status}",
            f"steps_taken  : {len(self.steps)}",
            f"human_review : {'YES' if self.requires_human_review else 'NO'}",
        ]
        if self.human_review_reason:
            lines.append(f"review_reason: {self.human_review_reason}")
        if self.steps:
            lines.append("steps        :")
            for s in self.steps:
                lines.append(f"  - {s}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class OrchestratorAgent(BaseAgent):
    """Routes tasks and coordinates sub-agents across Workflows 1, 2, and 3.

    Each budget unit corresponds to one LLM routing call + one sub-agent
    dispatch.  Sub-agents consume their own budgets independently.

    Args:
        config: Agent configuration.  ``budget`` caps orchestration cycles.
        llm: LLM client used for routing decisions.
        sub_agents: Mapping from agent key to agent instance, e.g.
            ``{"code_generator": CodeGeneratorAgent(...), ...}``.
            Missing keys are handled gracefully.
        project_config: Optional context for PromptLoader enrichment.
        session: Optional session state.
        prompts_dir: Directory containing ``orchestrator.md``.
    """

    VALID_ACTIONS: frozenset[str] = frozenset(
        {
            "run_code_generator",
            "run_sim_controller",
            "run_log_analyzer",
            "run_coverage_analyst",
            "run_bug_classifier",
            "run_spec_analyst",
            "run_reporter",
            "done",
            "escalate",
        }
    )

    _AGENT_KEY: ClassVar[dict[str, str]] = {
        "run_code_generator": "code_generator",
        "run_sim_controller": "sim_controller",
        "run_log_analyzer": "log_analyzer",
        "run_coverage_analyst": "coverage_analyst",
        "run_bug_classifier": "bug_classifier",
        "run_spec_analyst": "spec_analyst",
        "run_reporter": "reporter",
    }

    _WORKFLOW_RE = re.compile(r"WORKFLOW\s*[:\-]?\s*([123])", re.IGNORECASE)
    _ACTION_RE = re.compile(r"ACTION\s*:\s*(" + "|".join(VALID_ACTIONS) + r")", re.IGNORECASE)
    _INPUT_RE = re.compile(r"INPUT\s*:(.*?)(?=\n[A-Z_]+\s*:|\n###|\Z)", re.DOTALL)
    _HUMAN_RE = re.compile(
        r"Human\s+Review\s+Required\s*\n(YES|NO)(.*?)(?=\n###|\Z)",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(
        self,
        config: AgentConfig,
        llm: BaseLLMClient,
        sub_agents: dict[str, BaseAgent] | None = None,
        project_config: ProjectContext | None = None,
        session: SessionState | None = None,
        prompts_dir: str | Path | None = None,
    ) -> None:
        super().__init__(config)
        self.llm = llm
        self.sub_agents: dict[str, BaseAgent] = sub_agents or {}
        self.project_config = project_config
        self.session = session
        self.prompts_dir = prompts_dir

    # ------------------------------------------------------------------
    # BaseAgent ABC
    # ------------------------------------------------------------------

    async def run(self, task_input: str) -> str:
        """Execute the full agentic verification flow.

        Args:
            task_input: Natural language description of the verification task.

        Returns:
            A human-readable final summary report.
        """
        if not task_input or not isinstance(task_input, str):
            raise ValueError("task_input must be a non-empty string")

        task_id = self._extract_task_id(task_input)
        system_prompt = self._load_system_prompt()

        if not system_prompt:
            raise RuntimeError("System prompt must not be empty")
        if self.iteration != 0:
            raise RuntimeError(f"Agent must start at iteration 0 (current: {self.iteration})")
        history: list[dict[str, str]] = [{"role": "user", "content": task_input}]

        workflow = "unknown"
        steps: list[str] = []

        while await self.step():
            response = await self.llm.complete(system_prompt, history, max_tokens=1000)
            history.append({"role": "assistant", "content": response})

            decision = self._parse_decision(response)
            if decision.workflow != "unknown":
                workflow = decision.workflow

            logger.info(
                "Orchestrator iter=%d action=%s workflow=%s human_review=%s",
                self.iteration,
                decision.action,
                workflow,
                decision.human_review,
            )

            if decision.human_review:
                return OrchestratorResult(
                    task_id=task_id,
                    workflow=workflow,
                    final_status="escalated",
                    steps=steps,
                    requires_human_review=True,
                    human_review_reason=decision.human_review_reason,
                ).to_str()

            if decision.action == "done":
                return OrchestratorResult(
                    task_id=task_id,
                    workflow=workflow,
                    final_status="done",
                    steps=steps,
                ).to_str()

            if decision.action == "escalate":
                return OrchestratorResult(
                    task_id=task_id,
                    workflow=workflow,
                    final_status="escalated",
                    steps=steps,
                    requires_human_review=True,
                    human_review_reason="LLM requested escalation.",
                ).to_str()

            # Dispatch to sub-agent
            sub_result = await self._dispatch(decision.action, decision.input_text)
            step_label = f"{decision.action}: {sub_result[:120].strip()}"
            steps.append(step_label)

            # Feed result back to LLM for the next routing decision
            history.append(
                {
                    "role": "user",
                    "content": (
                        f"Result of {decision.action}:\n{sub_result}\n\n"
                        "Based on this result, what is the next action?"
                    ),
                }
            )

        return OrchestratorResult(
            task_id=task_id,
            workflow=workflow,
            final_status="budget_exhausted",
            steps=steps,
            requires_human_review=True,
            human_review_reason=f"Budget exhausted after {self.iteration} iterations.",
        ).to_str()

    # ------------------------------------------------------------------
    # Private — dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, action: str, input_text: str) -> str:
        """Call the sub-agent associated with *action*.

        Args:
            action: One of ``VALID_ACTIONS`` (excluding ``done``/``escalate``).
            input_text: Input forwarded to the sub-agent's ``run()`` method.

        Returns:
            The sub-agent's output string, or an informative error message
            if the agent is not configured.
        """
        if not action or not isinstance(action, str):
            raise ValueError("action must be a non-empty string")
        if not isinstance(input_text, str):
            raise TypeError("input_text must be a string")

        if action not in self.VALID_ACTIONS:
            raise ValueError(f"Action '{action}' is not valid")

        key = self._AGENT_KEY.get(action)
        if not key:
            return f"No sub-agent mapping for action '{action}'."

        agent = self.sub_agents.get(key)
        if not agent:
            return f"Sub-agent '{key}' is not configured in this orchestrator. Skipping."

        logger.info("Orchestrator dispatching to '%s'", key)
        try:
            return await agent.run(input_text)
        except Exception as exc:
            # Catch all sub-agent exceptions to prevent the orchestrator from crashing.
            # Errors are logged and returned as a string for LLM feedback.
            logger.exception("Sub-agent '%s' raised an exception", key)
            return f"Sub-agent '{key}' failed: {exc}"

    # ------------------------------------------------------------------
    # Private — parsing
    # ------------------------------------------------------------------

    def _parse_decision(self, response: str) -> _Decision:
        if not response or not isinstance(response, str):
            raise ValueError("LLM response must be a non-empty string")

        workflow = "unknown"
        m = self._WORKFLOW_RE.search(response)
        if m:
            workflow = m.group(1)

        action = "escalate"  # safe default
        m = self._ACTION_RE.search(response)
        if m:
            action = m.group(1).lower()

        input_text = ""
        m = self._INPUT_RE.search(response)
        if m:
            input_text = m.group(1).strip()

        human_review = False
        human_review_reason = ""
        m = self._HUMAN_RE.search(response)
        if m:
            human_review = m.group(1).upper() == "YES"
            human_review_reason = m.group(2).strip() if m.group(2) else ""

        decision = _Decision(
            workflow=workflow,
            action=action,
            input_text=input_text,
            human_review=human_review,
            human_review_reason=human_review_reason,
        )

        # Rule 5: Post-condition assertions
        assert decision.workflow in ("1", "2", "3", "unknown")
        assert decision.action in self.VALID_ACTIONS
        return decision

    def _load_system_prompt(self) -> str:
        try:
            loader = PromptLoader(
                prompts_dir=self.prompts_dir,
                project_config=self.project_config,
                session=self.session,
            )
            return loader.load("orchestrator")
        except (FileNotFoundError, RuntimeError) as exc:
            logger.warning("PromptLoader unavailable (%s); using fallback.", exc)
            return (
                "You are an orchestration agent for hardware verification. "
                "Given a task, determine the workflow (1, 2, or 3) and the next action.\n"
                "Always respond in this format:\n"
                "### Decision\n"
                "WORKFLOW: 1\n"
                "ACTION: run_code_generator\n"
                "INPUT: <what to pass to the agent>\n\n"
                "### Human Review Required\n"
                "NO\n"
            )

    @staticmethod
    def _extract_task_id(text: str) -> str:
        m = re.search(r"task[_\s]id\s*[:\s]+([a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
        return m.group(1) if m else "orchestrator_task"
