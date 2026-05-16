# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Simulation execution service.

Manages the full lifecycle of a simulation task:
  1. Create ``ai-task/{task_id}`` git branch.
  2. Compile (fail-fast — never submit a broken build).
  3. Run the simulation in a loop, up to ``max_runs`` iterations.
  4. Commit the final state and report results.
"""

import asyncio
import json
import logging
import re
import subprocess
from dataclasses import dataclass

from ...tools.interface import CoverageTool, SimulatorTool
from ...tools.models import SimResult, SimTask

logger = logging.getLogger(__name__)


@dataclass
class SimReport:
    """Structured output from a completed SimControllerService run."""

    task_id: str
    final_status: str  # "pass" | "fail" | "timeout" | "compile_fail" | "escalated"
    runs_total: int
    branch: str
    ready_for_pr: bool
    last_result: SimResult | None = None

    def to_str(self) -> str:
        pr_note = "yes" if self.ready_for_pr else f"no (status={self.final_status})"
        lines = [
            "### Task Complete",
            f"task_id      : {self.task_id}",
            f"final_status : {self.final_status}",
            f"runs_total   : {self.runs_total}",
            f"branch       : {self.branch}",
            f"ready_for_pr : {pr_note}",
        ]
        if self.last_result and self.last_result.error_summary:
            lines.append(f"last_error   : {self.last_result.error_summary}")
        return "\n".join(lines)


class SimControllerService:
    """Runs compile → simulate → commit cycles within a git branch.

    Does not require LLM access.  All decisions are deterministic:
    compile fail → abort; sim pass → done; budget exhausted → escalate.

    Args:
        simulator: A ``SimulatorTool`` adapter (Xcelium, GHDL, Icarus, …).
        coverage: Optional ``CoverageTool`` adapter used to record the
            coverage DB path in the report.
        base_branch: Git branch to fork from.  Defaults to ``"main"``.
    """

    def __init__(
        self,
        simulator: SimulatorTool,
        coverage: CoverageTool | None = None,
        base_branch: str = "main",
    ) -> None:
        self.sim = simulator
        self.cov = coverage
        self.base_branch = base_branch

    async def run(self, task_input: str | SimTask, max_runs: int = 10) -> str:
        """Execute the simulation task lifecycle.

        Args:
            task_input: Either a :class:`SimTask` instance or a JSON string
                that deserialises into one.
            max_runs: Maximum number of simulation iterations to attempt.

        Returns:
            A human-readable report string (see :class:`SimReport`).
        """
        if not task_input:
            raise ValueError("task_input must not be empty")

        task = self._parse_task(task_input)

        if not task.task_id:
            raise ValueError("SimTask must have a task_id")

        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", task.task_id)
        branch = f"ai-task/{safe_id}"

        await asyncio.to_thread(self._git_checkout_new_branch, branch)

        # Fail-fast compile
        compile_result = await asyncio.to_thread(self.sim.compile, task.file_list, task.top)
        if compile_result.status == "fail":
            logger.error("Compile failed for task '%s'", task.task_id)
            return (
                SimReport(
                    task_id=task.task_id,
                    final_status="compile_fail",
                    runs_total=0,
                    branch=branch,
                    ready_for_pr=False,
                ).to_str()
                + f"\n\n### Compile Output\n{compile_result.output}"
            )

        # Sim loop — iterate up to max_runs times
        results: list[SimResult] = []
        for iteration in range(1, max_runs + 1):
            sim_result = await asyncio.to_thread(self.sim.run, task.test, task.seed, task.debug)
            results.append(sim_result)
            logger.info(
                "Sim iter=%d status=%s job_id=%s",
                iteration,
                sim_result.status,
                sim_result.job_id,
            )
            await asyncio.to_thread(
                self._git_commit,
                f"[agent] sim iter={iteration} · task:{task.task_id} · iter:{iteration}",
            )
            if sim_result.status == "pass":
                return SimReport(
                    task_id=task.task_id,
                    final_status="pass",
                    runs_total=iteration,
                    branch=branch,
                    ready_for_pr=True,
                    last_result=sim_result,
                ).to_str()

        # Budget exhausted
        await asyncio.to_thread(
            self._git_commit, f"[agent] budget exhausted · task:{task.task_id} · INCOMPLETE"
        )
        last = results[-1] if results else None
        return SimReport(
            task_id=task.task_id,
            final_status="escalated",
            runs_total=max_runs,
            branch=branch,
            ready_for_pr=False,
            last_result=last,
        ).to_str()

    @staticmethod
    def _parse_task(task_input: str | SimTask) -> SimTask:
        if isinstance(task_input, SimTask):
            return task_input
        return SimTask(**json.loads(task_input))

    def _git(self, *args: str) -> None:
        """Run a git command, raising CalledProcessError on failure."""
        subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            check=True,
            capture_output=True,
        )

    def _git_checkout_new_branch(self, branch: str) -> None:
        try:
            self._git("checkout", self.base_branch)
            self._git("pull", "--ff-only")
            self._git("checkout", "-B", branch)
        except subprocess.CalledProcessError as exc:
            logger.warning("git branch setup failed (may be expected in CI): %s", exc)

    def _git_commit(self, message: str) -> None:
        try:
            # Add only tracked files and newly created files that are NOT in .gitignore
            self._git("add", ".")
            self._git("commit", "-m", message)
        except subprocess.CalledProcessError:
            logger.debug("Nothing to commit for message: %s", message)
