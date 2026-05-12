# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Unit tests for OrchestratorAgent (Phase 3b)."""

import asyncio
from typing import cast
from unittest.mock import AsyncMock, MagicMock

from dv_agentic.agents.base import AgentConfig, BaseAgent
from dv_agentic.agents.orchestrator import OrchestratorAgent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _llm(responses: list[str]) -> MagicMock:
    m = MagicMock()
    m.complete = AsyncMock(side_effect=responses)
    return m


def _sub_agent(result: str) -> MagicMock:
    a = MagicMock()
    a.run = AsyncMock(return_value=result)
    return a


def _decision(
    action: str, workflow: str = "1", input_text: str = "do it", human: str = "NO"
) -> str:
    return (
        f"### Decision\n"
        f"WORKFLOW: {workflow}\n"
        f"ACTION: {action}\n"
        f"INPUT: {input_text}\n\n"
        f"### Human Review Required\n"
        f"{human}\n"
    )


def _make_agent(
    responses: list[str],
    sub_agents: dict[str, BaseAgent] | None = None,
    budget: int = 10,
) -> OrchestratorAgent:
    return OrchestratorAgent(
        config=AgentConfig(name="orchestrator", budget=budget),
        llm=_llm(responses),
        sub_agents=sub_agents or {},
    )


# ---------------------------------------------------------------------------
# Decision parsing
# ---------------------------------------------------------------------------


class TestParseDecision:
    def setup_method(self) -> None:
        self.agent = _make_agent(responses=[])

    def test_workflow_extracted(self) -> None:
        d = self.agent._parse_decision(_decision("done", workflow="2"))
        assert d.workflow == "2"

    def test_action_extracted(self) -> None:
        d = self.agent._parse_decision(_decision("run_code_generator"))
        assert d.action == "run_code_generator"

    def test_input_extracted(self) -> None:
        d = self.agent._parse_decision(_decision("run_log_analyzer", input_text="sim.log"))
        assert d.input_text == "sim.log"

    def test_human_review_yes(self) -> None:
        d = self.agent._parse_decision(_decision("done", human="YES"))
        assert d.human_review is True

    def test_human_review_no(self) -> None:
        d = self.agent._parse_decision(_decision("done", human="NO"))
        assert d.human_review is False

    def test_unknown_action_defaults_to_escalate(self) -> None:
        d = self.agent._parse_decision("### Decision\nACTION: invalid_action\n")
        assert d.action == "escalate"

    def test_unknown_workflow(self) -> None:
        d = self.agent._parse_decision("### Decision\nACTION: done\n")
        assert d.workflow == "unknown"


# ---------------------------------------------------------------------------
# Terminal actions: done and escalate
# ---------------------------------------------------------------------------


class TestTerminalActions:
    def test_done_action_returns_done_status(self) -> None:
        agent = _make_agent([_decision("done")])
        result = asyncio.run(agent.run("Coverage is 73%"))
        assert "done" in result

    def test_escalate_action_returns_escalated_status(self) -> None:
        agent = _make_agent([_decision("escalate")])
        result = asyncio.run(agent.run("task"))
        assert "escalated" in result

    def test_human_review_yes_returns_escalated(self) -> None:
        agent = _make_agent([_decision("done", human="YES")])
        result = asyncio.run(agent.run("task"))
        assert "escalated" in result
        assert "YES" in result


# ---------------------------------------------------------------------------
# Sub-agent dispatch
# ---------------------------------------------------------------------------


class TestSubAgentDispatch:
    def test_dispatches_to_correct_sub_agent(self) -> None:
        code_gen = _sub_agent("### Code Generation Report\nfinal_status : pass")
        agent = _make_agent(
            responses=[
                _decision("run_code_generator", input_text="generate axi_seq"),
                _decision("done"),
            ],
            sub_agents={"code_generator": code_gen},
        )
        asyncio.run(agent.run("task"))
        code_gen.run.assert_called_once_with("generate axi_seq")

    def test_sub_agent_result_fed_back_to_llm(self) -> None:
        histories: list[list[dict[str, str]]] = []

        async def spy(system: str, messages: list[dict[str, str]], max_tokens: int = 1000) -> str:
            histories.append(list(messages))
            if len(histories) == 1:
                return _decision("run_log_analyzer", input_text="sim.log")
            return _decision("done")

        agent = OrchestratorAgent(
            config=AgentConfig(name="orch", budget=5),
            llm=MagicMock(complete=AsyncMock(side_effect=spy)),
            sub_agents={"log_analyzer": _sub_agent("error_class: uvm_fatal")},
        )
        asyncio.run(agent.run("regression failed"))

        # Second LLM call must contain the sub-agent result
        second_msgs = histories[1]
        last_user = next(m["content"] for m in reversed(second_msgs) if m["role"] == "user")
        assert "uvm_fatal" in last_user

    def test_missing_sub_agent_returns_informative_message(self) -> None:
        agent = _make_agent(
            responses=[
                _decision("run_code_generator"),
                _decision("done"),
            ],
            sub_agents={},  # code_generator not configured
        )
        result = asyncio.run(agent.run("task"))
        # Should still complete (not raise), and steps should record the skip
        assert "done" in result

    def test_step_recorded_after_dispatch(self) -> None:
        sim_ctrl = _sub_agent("final_status : pass")
        agent = _make_agent(
            responses=[
                _decision("run_sim_controller", input_text="my_test"),
                _decision("done"),
            ],
            sub_agents={"sim_controller": sim_ctrl},
        )
        result = asyncio.run(agent.run("task"))
        assert "run_sim_controller" in result

    def test_sub_agent_exception_does_not_crash_orchestrator(self) -> None:
        broken = MagicMock()
        broken.run = AsyncMock(side_effect=RuntimeError("sim exploded"))
        agent = _make_agent(
            responses=[
                _decision("run_sim_controller"),
                _decision("done"),
            ],
            sub_agents={"sim_controller": broken},
        )
        result = asyncio.run(agent.run("task"))
        assert "done" in result


# ---------------------------------------------------------------------------
# Workflow routing
# ---------------------------------------------------------------------------


class TestWorkflowRouting:
    def test_workflow_1_spec_to_sim(self) -> None:
        code_gen = _sub_agent("pass")
        sim_ctrl = _sub_agent("pass")
        agent = _make_agent(
            responses=[
                _decision("run_code_generator", workflow="1"),
                _decision("run_sim_controller", workflow="1"),
                _decision("done", workflow="1"),
            ],
            sub_agents={"code_generator": code_gen, "sim_controller": sim_ctrl},
        )
        result = asyncio.run(agent.run("develop verification for AXI feature"))
        assert "workflow     : 1" in result

    def test_workflow_reported_in_output(self) -> None:
        agent = _make_agent([_decision("done", workflow="3")])
        result = asyncio.run(agent.run("coverage is 73%"))
        assert "workflow     : 3" in result


# ---------------------------------------------------------------------------
# Budget exhaustion
# ---------------------------------------------------------------------------


class TestBudgetExhaustion:
    def test_budget_exhausted_status(self) -> None:
        # Always returns dispatch — never done
        agent = _make_agent(
            responses=[_decision("run_code_generator")] * 20,
            sub_agents={"code_generator": _sub_agent("pass")},
            budget=3,
        )
        result = asyncio.run(agent.run("task"))
        assert "budget_exhausted" in result

    def test_exactly_budget_llm_calls(self) -> None:
        agent = _make_agent(
            responses=[_decision("run_code_generator")] * 20,
            sub_agents={"code_generator": _sub_agent("pass")},
            budget=4,
        )
        asyncio.run(agent.run("task"))
        assert cast(MagicMock, agent.llm.complete).call_count == 4

    def test_human_review_set_on_budget_exhausted(self) -> None:
        agent = _make_agent(
            responses=[_decision("run_code_generator")] * 20,
            sub_agents={"code_generator": _sub_agent("pass")},
            budget=2,
        )
        result = asyncio.run(agent.run("task"))
        assert "YES" in result


# ---------------------------------------------------------------------------
# Task ID extraction
# ---------------------------------------------------------------------------


class TestTaskIdExtraction:
    def test_extracts_task_id_from_input(self) -> None:
        agent = _make_agent([])
        assert agent._extract_task_id("task_id: my_task_001") == "my_task_001"

    def test_fallback_task_id(self) -> None:
        agent = _make_agent([])
        assert agent._extract_task_id("no id here") == "orchestrator_task"
