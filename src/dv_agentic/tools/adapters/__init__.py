"""Simulator and coverage adapter factories for the dv-agentic-system."""

from ..interface import CoverageTool, SimulatorTool
from .ghdl_cocotb import GHDLCocotbAdapter
from .imc import IMCAdapter
from .xcelium import XceliumAdapter

__all__ = ["get_coverage_adapter", "get_simulator_adapter"]


def get_simulator_adapter(name: str) -> SimulatorTool:
    """Return a SimulatorTool instance for the given simulator name.

    Args:
        name: Simulator identifier.  Supported values: ``"xcelium"``,
            ``"ghdl"``, ``"cocotb"`` (alias for ``"ghdl"``).

    Raises:
        ValueError: If *name* is not a recognised simulator.

    """
    mapping: dict[str, type[SimulatorTool]] = {
        "xcelium": XceliumAdapter,
        "ghdl": GHDLCocotbAdapter,
        "cocotb": GHDLCocotbAdapter,  # Alias
    }

    adapter_class = mapping.get(name.lower())
    if not adapter_class:
        raise ValueError(f"Unknown simulator: '{name}'.  Supported: {list(mapping)}")

    return adapter_class()


def get_coverage_adapter(name: str) -> CoverageTool:
    """Return a CoverageTool instance for the given coverage tool name.

    Args:
        name: Coverage tool identifier.  Supported values: ``"imc"``
            (Cadence IMC 24.06 + Verisium 25.12, internal environment).

    Raises:
        ValueError: If *name* is not a recognised coverage tool.

    """
    mapping: dict[str, type[CoverageTool]] = {
        "imc": IMCAdapter,
    }

    adapter_class = mapping.get(name.lower())
    if not adapter_class:
        raise ValueError(f"Unknown coverage tool: '{name}'.  Supported: {list(mapping)}")

    return adapter_class()
