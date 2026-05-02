"""Unit tests for CoverageAnalystAgent (Phase 3a)."""

import asyncio
from unittest.mock import MagicMock

from dv_agentic.agents.base import AgentConfig
from dv_agentic.agents.coverage_analyst import CoverageAnalystAgent
from dv_agentic.tools.models import CoverageDB


def _make_agent(pct: float, threshold: float = 90.0) -> CoverageAnalystAgent:
    cov_mock = MagicMock()
    cov_mock.get_coverage.return_value = CoverageDB(
        path=f"cov_work/job_{pct:.0f}", overall_percentage=pct
    )
    return CoverageAnalystAgent(
        config=AgentConfig(name="cov_analyst"),
        coverage=cov_mock,
        threshold=threshold,
    )


class TestCoverageSummary:
    def test_above_threshold_ok(self) -> None:
        agent = _make_agent(pct=95.0, threshold=90.0)
        summary = agent.get_summary("job_95")
        assert summary.below_threshold is False
        assert summary.overall_pct == 95.0

    def test_below_threshold_flagged(self) -> None:
        agent = _make_agent(pct=73.0, threshold=90.0)
        summary = agent.get_summary("job_73")
        assert summary.below_threshold is True
        assert abs(summary.threshold_pct - summary.overall_pct - 17.0) < 0.01

    def test_exactly_at_threshold_is_ok(self) -> None:
        agent = _make_agent(pct=90.0, threshold=90.0)
        summary = agent.get_summary("job_90")
        # 90.0 < 90.0 is False → OK
        assert summary.below_threshold is False

    def test_zero_coverage(self) -> None:
        agent = _make_agent(pct=0.0, threshold=90.0)
        summary = agent.get_summary("job_0")
        assert summary.below_threshold is True

    def test_summary_fields(self) -> None:
        agent = _make_agent(pct=80.0)
        summary = agent.get_summary("myjob")
        assert summary.job_id == "myjob"
        assert "cov_work" in summary.db_path


class TestOutputFormat:
    def test_ok_output_contains_ok(self) -> None:
        agent = _make_agent(pct=92.0)
        out = agent.get_summary("j").to_str()
        assert "OK" in out
        assert "BELOW" not in out

    def test_below_output_mentions_phase3b(self) -> None:
        agent = _make_agent(pct=60.0)
        out = agent.get_summary("j").to_str()
        assert "BELOW THRESHOLD" in out
        assert "Phase 3b" in out

    def test_gap_shown_in_output(self) -> None:
        agent = _make_agent(pct=75.0, threshold=90.0)
        out = agent.get_summary("j").to_str()
        assert "15.00%" in out  # gap = 90 - 75


class TestCustomThreshold:
    def test_lower_threshold(self) -> None:
        agent = _make_agent(pct=70.0, threshold=60.0)
        summary = agent.get_summary("j")
        assert summary.below_threshold is False

    def test_higher_threshold(self) -> None:
        agent = _make_agent(pct=95.0, threshold=99.0)
        summary = agent.get_summary("j")
        assert summary.below_threshold is True


class TestAsyncRun:
    def test_run_returns_string(self) -> None:
        agent = _make_agent(pct=85.0)
        result = asyncio.run(agent.run("job_85"))
        assert isinstance(result, str)
        assert "85.00%" in result
