"""Adapter for GHDL + cocotb + pyuvm (External/Open-source environment)."""

from .cocotb_base import CocotbBaseAdapter


class GHDLCocotbAdapter(CocotbBaseAdapter):
    """Adapter for GHDL + cocotb + pyuvm (External Environment)."""

    def __init__(
        self,
        hdl_toplevel: str = "top",
        hdl_toplevel_lang: str = "vhdl",
    ) -> None:
        """Initialize GHDL cocotb adapter.

        Args:
            hdl_toplevel: Name of the HDL top-level module.
            hdl_toplevel_lang: Language of the top-level module (usually ``"vhdl"``).

        """
        super().__init__(
            simulator="ghdl",
            hdl_toplevel=hdl_toplevel,
            hdl_toplevel_lang=hdl_toplevel_lang,
        )
