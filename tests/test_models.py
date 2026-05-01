"""Unit tests for dv_agentic.tools.models."""

import pytest

from dv_agentic.tools.models import CompileResult, CoverageDB, SimResult


class TestCompileResult:
    @pytest.mark.parametrize("status", ["pass", "fail"])
    def test_status(self, status: str) -> None:
        r = CompileResult(status=status, output="some output")  # type: ignore[arg-type]
        assert r.status == status

    def test_output_preserved(self) -> None:
        r = CompileResult(status="pass", output="build ok")
        assert r.output == "build ok"


class TestSimResult:
    def test_optional_fields_default_to_none(self) -> None:
        r = SimResult(status="pass", job_id="j1", log_path="sim.log")
        assert r.error_summary is None
        assert r.cov_db_path is None

    def test_error_summary_set(self) -> None:
        r = SimResult(
            status="fail",
            job_id="j2",
            log_path="sim.log",
            error_summary="DUT mismatch",
        )
        assert r.error_summary == "DUT mismatch"

    def test_cov_db_path_set(self) -> None:
        r = SimResult(
            status="pass",
            job_id="j3",
            log_path="sim.log",
            cov_db_path="/results/cov.db",
        )
        assert r.cov_db_path == "/results/cov.db"

    def test_timeout_status(self) -> None:
        r = SimResult(status="timeout", job_id="j4", log_path="sim.log")
        assert r.status == "timeout"

    def test_job_id_and_log_path_preserved(self) -> None:
        r = SimResult(status="pass", job_id="abc_123", log_path="/logs/run.log")
        assert r.job_id == "abc_123"
        assert r.log_path == "/logs/run.log"


class TestCoverageDB:
    @pytest.mark.parametrize("pct", [0.0, 50.0, 87.5, 100.0])
    def test_overall_percentage(self, pct: float) -> None:
        db = CoverageDB(path="/results/cov.db", overall_percentage=pct)
        assert pytest.approx(db.overall_percentage) == pct

    def test_path_preserved(self) -> None:
        db = CoverageDB(path="/results/cov.db", overall_percentage=42.0)
        assert db.path == "/results/cov.db"
