"""Adapter for Icarus Verilog simulator (External/Open-source environment)."""

import logging
import os

from cocotb.runner import get_runner

from ..interface import SimulatorTool
from ..models import CompileResult, SimResult

logger = logging.getLogger(__name__)


class IcarusAdapter(SimulatorTool):
    """Adapter for Icarus Verilog simulator (External Environment)."""

    def __init__(
        self,
        hdl_toplevel: str = "top",
    ) -> None:
        """Initialize Icarus adapter.

        Args:
            hdl_toplevel: Name of the HDL top-level module.

        """
        self.hdl_toplevel = hdl_toplevel
        self.runner = get_runner("icarus")

    def compile(self, file_list: list[str], top: str) -> CompileResult:
        """Compile source files using iverilog via cocotb runner."""
        self.hdl_toplevel = top
        try:
            self.runner.build(
                verilog_sources=file_list,
                hdl_toplevel=top,
                always=True,
            )
            return CompileResult(status="pass", output="Icarus Verilog build successful.")
        except Exception as e:
            logger.exception("Icarus Verilog build failed")
            return CompileResult(status="fail", output=str(e))

    def run(self, test: str, seed: int, debug: bool) -> SimResult:
        """Run cocotb simulation with Icarus Verilog."""
        env = {
            **os.environ,
            "SIM": "icarus",
            "RANDOM_SEED": str(seed),
        }
        log_path = f"sim_{test}_{seed}.log"

        try:
            # Note: Icarus Verilog might require specific plusargs or environment setup
            self.runner.test(
                hdl_toplevel=self.hdl_toplevel,
                test_module=test.split(".")[0],
                testcase=test.split(".")[1] if "." in test else None,
                waves=debug,
                extra_env=env,
            )

            return SimResult(
                status="pass",
                job_id=f"{test}_{seed}",
                log_path=log_path,
            )
        except Exception as e:
            logger.exception("Icarus Verilog simulation failed for test '%s'", test)
            return SimResult(
                status="fail",
                job_id=f"{test}_{seed}",
                log_path=log_path,
                error_summary=str(e),
            )
