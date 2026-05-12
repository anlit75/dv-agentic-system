# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Adapter for Cadence Xcelium simulator (Internal environment)."""

import logging
import re
import subprocess
from typing import Literal

from ..interface import SimulatorTool
from ..models import CompileResult, SimResult

logger = logging.getLogger(__name__)


class XceliumAdapter(SimulatorTool):
    """Adapter for Cadence Xcelium simulator (Internal Environment)."""

    def __init__(
        self,
        xrun_path: str = "xrun",
        collect_coverage: bool = True,
        cov_work_dir: str = "cov_work",
    ) -> None:
        """Initialize Xcelium adapter.

        Args:
            xrun_path: Path to the xrun binary.
            collect_coverage: Whether to instrument the simulation for coverage.
                Set to ``False`` for quick smoke runs that skip IMC collection.
            cov_work_dir: Root directory for per-job coverage DBs.
                Each run writes to ``{cov_work_dir}/{job_id}/``.

        """
        self.xrun_path = xrun_path
        self.collect_coverage = collect_coverage
        self.cov_work_dir = cov_work_dir

    def compile(self, file_list: list[str], top: str) -> CompileResult:
        """Compile the source files using xrun -compile."""
        cmd = [self.xrun_path, "-compile", "-elaborate", "-64bit", "-uvm", "-top", top, *file_list]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
            status: Literal["pass", "fail"] = "pass" if result.returncode == 0 else "fail"

            return CompileResult(
                status=status,
                output=result.stdout + result.stderr,
            )
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.exception("Xcelium compile failed")
            return CompileResult(status="fail", output=str(e))

    def run(self, test: str, seed: int, debug: bool) -> SimResult:
        """Run a simulation using xrun -run."""
        cmd = [
            self.xrun_path,
            "-run",
            "-64bit",
            "-uvm",
            f"+UVM_TESTNAME={test}",
            f"+ntc_seed={seed}",
            "-l",
            f"sim_{test}_{seed}.log",
        ]

        if debug:
            cmd.extend(["-access", "+rwc", "-gui"])

        # Coverage instrumentation is delegated to IMCAdapter for analysis.
        # -covworkdir scopes each run to its own directory so merges are clean.
        cov_db_path: str | None = None
        if self.collect_coverage:
            cov_db_path = f"{self.cov_work_dir}/{test}_{seed}"
            cmd.extend(["-coverage", "all", "-covworkdir", cov_db_path, "-covoverwrite"])

        try:
            result = subprocess.run(  # noqa: S603
                cmd, capture_output=True, text=True, timeout=3600
            )
            status: Literal["pass", "fail"] = "pass" if result.returncode == 0 else "fail"
            log_path = f"sim_{test}_{seed}.log"
            error_summary = self._parse_errors(result.stdout + result.stderr)

            return SimResult(
                status=status,
                job_id=f"{test}_{seed}",
                log_path=log_path,
                error_summary=error_summary,
                cov_db_path=cov_db_path,
            )
        except subprocess.TimeoutExpired:
            logger.warning("Xcelium simulation timed out for test '%s' seed=%d", test, seed)
            return SimResult(
                status="timeout", job_id=f"{test}_{seed}", log_path="", cov_db_path=None
            )

    def _parse_errors(self, output: str) -> str | None:
        """Parse Xcelium-specific error patterns."""
        # Xcelium errors typically start with *E or *F
        error_pattern = r"\*E,(\w+): (.*)"
        matches = re.findall(error_pattern, output)
        if matches:
            return "\n".join(f"{code}: {msg}" for code, msg in matches)

        # Also check for UVM_ERROR
        uvm_error_pattern = r"UVM_ERROR @ (.*)"
        uvm_matches = re.findall(uvm_error_pattern, output)
        if uvm_matches:
            return "\n".join(uvm_matches)

        return None
