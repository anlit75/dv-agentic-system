"""Coverage analysis agent.

The agent retrieves a coverage DB for a given job ID, compares the
overall percentage against a threshold, and return a structured summary.

Hole classification (actionable / protocol_blocked / design_excluded) and
priority ranking are LLM-powered features intended for future extension.
"""

import asyncio
import logging
from dataclasses import dataclass

from ..tools.interface import CoverageTool
from ..tools.models import CoverageDB
from .base import AgentConfig, BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class CoverageSummary:
    """Structured output from :class:`CoverageAnalystAgent`."""

    job_id: str
    db_path: str
    overall_pct: float
    threshold_pct: float
    below_threshold: bool

    def to_str(self) -> str:
        status = "BELOW THRESHOLD ⚠" if self.below_threshold else "OK ✓"
        lines = [
            "### Coverage Summary",
            f"job_id     : {self.job_id}",
            f"db_path    : {self.db_path}",
            f"overall    : {self.overall_pct:.2f}%",
            f"threshold  : {self.threshold_pct:.2f}%",
            f"status     : {status}",
        ]
        if self.below_threshold:
            gap = self.threshold_pct - self.overall_pct
            lines += [
                f"gap        : {gap:.2f}% needed to reach threshold",
                "action     : Coverage hole analysis required (Phase 3b LLM agent)",
            ]
        return "\n".join(lines)


class CoverageAnalystAgent(BaseAgent):
    """Retrieves coverage for a job and reports whether it meets the threshold.

    Does not require LLM access. This agent can be extended
    to support LLM-based analysis.

    Args:
        config: Agent configuration.
        coverage: A ``CoverageTool`` adapter (IMC or pyuvm).
        threshold: Minimum acceptable overall coverage percentage.
            Defaults to 90.0.
    """

    def __init__(
        self,
        config: AgentConfig,
        coverage: CoverageTool,
        threshold: float = 90.0,
    ) -> None:
        super().__init__(config)
        self.cov = coverage
        self.threshold = threshold

    # ------------------------------------------------------------------
    # BaseAgent ABC
    # ------------------------------------------------------------------

    async def run(self, task_input: str) -> str:
        """Retrieve and summarise coverage for a simulation job.

        Args:
            task_input: The job ID whose coverage DB should be queried.

        Returns:
            A formatted :class:`CoverageSummary` string.
        """
        if not task_input or not isinstance(task_input, str):
            raise ValueError("task_input must be a non-empty string")

        if self.iteration != 0:
            raise RuntimeError(f"Agent must start at iteration 0 (current: {self.iteration})")

        await self.step()  # Deterministic agent
        summary = await asyncio.to_thread(self.get_summary, task_input)
        return summary.to_str()

    # ------------------------------------------------------------------
    # Public helper (useful for downstream agents without async overhead)
    # ------------------------------------------------------------------

    def get_summary(self, job_id: str) -> CoverageSummary:
        """Return a :class:`CoverageSummary` for *job_id*.

        Args:
            job_id: Simulation job identifier.
        """
        if not job_id or not isinstance(job_id, str):
            raise ValueError("job_id must be a non-empty string")

        db: CoverageDB = self.cov.get_coverage(job_id)

        if db.overall_percentage < 0:
            raise ValueError(f"Coverage percentage cannot be negative: {db.overall_percentage}")

        logger.info(
            "Coverage for job '%s': %.2f%% (threshold=%.2f%%)",
            job_id,
            db.overall_percentage,
            self.threshold,
        )
        return CoverageSummary(
            job_id=job_id,
            db_path=db.path,
            overall_pct=db.overall_percentage,
            threshold_pct=self.threshold,
            below_threshold=db.overall_percentage < self.threshold,
        )
