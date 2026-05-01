"""Unit tests for the new adapter implementations."""

import os
import unittest.mock as mock
from pathlib import Path
from typing import Any

import pytest

from dv_agentic.tools.adapters.ghdl_cocotb import GHDLCocotbAdapter
from dv_agentic.tools.adapters.icarus import IcarusAdapter
from dv_agentic.tools.adapters.pyuvm import PyuvmCoverageAdapter
from dv_agentic.tools.adapters.verilator import VerilatorAdapter


class TestIcarusAdapter:
    @mock.patch("dv_agentic.tools.adapters.cocotb_base.get_runner")
    def test_compile(self, mock_get_runner: Any) -> None:
        mock_runner = mock.Mock()
        mock_get_runner.return_value = mock_runner

        adapter = IcarusAdapter(hdl_toplevel="top")
        result = adapter.compile(["file.v"], top="new_top")

        assert result.status == "pass"
        mock_runner.build.assert_called_once_with(
            verilog_sources=["file.v"], hdl_toplevel="new_top", always=True
        )

    @mock.patch("dv_agentic.tools.adapters.cocotb_base.get_runner")
    def test_run(self, mock_get_runner: Any) -> None:
        mock_runner = mock.Mock()
        mock_get_runner.return_value = mock_runner

        adapter = IcarusAdapter(hdl_toplevel="top")
        result = adapter.run("my_test.Case", seed=123, debug=False)

        assert result.status == "pass"
        assert result.job_id == "my_test.Case_123"
        mock_runner.test.assert_called_once()

    @mock.patch("dv_agentic.tools.adapters.cocotb_base.get_runner")
    def test_compile_fail(self, mock_get_runner: Any) -> None:
        mock_runner = mock.Mock()
        mock_runner.build.side_effect = Exception("Build error")
        mock_get_runner.return_value = mock_runner

        adapter = IcarusAdapter(hdl_toplevel="top")
        result = adapter.compile(["file.v"], top="top")

        assert result.status == "fail"
        assert "Build error" in result.output

    @mock.patch("dv_agentic.tools.adapters.cocotb_base.get_runner")
    def test_run_fail(self, mock_get_runner: Any) -> None:
        mock_runner = mock.Mock()
        mock_runner.test.side_effect = Exception("Sim error")
        mock_get_runner.return_value = mock_runner

        adapter = IcarusAdapter(hdl_toplevel="top")
        result = adapter.run("test", seed=1, debug=False)

        assert result.status == "fail"
        assert result.error_summary is not None
        assert "Sim error" in result.error_summary

    @mock.patch("dv_agentic.tools.adapters.cocotb_base.get_runner", None)
    def test_get_runner_missing(self) -> None:
        adapter = IcarusAdapter()
        with pytest.raises(ImportError, match=r"cocotb.runner is not available"):
            adapter._get_runner()


class TestVerilatorAdapter:
    @mock.patch("dv_agentic.tools.adapters.cocotb_base.get_runner")
    def test_compile(self, mock_get_runner: Any) -> None:
        mock_runner = mock.Mock()
        mock_get_runner.return_value = mock_runner

        adapter = VerilatorAdapter(hdl_toplevel="top")
        result = adapter.compile(["file.v"], top="new_top")

        assert result.status == "pass"
        mock_runner.build.assert_called_once_with(
            verilog_sources=["file.v"], hdl_toplevel="new_top", always=True
        )


class TestGHDLCocotbAdapter:
    @mock.patch("dv_agentic.tools.adapters.cocotb_base.get_runner")
    def test_compile(self, mock_get_runner: Any) -> None:
        mock_runner = mock.Mock()
        mock_get_runner.return_value = mock_runner

        adapter = GHDLCocotbAdapter(hdl_toplevel="top")
        result = adapter.compile(["file.vhd"], top="new_top")

        assert result.status == "pass"
        mock_runner.build.assert_called_once_with(
            vhdl_sources=["file.vhd"], hdl_toplevel="new_top", hdl_toplevel_lang="vhdl", always=True
        )

    @mock.patch("dv_agentic.tools.adapters.cocotb_base.get_runner")
    def test_run(self, mock_get_runner: Any) -> None:
        mock_runner = mock.Mock()
        mock_get_runner.return_value = mock_runner

        adapter = GHDLCocotbAdapter(hdl_toplevel="top")
        result = adapter.run("my_vhdl_test.Case", seed=456, debug=True)

        assert result.status == "pass"
        mock_runner.test.assert_called_once_with(
            hdl_toplevel="top",
            hdl_toplevel_lang="vhdl",
            test_module="my_vhdl_test",
            testcase="Case",
            waves=True,
            extra_env=mock.ANY,
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
