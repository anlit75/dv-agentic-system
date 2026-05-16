# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

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

Auto-chain
----------
After ``run_code_generator`` completes, the Orchestrator automatically
invokes :class:`~dv_agentic.tools.services.SimControllerService` and then
:class:`~dv_agentic.tools.services.LogAnalyzerService` in sequence without
an additional LLM routing call.  The log-analysis result is fed back to the
LLM as the effective output of the code-generator step.

Dynamic escalation
------------------
During the auto-chain, the Orchestrator tracks the ``failure_subtype`` field
in each :class:`~dv_agentic.tools.services.FailureSummary`.  If the subtype
*shifts* between consecutive iterations (e.g. ``missing_timescale`` →
``unmatched_block``) the Orchestrator escalates immediately.  A shifting
error space indicates that each fix is revealing a new root-cause rather than
converging, so additional iterations are unlikely to produce a passing
simulation and token budget is better spent on human diagnosis.

Valid actions
-------------
``run_code_generator``, ``run_coverage_analyst``, ``run_bug_classifier``,
``run_spec_analyst``, ``run_reporter``, ``done``, ``escalate``

Expected LLM response format::

    ### Decision
    WORKFLOW: 1
    ACTION: run_code_generator
    INPUT: Generate a targeted sequence for axi_burst bin

    ### Human Review Required
    NO
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from ..wiki.manager import WikiConfig

from ..prompts.context import ProjectContext, SessionState
from ..prompts.prompt_loader import PromptLoader
from ..tools.llm.interface import BaseLLMClient
from ..tools.models import SimTask
from ..tools.services import (
    CoverageAnalystService,
    LogAnalyzerService,
    SimControllerService,
)
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
    After ``run_code_generator``, :class:`~dv_agentic.tools.services.SimControllerService`
    and :class:`~dv_agentic.tools.services.LogAnalyzerService` are invoked
    automatically (no extra LLM routing call required).

    Args:
        config: Agent configuration.  ``budget`` caps orchestration cycles.
        llm: LLM client used for routing decisions.
        sub_agents: Mapping from agent key to agent instance.  Expected keys:
            ``code_generator``, ``coverage_analyst``, ``bug_classifier``,
            ``spec_analyst``, ``reporter``.  Missing keys are handled gracefully.
        project_config: Optional context for PromptLoader enrichment.
        session: Optional session state.
        prompts_dir: Directory containing ``orchestrator.md``.
        wiki_config: Optional wiki configuration.
        simulator: Optional :class:`~dv_agentic.tools.interface.SimulatorTool`
            adapter.  When provided, enables the auto-chain after
            ``run_code_generator``.
        coverage: Optional :class:`~dv_agentic.tools.interface.CoverageTool`
            adapter.  When provided, enables
            :class:`~dv_agentic.tools.services.CoverageAnalystService`.
        coverage_threshold: Minimum acceptable coverage percentage (default 90.0).
        sim_max_runs: Maximum sim iterations per auto-chain call.  Falls back
            to ``config.budget`` when ``None``.
    """

    VALID_ACTIONS: frozenset[str] = frozenset(
        {
            "run_code_generator",
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
        "run_bug_classifier": "bug_classifier",
        "run_spec_analyst": "spec_analyst",
        "run_reporter": "reporter",
    }

    _SIMTASK_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n(\{.*?\})\s*```", re.DOTALL)

    _WORKFLOW_RE = re.compile(r"WORKFLOW\s*[:\-]?\s*([123])", re.IGNORECASE)
    _ACTION_RE = re.compile(r"ACTION\s*:\s*(" + "|".join(VALID_ACTIONS) + r")", re.IGNORECASE)
    _INPUT_RE = re.compile(r"INPUT\s*:(.*?)(?=\n[A-Z_]+\s*:|\n###|\Z)", re.DOTALL)
    _HUMAN_RE = re.compile(
        r"Human\s+Review\s+Required\s*\n(YES|NO)(.*?)(?=\n###|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    _FAILURE_SUBTYPE_RE = re.compile(r"failure_subtype\s+:\s+(\S+)", re.IGNORECASE)

    def __init__(
        self,
        config: AgentConfig,
        llm: BaseLLMClient,
        sub_agents: dict[str, BaseAgent] | None = None,
        project_config: ProjectContext | None = None,
        session: SessionState | None = None,
        prompts_dir: str | Path | None = None,
        wiki_config: "WikiConfig | None" = None,
        simulator: object | None = None,
        coverage: object | None = None,
        coverage_threshold: float = 90.0,
        sim_max_runs: int | None = None,
    ) -> None:
        super().__init__(config)
        self.llm = llm
        self.sub_agents: dict[str, BaseAgent] = sub_agents or {}
        self.project_config = project_config
        self.session = session
        self.prompts_dir = prompts_dir
        self.wiki_config = wiki_config

        from ..tools.interface import CoverageTool, SimulatorTool

        self._sim_svc = (
            SimControllerService(simulator) if isinstance(simulator, SimulatorTool) else None
        )
        self._log_svc = LogAnalyzerService(wiki_config=wiki_config)
        self._cov_svc = (
            CoverageAnalystService(coverage, threshold=coverage_threshold, wiki_config=wiki_config)
            if isinstance(coverage, CoverageTool)
            else None
        )
        self._sim_max_runs = sim_max_runs
        self._temperature: float = 0.0  # loaded from frontmatter in _load_system_prompt()

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

        # Fast sanity check: ensure wiki index matches disk before task execution.
        if self.wiki_config and self.wiki_config.enabled and self.wiki_config.lint_on_startup:
            try:
                from ..wiki.lint import WikiLintService

                lint_report = WikiLintService(self.wiki_config).run(depth="quick")
                if lint_report.human_review_required:
                    logger.warning("Wiki Quick Lint found issues: %s", lint_report.to_str())
            except Exception as exc:
                logger.debug("Orchestrator: Wiki quick lint failed: %s", exc)

        history: list[dict[str, str]] = [{"role": "user", "content": task_input}]

        workflow = "unknown"
        steps: list[str] = []
        # Dynamic escalation: track failure_subtype across consecutive auto-chain runs.
        # Populated by the auto-chain after each code_generator → sim → log_analyzer pass.
        # Not reset between iterations so we can detect shifts in failure kind.
        _failure_subtype_history: list[str] = []

        while await self.step():
            response = await self.llm.complete(
                system_prompt, history, max_tokens=1000, temperature=self._temperature
            )
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

            # ----------------------------------------------------------------
            # Auto-chain: code_generator → sim → log_analyzer
            # These two steps are deterministic after code generation; routing
            # them through the LLM would waste a routing call on a known sequence.
            # ----------------------------------------------------------------
            if decision.action == "run_code_generator" and self._sim_svc is not None:
                max_runs = self._sim_max_runs or self.config.budget
                sim_task = self._build_sim_task(decision.input_text, task_id)
                try:
                    sim_result = await self._sim_svc.run(sim_task, max_runs=max_runs)
                except Exception as exc:
                    logger.exception("SimControllerService failed during auto-chain")
                    sim_result = f"SimControllerService failed: {exc}"
                steps.append(f"run_sim_controller[auto]: {sim_result[:120].strip()}")

                log_result = await self._log_svc.run(sim_result)
                steps.append(f"run_log_analyzer[auto]: {log_result[:120].strip()}")

                # Dynamic escalation: detect shifting failure subtypes across iterations.
                current_subtype = self._extract_failure_subtype(log_result)
                if _failure_subtype_history and _failure_subtype_history[-1] != current_subtype:
                    prev = _failure_subtype_history[-1]
                    reason = (
                        f"Failure type shifted from '{prev}' to '{current_subtype}' "
                        f"across iterations — iterating is unlikely to converge. "
                        f"Manual diagnosis required."
                    )
                    logger.warning(
                        "Orchestrator: failure subtype shifted %s → %s at iter=%d; escalating",
                        prev,
                        current_subtype,
                        self.iteration,
                    )
                    return OrchestratorResult(
                        task_id=task_id,
                        workflow=workflow,
                        final_status="escalated",
                        steps=steps,
                        requires_human_review=True,
                        human_review_reason=reason,
                    ).to_str()
                _failure_subtype_history.append(current_subtype)

                # Feed log analysis result to LLM for the next routing decision.
                sub_result = log_result

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
                Valid dispatchable actions: ``run_code_generator``,
                ``run_coverage_analyst``, ``run_bug_classifier``,
                ``run_spec_analyst``, ``run_reporter``.
                Note: ``run_sim_controller`` and ``run_log_analyzer`` are no
                longer valid actions — they are invoked automatically via the
                auto-chain after ``run_code_generator``.
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

        if action == "run_coverage_analyst":
            if self._cov_svc is None:
                return "CoverageAnalystService is not configured (no coverage adapter). Skipping."
            logger.info("Orchestrator dispatching to CoverageAnalystService")
            try:
                return await self._cov_svc.run(input_text)
            except Exception as exc:
                logger.exception("CoverageAnalystService raised an exception")
                return f"CoverageAnalystService failed: {exc}"

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

    def _build_sim_task(self, input_text: str, task_id: str) -> SimTask:
        """Build a :class:`SimTask` from the orchestrator INPUT for ``run_code_generator``.

        The code generator's output is not used here — only the routing INPUT,
        which may be plain text, inline JSON, or a fenced JSON block.

        Args:
            input_text: ``INPUT`` field from the LLM decision (passed to code generator).
            task_id: Task identifier for branch naming and reporting.

        Returns:
            A :class:`SimTask` with parsed or default field values.
        """

        def _from_dict(data: dict[str, Any]) -> SimTask:
            return SimTask(
                task_id=str(data.get("task_id", task_id)),
                test=str(data.get("test", "uvm_test")),
                seed=int(data.get("seed", 1)),
                file_list=list(data.get("file_list", [])),
                top=str(data.get("top", "top")),
                debug=bool(data.get("debug", False)),
            )

        text = input_text.strip()
        if text.startswith("{"):
            try:
                return _from_dict(json.loads(text))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                logger.debug("Inline SimTask JSON parse failed: %s", exc)

        block = self._SIMTASK_JSON_BLOCK_RE.search(text)
        if block:
            try:
                return _from_dict(json.loads(block.group(1)))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                logger.debug("Fenced SimTask JSON parse failed: %s", exc)

        test_m = re.search(r"(?:test|UVM_TESTNAME)\s*[=:]\s*(\S+)", text, re.IGNORECASE)
        seed_m = re.search(r"seed\s*[=:]\s*(\d+)", text, re.IGNORECASE)
        return SimTask(
            task_id=task_id,
            test=test_m.group(1) if test_m else "uvm_test",
            seed=int(seed_m.group(1)) if seed_m else 1,
            file_list=[],
            top="top",
            debug=False,
        )

    def _extract_failure_subtype(self, log_analyzer_output: str) -> str:
        """Parse the ``failure_subtype`` field from a :class:`FailureSummary` string.

        Args:
            log_analyzer_output: The string returned by ``LogAnalyzerService.run()``.

        Returns:
            The subtype token (e.g. ``"missing_timescale"``), or ``"unknown"``
            if the field is absent (e.g. when the sub-agent itself errored).
        """
        m = self._FAILURE_SUBTYPE_RE.search(log_analyzer_output)
        return m.group(1) if m else "unknown"

    def _load_system_prompt(self) -> str:
        try:
            loader = PromptLoader(
                prompts_dir=self.prompts_dir,
                project_config=self.project_config,
                session=self.session,
            )
            self._temperature = loader.load_temperature("orchestrator")
            return loader.load("orchestrator")
        except (FileNotFoundError, RuntimeError) as exc:
            logger.warning("PromptLoader unavailable (%s); using fallback.", exc)
            self._temperature = 0.0
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
