# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Unit tests for SimControllerAgent (Phase 3a)."""

import asyncio
import json
from collections.abc import Generator, Iterator
from unittest.mock import MagicMock, patch

import pytest

from dv_agentic.agents.base import AgentConfig
from dv_agentic.agents.sim_controller import SimControllerAgent
from dv_agentic.tools.interface import SimulatorTool
from dv_agentic.tools.models import CompileResult, SimResult, SimTask

# ---------------------------------------------------------------------------
# Stub adapters
# ---------------------------------------------------------------------------


class _StubSim(SimulatorTool):
    """Minimal SimulatorTool stub."""

    def __init__(self, compile_status: str = "pass", run_statuses: list[str] | None = None) -> None:
        self._compile_status = compile_status
        self._run_statuses: Iterator[str] = iter(run_statuses or ["pass"])

    def compile(self, _file_list: list[str], _top: str) -> CompileResult:
        return CompileResult(status=self._compile_status, output="stub output")  # type: ignore[arg-type]

    def run(self, test: str, seed: int, _debug: bool) -> SimResult:
        status = next(self._run_statuses, "fail")
        return SimResult(
            status=status,  # type: ignore[arg-type]
            job_id=f"{test}_{seed}",
            log_path=f"sim_{test}_{seed}.log",
            error_summary="stub error" if status != "pass" else None,
        )


@pytest.fixture()
def task() -> SimTask:
    return SimTask(task_id="test_task_001", test="my_test", seed=42)


@pytest.fixture()
def _no_git() -> Generator[MagicMock, None, None]:
    """Patch _git so tests don't require a real git repo."""
    with patch.object(SimControllerAgent, "_git") as m:
        yield m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCompileFail:
    def test_returns_compile_fail_status(self, task: SimTask, _no_git: MagicMock) -> None:
        agent = SimControllerAgent(
            config=AgentConfig(name="sim_ctrl", budget=5),
            simulator=_StubSim(compile_status="fail"),
        )
        result = asyncio.run(agent.run(task))
        assert "compile_fail" in result

    def test_does_not_run_simulation_after_compile_fail(
        self, task: SimTask, _no_git: MagicMock
    ) -> None:
        sim = _StubSim(compile_status="fail")
        sim.run = MagicMock()  # type: ignore[method-assign]
        agent = SimControllerAgent(
            config=AgentConfig(name="sim_ctrl", budget=5),
            simulator=sim,
        )
        asyncio.run(agent.run(task))
        sim.run.assert_not_called()


class TestSimPass:
    def test_pass_on_first_run(self, task: SimTask, _no_git: MagicMock) -> None:
        agent = SimControllerAgent(
            config=AgentConfig(name="sim_ctrl", budget=5),
            simulator=_StubSim(run_statuses=["pass"]),
        )
        result = asyncio.run(agent.run(task))
        assert "pass" in result
        assert "ready_for_pr : yes" in result

    def test_pass_after_two_fails(self, task: SimTask, _no_git: MagicMock) -> None:
        agent = SimControllerAgent(
            config=AgentConfig(name="sim_ctrl", budget=5),
            simulator=_StubSim(run_statuses=["fail", "fail", "pass"]),
        )
        result = asyncio.run(agent.run(task))
        assert "pass" in result
        assert "runs_total   : 3" in result


class TestBudgetExhaustion:
    def test_escalated_when_budget_runs_out(self, task: SimTask, _no_git: MagicMock) -> None:
        agent = SimControllerAgent(
            config=AgentConfig(name="sim_ctrl", budget=3),
            simulator=_StubSim(run_statuses=["fail", "fail", "fail", "fail"]),
        )
        result = asyncio.run(agent.run(task))
        assert "escalated" in result
        assert "ready_for_pr : no" in result

    def test_exactly_budget_runs_executed(self, task: SimTask, _no_git: MagicMock) -> None:
        sim = _StubSim(run_statuses=["fail"] * 10)
        run_mock = MagicMock(side_effect=sim.run)
        sim.run = run_mock  # type: ignore[method-assign]
        agent = SimControllerAgent(
            config=AgentConfig(name="sim_ctrl", budget=3),
            simulator=sim,
        )
        asyncio.run(agent.run(task))
        assert run_mock.call_count == 3


class TestGitCalls:
    def test_branch_created_with_task_id(self, task: SimTask) -> None:
        with patch.object(SimControllerAgent, "_git") as git_mock:
            agent = SimControllerAgent(
                config=AgentConfig(name="sim_ctrl", budget=1),
                simulator=_StubSim(run_statuses=["pass"]),
            )
            asyncio.run(agent.run(task))

        # checkout -b ai-task/{task_id} must appear somewhere in the calls
        all_calls = [c.args for c in git_mock.call_args_list]
        assert any(args == ("checkout", "-B", f"ai-task/{task.task_id}") for args in all_calls)

    def test_commit_called_after_run(self, task: SimTask) -> None:
        with patch.object(SimControllerAgent, "_git") as git_mock:
            agent = SimControllerAgent(
                config=AgentConfig(name="sim_ctrl", budget=1),
                simulator=_StubSim(run_statuses=["pass"]),
            )
            asyncio.run(agent.run(task))

        all_args = [c.args for c in git_mock.call_args_list]
        commit_calls = [a for a in all_args if a[0] == "commit"]
        assert len(commit_calls) >= 1
        assert task.task_id in commit_calls[0][2]  # commit -m "...task_id..."


class TestTaskParsing:
    def test_accepts_simtask_directly(self, _no_git: MagicMock) -> None:
        task = SimTask(task_id="t1", test="foo", seed=1)
        agent = SimControllerAgent(
            config=AgentConfig(name="sim_ctrl", budget=1),
            simulator=_StubSim(run_statuses=["pass"]),
        )
        result = asyncio.run(agent.run(task))
        assert "t1" in result

    def test_accepts_json_string(self, _no_git: MagicMock) -> None:
        task_json = json.dumps({"task_id": "t2", "test": "bar", "seed": 7})
        agent = SimControllerAgent(
            config=AgentConfig(name="sim_ctrl", budget=1),
            simulator=_StubSim(run_statuses=["pass"]),
        )
        result = asyncio.run(agent.run(task_json))
        assert "t2" in result
