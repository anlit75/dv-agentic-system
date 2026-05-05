"""Unit tests for Cadence adapters (Xcelium and IMC)."""

import subprocess
import unittest.mock as mock

from dv_agentic.tools.adapters.imc import IMCAdapter
from dv_agentic.tools.adapters.xcelium import XceliumAdapter


class TestXceliumAdapter:
    @mock.patch("subprocess.run")
    def test_compile_success(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = mock.Mock(returncode=0, stdout="Compile OK", stderr="")
        adapter = XceliumAdapter(xrun_path="xrun_test")
        result = adapter.compile(["test.sv"], top="top_test")

        assert result.status == "pass"
        assert "Compile OK" in result.output
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "xrun_test" in args
        assert "top_test" in args

    @mock.patch("subprocess.run")
    def test_compile_fail(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = mock.Mock(returncode=1, stdout="", stderr="Syntax error")
        adapter = XceliumAdapter()
        result = adapter.compile(["test.sv"], top="top")

        assert result.status == "fail"
        assert "Syntax error" in result.output

    @mock.patch("subprocess.run")
    def test_run_success(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = mock.Mock(returncode=0, stdout="Sim passed", stderr="")
        adapter = XceliumAdapter(collect_coverage=True)
        result = adapter.run("my_test", seed=42, debug=False)

        assert result.status == "pass"
        assert result.job_id == "my_test_42"
        assert result.cov_db_path == "cov_work/my_test_42"
        mock_run.assert_called_once()

    @mock.patch("subprocess.run")
    def test_run_timeout(self, mock_run: mock.Mock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["xrun"], timeout=3600)
        adapter = XceliumAdapter()
        result = adapter.run("test", seed=1, debug=False)

        assert result.status == "timeout"
        assert result.job_id == "test_1"

    def test_parse_errors(self) -> None:
        adapter = XceliumAdapter()
        output = "*E,ILLPRI: Illegal priority\n*E,SYNERR: Syntax error"
        errors = adapter._parse_errors(output)
        assert errors and "ILLPRI" in errors
        assert errors and "SYNERR" in errors

        uvm_output = "UVM_ERROR @ 100: uvm_test_top [TEST] Mismatch"
        errors = adapter._parse_errors(uvm_output)
        assert errors and "uvm_test_top [TEST] Mismatch" in errors

        assert adapter._parse_errors("clean output") is None


class TestIMCAdapter:
    def test_parse_total(self) -> None:
        adapter = IMCAdapter()
        assert adapter._parse_total("Cumulative coverage result: 87.65 %") == 87.65
        assert adapter._parse_total("Total coverage: 82.35%") == 82.35
        assert adapter._parse_total("Overall coverage: 79.10 %") == 79.10
        assert adapter._parse_total("no coverage info") is None

    @mock.patch("subprocess.run")
    def test_report_success(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = mock.Mock(returncode=0, stdout="Total coverage: 95.0%", stderr="")
        adapter = IMCAdapter()
        result = adapter.get_coverage("job_1")

        assert result.overall_percentage == 95.0
        assert "job_1" in result.path

    @mock.patch("subprocess.run")
    def test_report_fail(self, mock_run: mock.Mock) -> None:
        mock_run.side_effect = FileNotFoundError("imc not found")
        adapter = IMCAdapter()
        result = adapter.get_coverage("job_fail")

        assert result.overall_percentage == 0.0

    @mock.patch("subprocess.run")
    def test_merge(self, mock_run: mock.Mock) -> None:
        # Mocking both merge and subsequent report calls
        mock_run.side_effect = [
            mock.Mock(returncode=0, stdout="Merge OK", stderr=""),
            mock.Mock(returncode=0, stdout="Overall coverage: 80.0%", stderr=""),
        ]
        adapter = IMCAdapter()
        result = adapter.merge(["job1", "job2"], merged_dir="merged_test")

        assert result.overall_percentage == 80.0
        assert result.path == "merged_test"
        assert mock_run.call_count == 2

    @mock.patch("subprocess.run")
    def test_verisium_merge_skip(self, mock_run: mock.Mock) -> None:
        # Should skip verisium if .vsif doesn't exist
        adapter = IMCAdapter()
        with mock.patch("pathlib.Path.exists", return_value=False):
            adapter._verisium_merge("no_vsif_dir")
            mock_run.assert_not_called()

    @mock.patch("subprocess.run")
    def test_verisium_merge_run(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = mock.Mock(returncode=0, stdout="VSIF OK", stderr="")
        adapter = IMCAdapter()
        with mock.patch("pathlib.Path.exists", return_value=True):
            adapter._verisium_merge("has_vsif_dir")
            mock_run.assert_called_once()
