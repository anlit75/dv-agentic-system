"""Data models for simulation results and coverage tracking."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class CompileResult:
    """Result of a compilation step."""

    status: Literal["pass", "fail"]
    output: str


@dataclass
class SimResult:
    """Result of a simulation run."""

    status: Literal["pass", "fail", "timeout"]
    job_id: str
    log_path: str
    error_summary: str | None = None
    cov_db_path: str | None = None
    """Path to the coverage DB written by the simulator (None if not collected)."""


@dataclass
class CoverageDB:
    """Representation of a coverage database."""

    path: str
    overall_percentage: float
