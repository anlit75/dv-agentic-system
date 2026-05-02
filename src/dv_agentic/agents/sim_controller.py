"""Simulation execution agent (Phase 3a — no LLM required).

Manages the full lifecycle of a simulation task:
  1. Create ``agent/{task_id}`` git branch.
  2. Compile (fail-fast — never submit a broken build).
  3. Run the simulation in a loop, respecting the budget in ``AgentConfig``.
  4. Commit the final state and report results.
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass

from ..tools.interface import CoverageTool, SimulatorTool
from ..tools.models import SimResult, SimTask
from .base import AgentConfig, BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class SimReport:
    """Structured output from a completed SimControllerAgent run."""

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


class SimControllerAgent(BaseAgent):
    """Runs compile → simulate → commit cycles within a git branch.

    Does not require LLM access.  All decisions are deterministic:
    compile fail → abort; sim pass → done; budget exhausted → escalate.

    Args:
        config: Agent configuration (name, budget, environment).
        simulator: A ``SimulatorTool`` adapter (Xcelium, GHDL, Icarus, …).
        coverage: Optional ``CoverageTool`` adapter used to record the
            coverage DB path in the report.
        base_branch: Git branch to fork from.  Defaults to ``"main"``.
    """

    def __init__(
        self,
        config: AgentConfig,
        simulator: SimulatorTool,
        coverage: CoverageTool | None = None,
        base_branch: str = "main",
    ) -> None:
        super().__init__(config)
        self.sim = simulator
        self.cov = coverage
        self.base_branch = base_branch

    # ------------------------------------------------------------------
    # BaseAgent ABC
    # ------------------------------------------------------------------

    async def run(self, task_input: str | SimTask) -> str:
        """Execute the simulation task lifecycle.

        Args:
            task_input: Either a :class:`SimTask` instance or a JSON string
                that deserialises into one.

        Returns:
            A human-readable report string (see :class:`SimReport`).
        """
        task = self._parse_task(task_input)
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", task.task_id)
        branch = f"agent/{safe_id}"

        self._git_checkout_new_branch(branch)

        # Fail-fast compile
        compile_result = self.sim.compile(task.file_list, task.top)
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

        # Sim loop — self.step() checks budget AND increments self.iteration
        results: list[SimResult] = []
        while self.step():
            sim_result = self.sim.run(task.test, task.seed, task.debug)
            results.append(sim_result)
            logger.info(
                "Sim iter=%d status=%s job_id=%s",
                self.iteration,
                sim_result.status,
                sim_result.job_id,
            )
            self._git_commit(
                f"[agent] sim iter={self.iteration} · task:{task.task_id} · iter:{self.iteration}"
            )
            if sim_result.status == "pass":
                return SimReport(
                    task_id=task.task_id,
                    final_status="pass",
                    runs_total=self.iteration,
                    branch=branch,
                    ready_for_pr=True,
                    last_result=sim_result,
                ).to_str()

        # Budget exhausted
        self._git_commit(f"[agent] budget exhausted · task:{task.task_id} · INCOMPLETE")
        last = results[-1] if results else None
        return SimReport(
            task_id=task.task_id,
            final_status="escalated",
            runs_total=self.iteration,
            branch=branch,
            ready_for_pr=False,
            last_result=last,
        ).to_str()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
            self._git("checkout", "-b", branch)
        except subprocess.CalledProcessError as exc:
            logger.warning("git branch setup failed (may be expected in CI): %s", exc)

    def _git_commit(self, message: str) -> None:
        try:
            self._git("add", "-A")
            self._git("commit", "-m", message)
        except subprocess.CalledProcessError:
            logger.debug("Nothing to commit for message: %s", message)
