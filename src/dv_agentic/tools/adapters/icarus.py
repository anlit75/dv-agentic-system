"""Adapter for Icarus Verilog simulator (External/Open-source environment)."""

from .cocotb_base import CocotbBaseAdapter


class IcarusAdapter(CocotbBaseAdapter):
    """Adapter for Icarus Verilog simulator (External Environment)."""

    def __init__(
        self,
        hdl_toplevel: str = "top",
    ) -> None:
        """Initialize Icarus adapter.

        Args:
            hdl_toplevel: Name of the HDL top-level module.

        """
        super().__init__(simulator="icarus", hdl_toplevel=hdl_toplevel)
