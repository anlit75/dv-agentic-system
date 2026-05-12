# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Simulator and coverage adapter factories for the dv-agentic-system."""

from typing import cast

from ..interface import CoverageTool, SimulatorTool

__all__ = ["get_coverage_adapter", "get_simulator_adapter"]

_SIMULATOR_REGISTRY: dict[str, str] = {
    "xcelium": "dv_agentic.tools.adapters.xcelium.XceliumAdapter",
    "ghdl": "dv_agentic.tools.adapters.ghdl_cocotb.GHDLCocotbAdapter",
    "cocotb": "dv_agentic.tools.adapters.ghdl_cocotb.GHDLCocotbAdapter",
    "icarus": "dv_agentic.tools.adapters.icarus.IcarusAdapter",
    "verilator": "dv_agentic.tools.adapters.verilator.VerilatorAdapter",
}

_COVERAGE_REGISTRY: dict[str, str] = {
    "imc": "dv_agentic.tools.adapters.imc.IMCAdapter",
    "pyuvm": "dv_agentic.tools.adapters.pyuvm.PyuvmCoverageAdapter",
}


def _load(dotted_path: str) -> type:
    """Import and return a class from a dotted module path."""
    import importlib

    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)  # type: ignore[no-any-return]


def get_simulator_adapter(name: str) -> SimulatorTool:
    """Return a SimulatorTool instance for the given simulator name.

    Args:
        name: Simulator identifier.  Supported values: ``"xcelium"``,
            ``"ghdl"``, ``"cocotb"`` (alias for ``"ghdl"``),
            ``"icarus"``, ``"verilator"``.

    Raises:
        ValueError: If *name* is not a recognised simulator.

    """
    dotted = _SIMULATOR_REGISTRY.get(name.lower())
    if not dotted:
        raise ValueError(f"Unknown simulator: '{name}'.  Supported: {list(_SIMULATOR_REGISTRY)}")
    return cast(SimulatorTool, _load(dotted)())


def get_coverage_adapter(name: str) -> CoverageTool:
    """Return a CoverageTool instance for the given coverage tool name.

    Args:
        name: Coverage tool identifier.  Supported values: ``"imc"``
            (Cadence IMC 24.06 + Verisium 25.12, internal environment),
            ``"pyuvm"`` (text-based coverage reports for external environment).

    Raises:
        ValueError: If *name* is not a recognised coverage tool.

    """
    dotted = _COVERAGE_REGISTRY.get(name.lower())
    if not dotted:
        raise ValueError(f"Unknown coverage tool: '{name}'.  Supported: {list(_COVERAGE_REGISTRY)}")
    return cast(CoverageTool, _load(dotted)())
