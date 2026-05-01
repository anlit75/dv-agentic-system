"""Unit tests for the new adapter implementations."""

import importlib.util
import os
import unittest.mock as mock
from pathlib import Path
from typing import Any

import pytest

from dv_agentic.tools.adapters.pyuvm import PyuvmCoverageAdapter

# cocotb.runner is Linux-only
cocotb_runner_available = importlib.util.find_spec("cocotb.runner") is not None
skip_no_cocotb = pytest.mark.skipif(
    not cocotb_runner_available, reason="cocotb.runner not available"
)

if cocotb_runner_available:
    from dv_agentic.tools.adapters.icarus import IcarusAdapter
    from dv_agentic.tools.adapters.verilator import VerilatorAdapter
else:
    # Placeholders for type checking or if tests are not skipped
    IcarusAdapter = None  # type: ignore
    VerilatorAdapter = None  # type: ignore


@skip_no_cocotb
class TestIcarusAdapter:
    @mock.patch("dv_agentic.tools.adapters.icarus.get_runner")
    def test_compile(self, mock_get_runner: Any) -> None:
        mock_runner = mock.Mock()
        mock_get_runner.return_value = mock_runner

        adapter = IcarusAdapter(hdl_toplevel="top")
        result = adapter.compile(["file.v"], top="new_top")

        assert result.status == "pass"
        mock_runner.build.assert_called_once_with(
            verilog_sources=["file.v"], hdl_toplevel="new_top", always=True
        )

    @mock.patch("dv_agentic.tools.adapters.icarus.get_runner")
    def test_run(self, mock_get_runner: Any) -> None:
        mock_runner = mock.Mock()
        mock_get_runner.return_value = mock_runner

        adapter = IcarusAdapter(hdl_toplevel="top")
        result = adapter.run("my_test.Case", seed=123, debug=False)

        assert result.status == "pass"
        assert result.job_id == "my_test.Case_123"
        mock_runner.test.assert_called_once()


@skip_no_cocotb
class TestVerilatorAdapter:
    @mock.patch("dv_agentic.tools.adapters.verilator.get_runner")
    def test_compile(self, mock_get_runner: Any) -> None:
        mock_runner = mock.Mock()
        mock_get_runner.return_value = mock_runner

        adapter = VerilatorAdapter(hdl_toplevel="top")
        result = adapter.compile(["file.v"], top="new_top")

        assert result.status == "pass"
        mock_runner.build.assert_called_once_with(
            verilog_sources=["file.v"], hdl_toplevel="new_top", always=True
        )


class TestPyuvmCoverageAdapter:
    def test_parse_total(self) -> None:
        adapter = PyuvmCoverageAdapter()
        output = "Some log...\nFunctional Coverage: 85.5%\nMore logs..."
        assert adapter._parse_total(output) == 85.5

        output = "Total Coverage: 90.00 %"
        assert adapter._parse_total(output) == 90.0

        output = "UVMCoverage: 77.2 %"
        assert adapter._parse_total(output) == 77.2

    def test_get_coverage_job_specific(self, tmp_path: Path) -> None:
        # Create a job-specific log file
        log_file = tmp_path / "sim_job1.log"
        log_file.write_text("Functional Coverage: 92.5%")

        # We need to change the current working directory to tmp_path
        # so that the adapter finds the file.
        old_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            adapter = PyuvmCoverageAdapter()
            result = adapter.get_coverage("job1")

            assert result.overall_percentage == 92.5
            assert "sim_job1.log" in result.path
        finally:
            os.chdir(old_cwd)

    def test_get_coverage_fallback(self, tmp_path: Path) -> None:
        # Create a default report file
        report_file = tmp_path / "coverage.txt"
        report_file.write_text("Total Coverage: 45.0%")

        old_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            adapter = PyuvmCoverageAdapter(default_report_path="coverage.txt")
            result = adapter.get_coverage("any_job")

            assert result.overall_percentage == 45.0
            assert result.path == "coverage.txt"
        finally:
            os.chdir(old_cwd)
