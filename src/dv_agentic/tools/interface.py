"""Abstract base classes defining the simulator and coverage tool contracts."""

import abc

from .models import CompileResult, CoverageDB, SimResult


class SimulatorTool(abc.ABC):
    """Interface for simulation tools (VCS, Questa, cocotb, etc.)."""

    @abc.abstractmethod
    def compile(self, file_list: list[str], top: str) -> CompileResult:
        """Compile the source files.

        Args:
            file_list: List of source file paths.
            top: Name of the top-level module.

        """

    @abc.abstractmethod
    def run(self, test: str, seed: int, debug: bool) -> SimResult:
        """Run a specific test.

        Args:
            test: Name of the test to run.
            seed: Random seed for simulation.
            debug: Whether to enable debug mode (e.g., waveform dumping).

        """


class CoverageTool(abc.ABC):
    """Interface for coverage analysis tools."""

    @abc.abstractmethod
    def get_coverage(self, job_id: str) -> CoverageDB:
        """Retrieve coverage results for a specific job.

        Args:
            job_id: The ID of the simulation job.

        """
