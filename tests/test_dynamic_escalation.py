"""Tests for the dynamic escalation logic added to OrchestratorAgent.

The Orchestrator now tracks ``failure_subtype`` across consecutive
``run_log_analyzer`` dispatches and escalates immediately when the subtype
shifts (indicating a changing error space that iteration cannot converge).

These tests are kept in a separate file to leave the original
test_orchestrator.py untouched (surgical-change principle).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from dv_agentic.agents.base import AgentConfig
from dv_agentic.agents.orchestrator import OrchestratorAgent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _llm(responses: list[str]) -> MagicMock:
    m = MagicMock()
    m.complete = AsyncMock(side_effect=responses)
    return m


def _decision(action: str, workflow: str = "2", input_text: str = "sim.log") -> str:
    return (
        f"### Decision\n"
        f"WORKFLOW: {workflow}\n"
        f"ACTION: {action}\n"
        f"INPUT: {input_text}\n\n"
        f"### Human Review Required\nNO\n"
    )


def _log_result(error_class: str, subtype: str) -> str:
    return (
        f"### Failure Summary\n"
        f"error_class      : {error_class}\n"
        f"failure_subtype  : {subtype}\n"
        f"first_occurrence : line 5\n"
        f"message          : some error\n\n"
        f"### Context Window\n(none)\n\n"
        f"### Debug Mode Required\nNO  — log is sufficient\n\n"
        f"### Recommended Next Step\nCompile error — pass to Code Generator for fix."
    )


def _sub_agent(results: list[str]) -> MagicMock:
    a = MagicMock()
    a.run = AsyncMock(side_effect=results)
    return a


def _make_agent(
    llm_responses: list[str],
    log_analyzer_results: list[str],
    budget: int = 10,
) -> OrchestratorAgent:
    return OrchestratorAgent(
        config=AgentConfig(name="orchestrator", budget=budget),
        llm=_llm(llm_responses),
        sub_agents={"log_analyzer": _sub_agent(log_analyzer_results)},
    )


# ---------------------------------------------------------------------------
# _extract_failure_subtype helper
# ---------------------------------------------------------------------------


class TestExtractFailureSubtype:
    def setup_method(self) -> None:
        self.agent = OrchestratorAgent(
            config=AgentConfig(name="orch"),
            llm=MagicMock(),
        )

    def test_extracts_known_subtype(self) -> None:
        out = _log_result("compile_error", "missing_timescale")
        assert self.agent._extract_failure_subtype(out) == "missing_timescale"

    def test_extracts_sim_general(self) -> None:
        out = _log_result("uvm_error", "sim_general")
        assert self.agent._extract_failure_subtype(out) == "sim_general"

    def test_falls_back_to_unknown_when_field_absent(self) -> None:
        out = "### Failure Summary\nerror_class      : compile_error\nsome other text"
        assert self.agent._extract_failure_subtype(out) == "unknown"

    def test_unknown_from_empty_string(self) -> None:
        assert self.agent._extract_failure_subtype("") == "unknown"


# ---------------------------------------------------------------------------
# Dynamic escalation: shift detection
# ---------------------------------------------------------------------------


class TestDynamicEscalation:
    def test_escalates_on_subtype_shift(self) -> None:
        """Different subtype on 2nd log_analyzer call → immediate escalation."""
        agent = _make_agent(
            llm_responses=[
                _decision("run_log_analyzer"),
                _decision("run_log_analyzer"),  # second call would trigger shift
            ],
            log_analyzer_results=[
                _log_result("compile_error", "missing_timescale"),
                _log_result("compile_error", "unmatched_block"),
            ],
        )
        result = asyncio.run(agent.run("regression failing"))
        assert "escalated" in result
        assert "YES" in result  # human_review

    def test_escalation_reason_names_both_subtypes(self) -> None:
        agent = _make_agent(
            llm_responses=[
                _decision("run_log_analyzer"),
                _decision("run_log_analyzer"),
            ],
            log_analyzer_results=[
                _log_result("compile_error", "missing_timescale"),
                _log_result("compile_error", "unmatched_block"),
            ],
        )
        result = asyncio.run(agent.run("regression failing"))
        assert "missing_timescale" in result
        assert "unmatched_block" in result

    def test_no_escalation_on_same_subtype(self) -> None:
        """Same subtype repeated → continue iterating (done on third LLM call)."""
        agent = _make_agent(
            llm_responses=[
                _decision("run_log_analyzer"),
                _decision("run_log_analyzer"),
                _decision("done"),
            ],
            log_analyzer_results=[
                _log_result("compile_error", "missing_timescale"),
                _log_result("compile_error", "missing_timescale"),
            ],
        )
        result = asyncio.run(agent.run("regression failing"))
        assert "done" in result
        assert "escalated" not in result

    def test_first_log_analyzer_call_does_not_escalate(self) -> None:
        """Single log_analyzer call with no previous history → never escalates."""
        agent = _make_agent(
            llm_responses=[
                _decision("run_log_analyzer"),
                _decision("done"),
            ],
            log_analyzer_results=[
                _log_result("compile_error", "syntax_general"),
            ],
        )
        result = asyncio.run(agent.run("task"))
        assert "done" in result

    def test_escalation_step_recorded_before_return(self) -> None:
        """The log_analyzer step that caused the shift is in the steps list."""
        agent = _make_agent(
            llm_responses=[
                _decision("run_log_analyzer"),
                _decision("run_log_analyzer"),
            ],
            log_analyzer_results=[
                _log_result("compile_error", "missing_timescale"),
                _log_result("compile_error", "unmatched_block"),
            ],
        )
        result = asyncio.run(agent.run("task"))
        # The step from the second call should appear in the output
        assert "run_log_analyzer" in result

    def test_non_log_analyzer_actions_do_not_affect_history(self) -> None:
        """Only run_log_analyzer calls update the failure subtype history."""
        code_gen = MagicMock()
        code_gen.run = AsyncMock(return_value="### Code Generation Report\npass")
        agent = OrchestratorAgent(
            config=AgentConfig(name="orch", budget=10),
            llm=_llm(
                [
                    _decision("run_code_generator"),  # non-log action
                    _decision("run_log_analyzer"),  # first log call
                    _decision("run_log_analyzer"),  # same subtype → no escalation
                    _decision("done"),
                ]
            ),
            sub_agents={
                "code_generator": code_gen,
                "log_analyzer": _sub_agent(
                    [
                        _log_result("compile_error", "missing_timescale"),
                        _log_result("compile_error", "missing_timescale"),
                    ]
                ),
            },
        )
        result = asyncio.run(agent.run("task"))
        assert "done" in result

    def test_shift_across_different_error_classes(self) -> None:
        """A shift from compile-subtype to sim-subtype also triggers escalation."""
        agent = _make_agent(
            llm_responses=[
                _decision("run_log_analyzer"),
                _decision("run_log_analyzer"),
            ],
            log_analyzer_results=[
                _log_result("compile_error", "missing_timescale"),
                _log_result("uvm_error", "scoreboard_fail"),
            ],
        )
        result = asyncio.run(agent.run("task"))
        assert "escalated" in result
        assert "missing_timescale" in result
        assert "scoreboard_fail" in result

    def test_unknown_subtype_is_stable_with_itself(self) -> None:
        """'unknown' → 'unknown' is treated as no shift."""
        agent = _make_agent(
            llm_responses=[
                _decision("run_log_analyzer"),
                _decision("run_log_analyzer"),
                _decision("done"),
            ],
            log_analyzer_results=[
                _log_result("unknown", "unknown"),
                _log_result("unknown", "unknown"),
            ],
        )
        result = asyncio.run(agent.run("task"))
        assert "done" in result

    def test_budget_exhaustion_still_works_without_log_analyzer(self) -> None:
        """Budget exhaustion path is unaffected when log_analyzer is never called."""
        agent = OrchestratorAgent(
            config=AgentConfig(name="orch", budget=2),
            llm=_llm([_decision("run_code_generator")] * 5),
            sub_agents={"code_generator": _sub_agent(["pass"] * 5)},
        )
        result = asyncio.run(agent.run("task"))
        assert "budget_exhausted" in result
