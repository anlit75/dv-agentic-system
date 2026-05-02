"""Unit tests for LogAnalyzerAgent (Phase 3a)."""

from pathlib import Path

import pytest

from dv_agentic.agents.base import AgentConfig
from dv_agentic.agents.log_analyzer import LogAnalyzerAgent


@pytest.fixture()
def agent() -> LogAnalyzerAgent:
    return LogAnalyzerAgent(config=AgentConfig(name="log_analyzer"))


class TestErrorClassification:
    def test_uvm_fatal(self, agent: LogAnalyzerAgent) -> None:
        log = "some preamble\nUVM_FATAL @ 100ns [my_monitor] unexpected value\nend"
        s = agent.analyze(log)
        assert s.error_class == "uvm_fatal"
        assert "line 2" in s.first_occurrence
        assert s.debug_required is False

    def test_xcelium_compile_error(self, agent: LogAnalyzerAgent) -> None:
        log = "*E,NOIPRT (tb/env.sv,12): port not found\nExiting"
        s = agent.analyze(log)
        assert s.error_class == "compile_error"
        assert s.debug_required is False  # compile errors never need debug re-run

    def test_ghdl_compile_error(self, agent: LogAnalyzerAgent) -> None:
        log = "ghdl: error: unexpected token ';'"
        s = agent.analyze(log)
        assert s.error_class == "compile_error"

    def test_uvm_error_single(self, agent: LogAnalyzerAgent) -> None:
        log = "Sim running...\nUVM_ERROR @ 50ns: mismatch\nDone."
        s = agent.analyze(log)
        assert s.error_class == "uvm_error"
        assert s.debug_required is False  # only one UVM_ERROR

    def test_uvm_error_multiple_needs_debug(self, agent: LogAnalyzerAgent) -> None:
        log = "UVM_ERROR @ 10ns: first\nUVM_ERROR @ 20ns: second"
        s = agent.analyze(log)
        assert s.error_class == "uvm_error"
        assert s.debug_required is True

    def test_scoreboard_mismatch(self, agent: LogAnalyzerAgent) -> None:
        log = "INFO: transaction sent\nScoreboard mismatch: got 0xAA expected 0xBB"
        s = agent.analyze(log)
        assert s.error_class == "scoreboard_mismatch"

    def test_cocotb_assertion_error(self, agent: LogAnalyzerAgent) -> None:
        log = "Traceback (most recent call last):\n  File 'test.py'\nAssertionError: expected True"
        s = agent.analyze(log)
        assert s.error_class == "cocotb_error"

    def test_sim_timeout(self, agent: LogAnalyzerAgent) -> None:
        log = "Running test...\nSimTimeoutError: test exceeded 10000ns"
        s = agent.analyze(log)
        assert s.error_class == "timeout"

    def test_unknown_no_pattern_match(self, agent: LogAnalyzerAgent) -> None:
        log = "Everything looks fine.\nSimulation complete."
        s = agent.analyze(log)
        assert s.error_class == "unknown"
        assert s.debug_required is True

    def test_message_trimmed_to_120_chars(self, agent: LogAnalyzerAgent) -> None:
        long_line = "UVM_FATAL @ 1ns: " + "x" * 200
        s = agent.analyze(long_line)
        assert len(s.message) <= 120

    def test_context_window_included(self, agent: LogAnalyzerAgent) -> None:
        log = "line before\nUVM_FATAL @ 10ns: bad\nline after\nmore"
        s = agent.analyze(log)
        assert "line before" in s.context_lines
        assert "UVM_FATAL" in "\n".join(s.context_lines)


class TestOutputFormat:
    def test_to_str_contains_sections(self, agent: LogAnalyzerAgent) -> None:
        s = agent.analyze("UVM_ERROR @ 1ns: oops")
        out = s.to_str()
        assert "### Failure Summary" in out
        assert "### Context Window" in out
        assert "### Debug Mode Required" in out
        assert "### Recommended Next Step" in out

    def test_compile_error_recommends_code_generator(self, agent: LogAnalyzerAgent) -> None:
        s = agent.analyze("*E,NOIPRT: port not found")
        assert "Code Generator" in s.next_step

    def test_debug_required_yes_in_output(self, agent: LogAnalyzerAgent) -> None:
        s = agent.analyze("no matching error here at all")
        out = s.to_str()
        assert "YES" in out


class TestFileInput:
    def test_reads_file_if_path_exists(self, agent: LogAnalyzerAgent, tmp_path: Path) -> None:
        log_file = tmp_path / "sim.log"
        log_file.write_text("UVM_FATAL @ 5ns: crash\n")
        s = agent.analyze(str(log_file))
        assert s.error_class == "uvm_fatal"

    def test_treats_nonexistent_path_as_content(self, agent: LogAnalyzerAgent) -> None:
        # A string that looks like a path but doesn't exist should be used as content
        fake = "nonexistent_dir/does_not_exist_xyz.log"
        s = agent.analyze(fake)
        # No error pattern in the fake path → unknown
        assert s.error_class == "unknown"


class TestAsyncRun:
    @pytest.mark.asyncio
    async def test_run_returns_string(self, agent: LogAnalyzerAgent) -> None:
        result = await agent.run("UVM_FATAL @ 1ns: test")
        assert isinstance(result, str)
        assert "uvm_fatal" in result
