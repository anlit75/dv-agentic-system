# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Tests for failure_subtype classification added to LogAnalyzerAgent.

These tests extend the existing test_log_analyzer.py coverage to verify the
CVDP-informed granular sub-type field and its appearance in to_str() output.
They are intentionally kept in a separate file so the original test module
remains untouched (surgical-change principle).
"""

import pytest

from dv_agentic.agents.base import AgentConfig
from dv_agentic.agents.log_analyzer import LogAnalyzerAgent


@pytest.fixture()
def agent() -> LogAnalyzerAgent:
    return LogAnalyzerAgent(config=AgentConfig(name="log_analyzer"))


# ---------------------------------------------------------------------------
# failure_subtype: compile-error cluster
# ---------------------------------------------------------------------------


class TestCompileSubtypes:
    def test_missing_timescale(self, agent: LogAnalyzerAgent) -> None:
        log = "*E,NOTIME (tb/seq.sv,1): `timescale not defined"
        s = agent.analyze(log)
        assert s.error_class == "compile_error"
        assert s.failure_subtype == "missing_timescale"

    def test_unmatched_block(self, agent: LogAnalyzerAgent) -> None:
        log = "*E,MATCH (tb/seq.sv,42): unexpected end found, missing begin"
        s = agent.analyze(log)
        assert s.error_class == "compile_error"
        assert s.failure_subtype == "unmatched_block"

    def test_mixed_assignment(self, agent: LogAnalyzerAgent) -> None:
        log = "*E,MIXED (tb/seq.sv,10): blocking and non-blocking assignments mixed"
        s = agent.analyze(log)
        assert s.error_class == "compile_error"
        assert s.failure_subtype == "mixed_assignment"

    def test_multiple_drivers(self, agent: LogAnalyzerAgent) -> None:
        log = "*E,MDRIV (tb/seq.sv,7): multiple drivers found on signal 'ready'"
        s = agent.analyze(log)
        assert s.error_class == "compile_error"
        assert s.failure_subtype == "multiple_drivers"

    def test_width_mismatch(self, agent: LogAnalyzerAgent) -> None:
        log = "*E,WIDTH (tb/seq.sv,3): width mismatch: 4-bit expression assigned to 8-bit target"
        s = agent.analyze(log)
        assert s.error_class == "compile_error"
        assert s.failure_subtype == "width_mismatch"

    def test_interface_mismatch_compile(self, agent: LogAnalyzerAgent) -> None:
        log = "*E,NOIPRT (tb/env.sv,12): port not found in interface"
        s = agent.analyze(log)
        assert s.error_class == "compile_error"
        assert s.failure_subtype == "interface_mismatch"

    def test_ghdl_unmatched_block(self, agent: LogAnalyzerAgent) -> None:
        log = "ghdl: error: unexpected end found without begin"
        s = agent.analyze(log)
        assert s.error_class == "compile_error"
        assert s.failure_subtype == "unmatched_block"

    def test_generic_compile_error_falls_back_to_syntax_general(
        self, agent: LogAnalyzerAgent
    ) -> None:
        log = "*E,SYNERR (tb/seq.sv,5): syntax error near 'class'"
        s = agent.analyze(log)
        assert s.error_class == "compile_error"
        assert s.failure_subtype == "syntax_general"


# ---------------------------------------------------------------------------
# failure_subtype: sim-error cluster
# ---------------------------------------------------------------------------


class TestSimSubtypes:
    def test_scoreboard_fail(self, agent: LogAnalyzerAgent) -> None:
        log = "UVM_ERROR @ 100ns: scoreboard expected 0xAA, got 0xBB"
        s = agent.analyze(log)
        assert s.error_class == "uvm_error"
        assert s.failure_subtype == "scoreboard_fail"

    def test_coverage_miss(self, agent: LogAnalyzerAgent) -> None:
        log = "UVM_ERROR @ 50ns: coverage bin 'back_pressure' has 0 hits"
        s = agent.analyze(log)
        assert s.error_class == "uvm_error"
        assert s.failure_subtype == "coverage_miss"

    def test_timing_offset(self, agent: LogAnalyzerAgent) -> None:
        log = "UVM_ERROR @ 200ns: timing violation — clock edge synchronization failed"
        s = agent.analyze(log)
        assert s.error_class == "uvm_error"
        assert s.failure_subtype == "timing_offset"

    def test_protocol_violation(self, agent: LogAnalyzerAgent) -> None:
        log = "UVM_FATAL @ 10ns [PROTOCOL] SVA property 'axi_valid_stable' failed"
        s = agent.analyze(log)
        assert s.error_class == "uvm_fatal"
        assert s.failure_subtype == "protocol_violation"

    def test_sim_general_fallback(self, agent: LogAnalyzerAgent) -> None:
        log = "UVM_ERROR @ 5ns: unexpected value on output"
        s = agent.analyze(log)
        assert s.error_class == "uvm_error"
        assert s.failure_subtype == "sim_general"

    def test_unknown_class_uses_unknown_subtype(self, agent: LogAnalyzerAgent) -> None:
        log = "Everything looks fine. Simulation complete."
        s = agent.analyze(log)
        assert s.error_class == "unknown"
        assert s.failure_subtype == "unknown"


# ---------------------------------------------------------------------------
# failure_subtype appears in to_str() output
# ---------------------------------------------------------------------------


class TestFailureSubtypeInOutput:
    def test_subtype_in_to_str(self, agent: LogAnalyzerAgent) -> None:
        log = "*E,NOTIME (tb/seq.sv,1): `timescale not defined"
        out = agent.analyze(log).to_str()
        assert "failure_subtype  : missing_timescale" in out

    def test_subtype_present_for_unknown(self, agent: LogAnalyzerAgent) -> None:
        out = agent.analyze("clean log, no error").to_str()
        assert "failure_subtype  : unknown" in out

    @pytest.mark.asyncio
    async def test_async_run_includes_subtype(self, agent: LogAnalyzerAgent) -> None:
        result = await agent.run("*E,SYNERR: syntax error near 'class'")
        assert "failure_subtype" in result


# ---------------------------------------------------------------------------
# _classify_subtype static method directly
# ---------------------------------------------------------------------------


class TestClassifySubtype:
    def test_compile_missing_timescale(self) -> None:
        assert (
            LogAnalyzerAgent._classify_subtype("compile_error", "`timescale not defined")
            == "missing_timescale"
        )

    def test_compile_syntax_general(self) -> None:
        assert (
            LogAnalyzerAgent._classify_subtype("compile_error", "some random compile failure")
            == "syntax_general"
        )

    def test_sim_general(self) -> None:
        assert LogAnalyzerAgent._classify_subtype("uvm_error", "unexpected value") == "sim_general"

    def test_unknown_echoes_class(self) -> None:
        assert LogAnalyzerAgent._classify_subtype("unknown", "no pattern") == "unknown"

    def test_unrecognised_class_echoes_class(self) -> None:
        # Future error classes not in the known sets should fall through gracefully
        assert LogAnalyzerAgent._classify_subtype("future_class", "some text") == "future_class"
