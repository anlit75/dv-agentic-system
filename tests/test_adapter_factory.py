# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Unit tests for the simulator / coverage adapter factories."""

import importlib.util

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
    def test_xcelium_returns_correct_type(self) -> None:
        adapter = get_simulator_adapter("xcelium")
        assert isinstance(adapter, XceliumAdapter)
        assert isinstance(adapter, SimulatorTool)

    @skip_no_cocotb
    def test_ghdl_returns_correct_type(self) -> None:
        from dv_agentic.tools.adapters.ghdl_cocotb import GHDLCocotbAdapter

        adapter = get_simulator_adapter("ghdl")
        assert isinstance(adapter, GHDLCocotbAdapter)
        assert isinstance(adapter, SimulatorTool)

    @skip_no_cocotb
    def test_icarus_returns_correct_type(self) -> None:
        from dv_agentic.tools.adapters.icarus import IcarusAdapter

        adapter = get_simulator_adapter("icarus")
        assert isinstance(adapter, IcarusAdapter)
        assert isinstance(adapter, SimulatorTool)

    @skip_no_cocotb
    def test_verilator_returns_correct_type(self) -> None:
        from dv_agentic.tools.adapters.verilator import VerilatorAdapter

        adapter = get_simulator_adapter("verilator")
        assert isinstance(adapter, VerilatorAdapter)
        assert isinstance(adapter, SimulatorTool)

    @pytest.mark.parametrize("name", ["Xcelium", "XCELIUM", "xCeLiUm"])
    def test_case_insensitive(self, name: str) -> None:
        assert isinstance(get_simulator_adapter(name), XceliumAdapter)

    @pytest.mark.parametrize("name", ["vcs", "modelsim", "", "unknown"])
    def test_unknown_name_raises(self, name: str) -> None:
        with pytest.raises(ValueError, match="Unknown simulator"):
            get_simulator_adapter(name)


class TestGetCoverageAdapter:
    def test_imc_returns_correct_type(self) -> None:
        adapter = get_coverage_adapter("imc")
        assert isinstance(adapter, IMCAdapter)
        assert isinstance(adapter, CoverageTool)

    def test_pyuvm_returns_correct_type(self) -> None:
        from dv_agentic.tools.adapters.pyuvm import PyuvmCoverageAdapter

        adapter = get_coverage_adapter("pyuvm")
        assert isinstance(adapter, PyuvmCoverageAdapter)
        assert isinstance(adapter, CoverageTool)

    @pytest.mark.parametrize("name", ["IMC", "Imc", "iMc"])
    def test_case_insensitive(self, name: str) -> None:
        assert isinstance(get_coverage_adapter(name), IMCAdapter)

    @pytest.mark.parametrize("name", ["lcov", "gcov", "", "unknown"])
    def test_unknown_name_raises(self, name: str) -> None:
        with pytest.raises(ValueError, match="Unknown coverage tool"):
            get_coverage_adapter(name)
