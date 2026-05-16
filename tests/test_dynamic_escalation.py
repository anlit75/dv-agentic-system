# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Tests for the dynamic escalation logic in OrchestratorAgent.

The Orchestrator tracks ``failure_subtype`` across consecutive auto-chain
passes (code_generator -> sim -> log_analyzer) and escalates immediately when
the subtype shifts (indicating a changing error space that iteration cannot
converge).

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
        f"### Debug Mode Required\nNO  -- log is sufficient\n\n"
        f"### Recommended Next Step\nCompile error -- pass to Code Generator for fix."
    )


def _make_sim_svc(result: str = "sim done") -> MagicMock:
    svc = MagicMock()
    svc.run = AsyncMock(return_value=result)
    return svc


def _make_log_svc(results: list[str]) -> MagicMock:
    svc = MagicMock()
    svc.run = AsyncMock(side_effect=results)
    return svc


def _make_agent_with_auto_chain(
    llm_responses: list[str],
    log_results: list[str],
    budget: int = 10,
) -> OrchestratorAgent:
    """Create an OrchestratorAgent with sim + log services injected for auto-chain."""
    agent = OrchestratorAgent(
        config=AgentConfig(name="orchestrator", budget=budget),
        llm=_llm(llm_responses),
        sub_agents={"code_generator": MagicMock(run=AsyncMock(return_value="code output"))},
    )
    agent._sim_svc = _make_sim_svc()
    agent._log_svc = _make_log_svc(log_results)
    return agent


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
# Dynamic escalation: shift detection (via auto-chain)
# ---------------------------------------------------------------------------


class TestDynamicEscalation:
    """Tests for dynamic escalation triggered by shifting failure subtypes.

    After Phase 2, escalation is driven by the auto-chain (code_generator ->
    sim -> log_analyzer) rather than explicit LLM-dispatched run_log_analyzer.
    """

    def test_escalates_on_subtype_shift(self) -> None:
        """Shifting failure subtype across two auto-chain runs -> immediate escalation."""
        agent = _make_agent_with_auto_chain(
            llm_responses=[
                _decision("run_code_generator"),
                _decision("run_code_generator"),
            ],
            log_results=[
                _log_result("compile_error", "missing_timescale"),
                _log_result("compile_error", "unmatched_block"),
            ],
        )
        result = asyncio.run(agent.run("regression failing"))
        assert "escalated" in result
        assert "YES" in result

    def test_escalation_reason_names_both_subtypes(self) -> None:
        agent = _make_agent_with_auto_chain(
            llm_responses=[
                _decision("run_code_generator"),
                _decision("run_code_generator"),
            ],
            log_results=[
                _log_result("compile_error", "missing_timescale"),
                _log_result("compile_error", "unmatched_block"),
            ],
        )
        result = asyncio.run(agent.run("regression failing"))
        assert "missing_timescale" in result
        assert "unmatched_block" in result

    def test_no_escalation_on_same_subtype(self) -> None:
        """Same subtype repeated -> continue iterating (done on third LLM call)."""
        agent = _make_agent_with_auto_chain(
            llm_responses=[
                _decision("run_code_generator"),
                _decision("run_code_generator"),
                _decision("done"),
            ],
            log_results=[
                _log_result("compile_error", "missing_timescale"),
                _log_result("compile_error", "missing_timescale"),
            ],
        )
        result = asyncio.run(agent.run("regression failing"))
        assert "done" in result
        assert "escalated" not in result

    def test_first_auto_chain_call_does_not_escalate(self) -> None:
        """First auto-chain call with no history -> never escalates."""
        agent = _make_agent_with_auto_chain(
            llm_responses=[
                _decision("run_code_generator"),
                _decision("done"),
            ],
            log_results=[
                _log_result("compile_error", "syntax_general"),
            ],
        )
        result = asyncio.run(agent.run("task"))
        assert "done" in result

    def test_escalation_step_recorded_before_return(self) -> None:
        """Auto-chain steps that led to the shift are in the steps list."""
        agent = _make_agent_with_auto_chain(
            llm_responses=[
                _decision("run_code_generator"),
                _decision("run_code_generator"),
            ],
            log_results=[
                _log_result("compile_error", "missing_timescale"),
                _log_result("compile_error", "unmatched_block"),
            ],
        )
        result = asyncio.run(agent.run("task"))
        assert "run_log_analyzer[auto]" in result

    def test_non_code_generator_actions_do_not_affect_history(self) -> None:
        """Only auto-chain log runs update the failure subtype history."""
        agent = OrchestratorAgent(
            config=AgentConfig(name="orch", budget=10),
            llm=_llm(
                [
                    _decision("run_coverage_analyst"),  # non-chain action
                    _decision("run_code_generator"),  # first auto-chain run
                    _decision("run_code_generator"),  # same subtype -> no escalation
                    _decision("done"),
                ]
            ),
            sub_agents={
                "coverage_analyst": MagicMock(run=AsyncMock(return_value="coverage ok")),
                "code_generator": MagicMock(run=AsyncMock(return_value="code output")),
            },
        )
        agent._sim_svc = _make_sim_svc()
        agent._log_svc = _make_log_svc(
            [
                _log_result("compile_error", "missing_timescale"),
                _log_result("compile_error", "missing_timescale"),
            ]
        )
        result = asyncio.run(agent.run("task"))
        assert "done" in result

    def test_shift_across_different_error_classes(self) -> None:
        """A shift from compile-subtype to sim-subtype also triggers escalation."""
        agent = _make_agent_with_auto_chain(
            llm_responses=[
                _decision("run_code_generator"),
                _decision("run_code_generator"),
            ],
            log_results=[
                _log_result("compile_error", "missing_timescale"),
                _log_result("uvm_error", "scoreboard_fail"),
            ],
        )
        result = asyncio.run(agent.run("task"))
        assert "escalated" in result
        assert "missing_timescale" in result
        assert "scoreboard_fail" in result

    def test_unknown_subtype_is_stable_with_itself(self) -> None:
        """'unknown' -> 'unknown' is treated as no shift."""
        agent = _make_agent_with_auto_chain(
            llm_responses=[
                _decision("run_code_generator"),
                _decision("run_code_generator"),
                _decision("done"),
            ],
            log_results=[
                _log_result("unknown", "unknown"),
                _log_result("unknown", "unknown"),
            ],
        )
        result = asyncio.run(agent.run("task"))
        assert "done" in result

    def test_budget_exhaustion_still_works_without_sim_svc(self) -> None:
        """Budget exhaustion path works when no sim service is configured."""
        agent = OrchestratorAgent(
            config=AgentConfig(name="orch", budget=2),
            llm=_llm([_decision("run_code_generator")] * 5),
            sub_agents={"code_generator": MagicMock(run=AsyncMock(side_effect=["pass"] * 5))},
        )
        assert agent._sim_svc is None
        result = asyncio.run(agent.run("task"))
        assert "budget_exhausted" in result
