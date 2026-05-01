"""Adapter for Verilator simulator (External/Open-source environment)."""

from .cocotb_base import CocotbBaseAdapter


class VerilatorAdapter(CocotbBaseAdapter):
    """Adapter for Verilator simulator (External Environment)."""

    def __init__(
        self,
        hdl_toplevel: str = "top",
    ) -> None:
        """Initialize Verilator adapter.

        Args:
            hdl_toplevel: Name of the HDL top-level module.

        """
        super().__init__(simulator="verilator", hdl_toplevel=hdl_toplevel)
