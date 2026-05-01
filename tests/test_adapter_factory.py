"""Unit tests for the simulator / coverage adapter factories."""

import importlib

import pytest

from dv_agentic.tools.adapters import get_coverage_adapter, get_simulator_adapter
from dv_agentic.tools.adapters.imc import IMCAdapter
from dv_agentic.tools.adapters.xcelium import XceliumAdapter
from dv_agentic.tools.interface import CoverageTool, SimulatorTool

# cocotb.runner is Linux-only; skip GHDL adapter tests when unavailable.
cocotb_runner_available = importlib.util.find_spec("cocotb.runner") is not None
skip_no_cocotb = pytest.mark.skipif(
    not cocotb_runner_available, reason="cocotb.runner not available"
)


class TestGetSimulatorAdapter:
    def test_xcelium(self) -> None:
        adapter = get_simulator_adapter("xcelium")
        assert isinstance(adapter, XceliumAdapter)
        assert isinstance(adapter, SimulatorTool)

    @skip_no_cocotb
    def test_ghdl(self) -> None:
        from dv_agentic.tools.adapters.ghdl_cocotb import GHDLCocotbAdapter

        adapter = get_simulator_adapter("ghdl")
        assert isinstance(adapter, GHDLCocotbAdapter)

    @skip_no_cocotb
    def test_cocotb_alias(self) -> None:
        from dv_agentic.tools.adapters.ghdl_cocotb import GHDLCocotbAdapter

        adapter = get_simulator_adapter("cocotb")
        assert isinstance(adapter, GHDLCocotbAdapter)

    def test_case_insensitive(self) -> None:
        assert isinstance(get_simulator_adapter("Xcelium"), XceliumAdapter)

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown simulator"):
            get_simulator_adapter("vcs")


class TestGetCoverageAdapter:
    def test_imc(self) -> None:
        adapter = get_coverage_adapter("imc")
        assert isinstance(adapter, IMCAdapter)
        assert isinstance(adapter, CoverageTool)

    def test_case_insensitive(self) -> None:
        assert isinstance(get_coverage_adapter("IMC"), IMCAdapter)

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown coverage tool"):
            get_coverage_adapter("lcov")
