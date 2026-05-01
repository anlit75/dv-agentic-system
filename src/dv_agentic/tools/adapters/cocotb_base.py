"""Base class for cocotb.runner based simulator adapters."""

import logging
import os
from typing import Any

from ..interface import SimulatorTool
from ..models import CompileResult, SimResult

logger = logging.getLogger(__name__)


try:
    from cocotb.runner import get_runner
except ImportError:
    get_runner = None


class CocotbBaseAdapter(SimulatorTool):
    """Base class for simulators using cocotb.runner infrastructure."""

    def __init__(
        self,
        simulator: str,
        hdl_toplevel: str = "top",
        hdl_toplevel_lang: str | None = None,
    ) -> None:
        """Initialize the cocotb base adapter.

        Args:
            simulator: Name of the simulator (e.g., "icarus", "verilator", "ghdl").
            hdl_toplevel: Name of the HDL top-level module.
            hdl_toplevel_lang: Language of the top-level module ("verilog" or "vhdl").
        """
        self.simulator = simulator
        self.hdl_toplevel = hdl_toplevel
        self.hdl_toplevel_lang = hdl_toplevel_lang

    def _get_runner(self) -> Any:
        if get_runner is None:
            raise ImportError("cocotb.runner is not available on this platform.")
        return get_runner(self.simulator)

    def compile(self, file_list: list[str], top: str) -> CompileResult:
        """Compile source files using the cocotb runner."""
        self.hdl_toplevel = top
        runner = self._get_runner()
        try:
            # Most cocotb runners support verilog_sources and vhdl_sources.
            # We determine which to use based on file extensions or subclass choice.
            # For simplicity in the base class, we can try to guess or use specific kwargs.
            build_kwargs: dict[str, Any] = {
                "hdl_toplevel": top,
                "always": True,
            }

            v_files = [f for f in file_list if f.endswith((".v", ".sv"))]
            vhdl_files = [f for f in file_list if f.endswith((".vhd", ".vhdl"))]

            if v_files:
                build_kwargs["verilog_sources"] = v_files
            if vhdl_files:
                build_kwargs["vhdl_sources"] = vhdl_files

            if self.hdl_toplevel_lang:
                build_kwargs["hdl_toplevel_lang"] = self.hdl_toplevel_lang

            runner.build(**build_kwargs)
            return CompileResult(
                status="pass",
                output=f"{self.simulator.capitalize()} build successful.",
            )
        except Exception as e:
            logger.exception("%s build failed", self.simulator.capitalize())
            return CompileResult(status="fail", output=str(e))

    def run(self, test: str, seed: int, debug: bool) -> SimResult:
        """Run cocotb simulation."""
        env = os.environ.copy()
        env.update(
            {
                "SIM": self.simulator,
                "RANDOM_SEED": str(seed),
            }
        )
        log_path = f"sim_{test}_{seed}.log"

        # Robust testcase parsing: handle "module" or "module.testcase"
        parts = test.split(".", 1)
        test_module = parts[0]
        testcase = parts[1] if len(parts) > 1 else None

        try:
            runner = self._get_runner()
            runner.test(
                hdl_toplevel=self.hdl_toplevel,
                hdl_toplevel_lang=self.hdl_toplevel_lang,
                test_module=test_module,
                testcase=testcase,
                waves=debug,
                extra_env=env,
            )

            return SimResult(
                status="pass",
                job_id=f"{test}_{seed}",
                log_path=log_path,
            )
        except Exception as e:
            logger.exception(
                "%s simulation failed for test '%s'",
                self.simulator.capitalize(),
                test,
            )
            return SimResult(
                status="fail",
                job_id=f"{test}_{seed}",
                log_path=log_path,
                error_summary=str(e),
            )
