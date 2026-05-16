# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Unit tests for OrchestratorAgent (Phase 3b)."""

import asyncio
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from dv_agentic.agents.base import AgentConfig, BaseAgent
from dv_agentic.agents.orchestrator import OrchestratorAgent
from dv_agentic.tools.interface import CoverageTool, SimulatorTool
from dv_agentic.tools.models import CompileResult, CoverageDB, SimResult, SimTask
from dv_agentic.tools.services import SimControllerService

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
    simulator: SimulatorTool | None = None,
    coverage: CoverageTool | None = None,
) -> OrchestratorAgent:
    return OrchestratorAgent(
        config=AgentConfig(name="orchestrator", budget=budget),
        llm=_llm(responses),
        sub_agents=sub_agents or {},
        simulator=simulator,
        coverage=coverage,
    )


class _StubCoverage(CoverageTool):
    """Minimal CoverageTool for orchestrator integration tests."""

    def __init__(self, pct: float = 95.0) -> None:
        self._pct = pct

    def get_coverage(self, job_id: str) -> CoverageDB:
        return CoverageDB(path=f"cov_work/{job_id}", overall_percentage=self._pct)


class _StubSimulator(SimulatorTool):
    """Minimal SimulatorTool for orchestrator auto-chain integration tests."""

    def compile(self, _file_list: list[str], _top: str) -> CompileResult:
        return CompileResult(status="pass", output="ok")

    def run(self, test: str, seed: int, _debug: bool) -> SimResult:
        return SimResult(
            status="pass",
            job_id=f"{test}_{seed}",
            log_path=f"sim_{test}_{seed}.log",
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
        d = self.agent._parse_decision(_decision("run_bug_classifier", input_text="sim.log"))
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

        async def spy(
            system: str,
            messages: list[dict[str, str]],
            max_tokens: int = 1000,
            temperature: float | None = None,
        ) -> str:
            histories.append(list(messages))
            if len(histories) == 1:
                return _decision("run_bug_classifier", input_text="uvm_fatal in sim.log")
            return _decision("done")

        agent = OrchestratorAgent(
            config=AgentConfig(name="orch", budget=5),
            llm=MagicMock(complete=AsyncMock(side_effect=spy)),
            sub_agents={"bug_classifier": _sub_agent("type: TB_bug confidence: 0.9")},
        )
        asyncio.run(agent.run("regression failed"))

        # Second LLM call must contain the sub-agent result
        second_msgs = histories[1]
        last_user = next(m["content"] for m in reversed(second_msgs) if m["role"] == "user")
        assert "TB_bug" in last_user

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
        """Legacy sub_agents path: coverage_analyst mock still works if injected."""
        cov = _sub_agent("### Coverage Summary\nstatus : OK")
        agent = _make_agent(
            responses=[
                _decision("run_coverage_analyst", input_text="job_123"),
                _decision("done"),
            ],
            sub_agents={"coverage_analyst": cov},
        )
        result = asyncio.run(agent.run("task"))
        assert "run_coverage_analyst" in result

    def test_coverage_dispatch_uses_cov_svc_without_sub_agent(self) -> None:
        """CLI path: no coverage_analyst in sub_agents; uses CoverageAnalystService."""
        agent = _make_agent(
            responses=[
                _decision("run_coverage_analyst", input_text="job_123"),
                _decision("done"),
            ],
            sub_agents={},
            coverage=_StubCoverage(pct=95.0),
        )
        result = asyncio.run(agent.run("task"))
        assert "run_coverage_analyst" in result
        assert "job_123" in result
        assert "95.00%" in result

    def test_coverage_dispatch_skipped_when_no_adapter(self) -> None:
        agent = _make_agent(
            responses=[
                _decision("run_coverage_analyst", input_text="job_123"),
                _decision("done"),
            ],
            sub_agents={},
            coverage=None,
        )
        result = asyncio.run(agent.run("task"))
        assert "not configured" in result
        assert "done" in result

    def test_sub_agent_exception_does_not_crash_orchestrator(self) -> None:
        broken_cov = MagicMock(spec=CoverageTool)
        broken_cov.get_coverage.side_effect = RuntimeError("coverage tool exploded")
        agent = _make_agent(
            responses=[
                _decision("run_coverage_analyst", input_text="job_1"),
                _decision("done"),
            ],
            sub_agents={},
            coverage=broken_cov,
        )
        result = asyncio.run(agent.run("task"))
        assert "failed" in result
        assert "done" in result


# ---------------------------------------------------------------------------
# Workflow routing
# ---------------------------------------------------------------------------


class TestWorkflowRouting:
    def test_workflow_1_spec_to_sim(self) -> None:
        code_gen = _sub_agent("### Code Generation Report\nfinal_status : pass")
        agent = _make_agent(
            responses=[
                _decision("run_code_generator", workflow="1"),
                _decision("done", workflow="1"),
            ],
            sub_agents={"code_generator": code_gen},
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
# SimTask building (auto-chain input)
# ---------------------------------------------------------------------------


class TestBuildSimTask:
    def setup_method(self) -> None:
        self.agent = _make_agent(responses=[])

    def test_inline_json(self) -> None:
        task = self.agent._build_sim_task(
            '{"test": "axi_burst", "seed": 42, "top": "tb_top"}',
            "task_abc",
        )
        assert task.test == "axi_burst"
        assert task.seed == 42
        assert task.top == "tb_top"
        assert task.task_id == "task_abc"

    def test_fenced_json_block(self) -> None:
        inp = 'Generate seq\n```json\n{"test": "my_test", "seed": 7}\n```'
        task = self.agent._build_sim_task(inp, "tid")
        assert task.test == "my_test"
        assert task.seed == 7

    def test_heuristic_defaults(self) -> None:
        task = self.agent._build_sim_task("Fix the burst sequence", "orch_task")
        assert task.task_id == "orch_task"
        assert task.test == "uvm_test"
        assert task.seed == 1

    def test_heuristic_extracts_test_and_seed(self) -> None:
        inp = "Run test=foo_test with seed: 99"
        task = self.agent._build_sim_task(inp, "t1")
        assert task.test == "foo_test"
        assert task.seed == 99


# ---------------------------------------------------------------------------
# Auto-chain (sim + log after code_generator)
# ---------------------------------------------------------------------------


def _make_sim_svc(result: str) -> MagicMock:
    svc = MagicMock()
    svc.run = AsyncMock(return_value=result)
    return svc


def _make_log_svc(result: str) -> MagicMock:
    svc = MagicMock()
    svc.run = AsyncMock(return_value=result)
    return svc


class TestAutoChain:
    """Tests for the automatic code_generator → sim → log_analyzer chain."""

    def _make_agent_with_svc(
        self,
        responses: list[str],
        sim_result: str = "### Task Complete\nfinal_status : pass",
        log_result: str = "### Failure Summary\nfailure_subtype  : sim_general",
        sub_agents: dict[str, BaseAgent] | None = None,
        budget: int = 10,
    ) -> OrchestratorAgent:
        agent = OrchestratorAgent(
            config=AgentConfig(name="orchestrator", budget=budget),
            llm=_llm(responses),
            sub_agents=sub_agents or {"code_generator": _sub_agent("code output")},
        )
        agent._sim_svc = _make_sim_svc(sim_result)
        agent._log_svc = _make_log_svc(log_result)
        return agent

    def test_auto_chain_calls_sim_after_code_generator(self) -> None:
        agent = self._make_agent_with_svc(
            responses=[_decision("run_code_generator"), _decision("done")]
        )
        asyncio.run(agent.run("task"))
        sim_svc = cast(MagicMock, agent._sim_svc)
        sim_svc.run.assert_called_once()

    @patch.object(SimControllerService, "run", new_callable=AsyncMock)
    def test_auto_chain_passes_sim_task_not_codegen_output(self, mock_sim_run: AsyncMock) -> None:
        """Auto-chain must pass SimTask built from decision INPUT, not code gen text."""
        mock_sim_run.return_value = "### Task Complete\nfinal_status : pass"

        agent = OrchestratorAgent(
            config=AgentConfig(name="orch", budget=5),
            llm=_llm(
                [
                    _decision(
                        "run_code_generator",
                        input_text='{"test": "burst_test", "seed": 42}',
                    ),
                    _decision("done"),
                ]
            ),
            sub_agents={"code_generator": _sub_agent("### Code report\nunrelated markdown")},
            simulator=_StubSimulator(),
        )
        agent._log_svc = _make_log_svc("### Failure Summary\nfailure_subtype  : sim_general")

        asyncio.run(agent.run("task_id: chain_task"))

        mock_sim_run.assert_called_once()
        sim_arg = mock_sim_run.call_args[0][0]
        assert isinstance(sim_arg, SimTask)
        assert sim_arg.test == "burst_test"
        assert sim_arg.seed == 42
        assert sim_arg.task_id == "chain_task"

    def test_auto_chain_calls_log_after_sim(self) -> None:
        agent = self._make_agent_with_svc(
            responses=[_decision("run_code_generator"), _decision("done")]
        )
        asyncio.run(agent.run("task"))
        log_svc = cast(MagicMock, agent._log_svc)
        log_svc.run.assert_called_once()

    def test_auto_chain_steps_appear_in_result(self) -> None:
        agent = self._make_agent_with_svc(
            responses=[_decision("run_code_generator"), _decision("done")]
        )
        result = asyncio.run(agent.run("task"))
        assert "run_sim_controller[auto]" in result
        assert "run_log_analyzer[auto]" in result

    def test_auto_chain_skipped_when_sim_svc_is_none(self) -> None:
        agent = _make_agent(
            responses=[_decision("run_code_generator"), _decision("done")],
            sub_agents={"code_generator": _sub_agent("code output")},
        )
        assert agent._sim_svc is None
        result = asyncio.run(agent.run("task"))
        assert "run_sim_controller[auto]" not in result

    def test_auto_chain_log_result_fed_to_llm(self) -> None:
        histories: list[list[dict[str, str]]] = []
        log_content = "### Failure Summary\nfailure_subtype  : uvm_fatal_detail"

        async def spy(
            system: str,
            messages: list[dict[str, str]],
            max_tokens: int = 1000,
            temperature: float | None = None,
        ) -> str:
            histories.append(list(messages))
            if len(histories) == 1:
                return _decision("run_code_generator")
            return _decision("done")

        agent = OrchestratorAgent(
            config=AgentConfig(name="orch", budget=5),
            llm=MagicMock(complete=AsyncMock(side_effect=spy)),
            sub_agents={"code_generator": _sub_agent("code output")},
        )
        agent._sim_svc = _make_sim_svc("sim pass")
        agent._log_svc = _make_log_svc(log_content)

        asyncio.run(agent.run("task"))

        second_msgs = histories[1]
        last_user = next(m["content"] for m in reversed(second_msgs) if m["role"] == "user")
        assert "uvm_fatal_detail" in last_user

    def test_auto_chain_escalates_on_shifting_failure_subtype(self) -> None:
        log_results = [
            "### Failure Summary\nfailure_subtype  : missing_timescale",
            "### Failure Summary\nfailure_subtype  : unmatched_block",
        ]
        call_count = 0

        async def log_svc_run(_: str) -> str:
            nonlocal call_count
            result = log_results[call_count]
            call_count += 1
            return result

        log_svc = MagicMock()
        log_svc.run = log_svc_run

        agent = OrchestratorAgent(
            config=AgentConfig(name="orch", budget=10),
            llm=_llm([_decision("run_code_generator")] * 10),
            sub_agents={"code_generator": _sub_agent("code output")},
        )
        agent._sim_svc = _make_sim_svc("sim fail")
        agent._log_svc = log_svc

        result = asyncio.run(agent.run("task"))
        assert "escalated" in result
        assert "missing_timescale" in result or "unmatched_block" in result

    def test_auto_chain_no_escalation_when_subtype_stable(self) -> None:
        log_result = "### Failure Summary\nfailure_subtype  : missing_timescale"
        agent = self._make_agent_with_svc(
            responses=[
                _decision("run_code_generator"),
                _decision("run_code_generator"),
                _decision("done"),
            ],
            log_result=log_result,
        )
        result = asyncio.run(agent.run("task"))
        assert "done" in result


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
