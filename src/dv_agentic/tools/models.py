# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Data models for simulation results and coverage tracking."""

from dataclasses import dataclass, field
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
    wall_time_sec: int | None = None
    """Wall-clock time in seconds that the simulation took to run."""


@dataclass
class CoverageDB:
    """Representation of a coverage database."""

    path: str
    overall_percentage: float


@dataclass
class SimTask:
    """Input specification for a single SimControllerAgent run.

    Attributes:
        task_id: Unique identifier for this task (used for branch naming and
            commit messages).
        test: UVM test name or cocotb test module to run.
        seed: Random seed for the simulation.
        file_list: Source files to compile.  May be empty if the project
            already has a compiled snapshot.
        top: Top-level module name passed to the simulator.
        debug: Whether to enable debug mode (waveform dumping, full verbosity).
    """

    task_id: str
    test: str
    seed: int
    file_list: list[str] = field(default_factory=list)
    top: str = "top"
    debug: bool = False
