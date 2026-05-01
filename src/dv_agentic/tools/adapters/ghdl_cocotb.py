"""Adapter for GHDL + cocotb + pyuvm (External/Open-source environment)."""

import logging
import os
from typing import Literal

from cocotb.runner import get_runner

from ..interface import SimulatorTool
from ..models import CompileResult, SimResult

logger = logging.getLogger(__name__)


class GHDLCocotbAdapter(SimulatorTool):
    """Adapter for GHDL + cocotb + pyuvm (External Environment)."""

    def __init__(
        self,
        hdl_toplevel: str = "top",
        hdl_toplevel_lang: str = "vhdl",
    ) -> None:
        """Initialize GHDL cocotb adapter.

        Args:
            hdl_toplevel: Name of the HDL top-level module.  Updated
                automatically when ``compile()`` is called with a ``top``
                argument, so explicit construction is only needed when
                calling ``run()`` without a prior ``compile()`` call.
            hdl_toplevel_lang: Language of the top-level module (``"vhdl"``).

        """
        self.hdl_toplevel = hdl_toplevel
        self.hdl_toplevel_lang = hdl_toplevel_lang
        self.runner = get_runner("ghdl")

    def compile(self, file_list: list[str], top: str) -> CompileResult:
        """Compile/Analyze source files using GHDL."""
        self.hdl_toplevel = top  # Keep run() consistent with compile()
        try:
            self.runner.build(
                vhdl_sources=file_list,
                hdl_toplevel=top,
                always=True,
            )
            return CompileResult(status="pass", output="GHDL build successful.")
        except Exception as e:
            logger.exception("GHDL build failed")
            return CompileResult(status="fail", output=str(e))

    def run(self, test: str, seed: int, debug: bool) -> SimResult:
        """Run cocotb simulation with GHDL."""
        # cocotb is configured via environment variables; scope them to avoid
        # mutating the global process environment across successive test runs.
        env = {
            **os.environ,
            "SIM": "ghdl",
            "RANDOM_SEED": str(seed),
        }
        log_path = f"sim_{test}_{seed}.log"

        # Testcase mapping: test usually refers to a Python class/function in cocotb
        try:
            self.runner.test(
                hdl_toplevel=self.hdl_toplevel,
                test_module=test.split(".")[0],  # Assuming module.testcase format
                testcase=test.split(".")[1] if "." in test else None,
                waves=debug,
                extra_env=env,
            )

            status: Literal["pass", "fail"] = "pass"
            return SimResult(
                status=status,
                job_id=f"{test}_{seed}",
                log_path=log_path,
            )
        except Exception as e:
            logger.exception("GHDL simulation failed for test '%s'")
            return SimResult(
                status="fail",
                job_id=f"{test}_{seed}",
                log_path=log_path,
                error_summary=str(e),
            )
