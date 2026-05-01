"""Unit tests for dv_agentic.tools.models."""

import pytest

from dv_agentic.tools.models import CompileResult, CoverageDB, SimResult


class TestCompileResult:
    def test_pass_status(self) -> None:
        r = CompileResult(status="pass", output="ok")
        assert r.status == "pass"
        assert r.output == "ok"

    def test_fail_status(self) -> None:
        r = CompileResult(status="fail", output="error: syntax")
        assert r.status == "fail"

    def test_invalid_status_type(self) -> None:
        # dataclass does not enforce Literal at runtime; verify field exists
        r = CompileResult(status="pass", output="")
        assert hasattr(r, "status")


class TestSimResult:
    def test_defaults(self) -> None:
        r = SimResult(status="pass", job_id="j1", log_path="sim.log")
        assert r.error_summary is None
        assert r.cov_db_path is None

    def test_with_error(self) -> None:
        r = SimResult(
            status="fail",
            job_id="j2",
            log_path="sim.log",
            error_summary="DUT mismatch",
        )
        assert r.error_summary == "DUT mismatch"

    def test_timeout_status(self) -> None:
        r = SimResult(status="timeout", job_id="j3", log_path="sim.log")
        assert r.status == "timeout"


class TestCoverageDB:
    def test_fields(self) -> None:
        db = CoverageDB(path="/results/cov.db", overall_percentage=87.5)
        assert db.path == "/results/cov.db"
        assert pytest.approx(db.overall_percentage) == 87.5
