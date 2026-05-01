"""Adapter for Cadence IMC 24.06 + Verisium 25.12 coverage tools (Internal environment).

Workflow
--------
1. ``XceliumAdapter.run()`` writes a per-job coverage DB to
   ``{cov_work_dir}/{job_id}/`` (one directory per simulation run).
2. ``IMCAdapter.get_coverage(job_id)`` loads that directory and returns a
   ``CoverageDB`` summary.
3. ``IMCAdapter.merge(job_ids)`` merges multiple runs into a single aggregated
   DB, then optionally invokes Verisium ``vsif`` for enterprise-level
   aggregation reports.

Assumed tool versions
---------------------
- IMC      : 24.06.a001
- Verisium : 25.12.081
- OS       : RHEL 8.4
"""

import logging
import re
import subprocess
from pathlib import Path

from ..interface import CoverageTool
from ..models import CoverageDB

logger = logging.getLogger(__name__)

# Matches IMC reportstats lines such as:
#   "Cumulative coverage result: 87.65 %"
#   "Total coverage: 82.35%"
#   "Overall coverage: 79.10 %"
_TOTAL_COV_RE = re.compile(
    r"(?:cumulative\s+coverage\s+result|total\s+coverage|overall\s+coverage)"
    r"[^\d]*(\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)


class IMCAdapter(CoverageTool):
    """Coverage adapter for IMC 24.06 + Verisium 25.12 (Internal environment).

    Paired with ``XceliumAdapter`` — both must share the same ``cov_work_dir``
    so that job IDs resolve to the same filesystem paths.
    """

    def __init__(
        self,
        imc_path: str = "imc",
        vsif_path: str = "vsif",
        cov_work_dir: str = "cov_work",
    ) -> None:
        """Initialize the IMC coverage adapter.

        Args:
            imc_path: Path to the ``imc`` binary (Cadence IMC 24.06).
            vsif_path: Path to the ``vsif`` binary (Verisium 25.12).
            cov_work_dir: Root directory where ``XceliumAdapter`` writes
                per-job coverage DBs.  Each job writes to
                ``{cov_work_dir}/{job_id}/``.

        """
        self.imc_path = imc_path
        self.vsif_path = vsif_path
        self.cov_work_dir = cov_work_dir

    # ------------------------------------------------------------------
    # CoverageTool ABC
    # ------------------------------------------------------------------

    def get_coverage(self, job_id: str) -> CoverageDB:
        """Load a single run's coverage DB and return a summary.

        Args:
            job_id: Simulation job identifier produced by ``XceliumAdapter``,
                e.g. ``"my_test_42"``.  The coverage DB is expected at
                ``{cov_work_dir}/{job_id}/``.

        """
        db_path = Path(self.cov_work_dir) / job_id
        return self._report(db_path)

    # ------------------------------------------------------------------
    # IMC / Verisium-specific: multi-run merge
    # ------------------------------------------------------------------

    def merge(
        self,
        job_ids: list[str],
        merged_dir: str = "cov_merged",
        use_verisium: bool = False,
    ) -> CoverageDB:
        """Merge coverage from multiple simulation runs into one aggregated DB.

        Runs ``imc -load <dir1> <dir2> ... -merge <merged_dir> -exit`` to
        aggregate per-job coverage DBs, then optionally invokes Verisium
        ``vsif`` for cross-session enterprise-level reporting.

        Args:
            job_ids: Job IDs whose coverage DBs will be merged.
            merged_dir: Destination directory for the aggregated DB.
            use_verisium: If ``True``, run ``vsif run <merged_dir>/merge.vsif``
                after the IMC merge step.  The ``.vsif`` file must already
                exist in ``merged_dir`` (typically hand-authored or generated
                by a prior Verisium session).

        """
        load_dirs = [str(Path(self.cov_work_dir) / jid) for jid in job_ids]
        cmd = [self.imc_path, "-64", "-load", *load_dirs, "-merge", merged_dir, "-exit"]
        logger.info("IMC merge: %d run(s) → %s", len(job_ids), merged_dir)

        try:
            result = subprocess.run(  # noqa: S603
                cmd, capture_output=True, text=True, timeout=600
            )
            if result.returncode != 0:
                logger.error("IMC merge failed:\n%s", result.stderr)
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.exception("IMC merge invocation failed")

        if use_verisium:
            self._verisium_merge(merged_dir)

        return self._report(Path(merged_dir))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _report(self, db_path: Path) -> CoverageDB:
        """Run ``imc -reportstats`` on *db_path* and parse total coverage %.

        Args:
            db_path: Path to an IMC coverage DB directory.

        """
        cmd = [
            self.imc_path,
            "-64",
            "-load",
            str(db_path),
            "-reportstats",
            "-exit",
        ]
        try:
            result = subprocess.run(  # noqa: S603
                cmd, capture_output=True, text=True, timeout=120
            )
            pct = self._parse_total(result.stdout + result.stderr)
            if pct is None:
                logger.warning(
                    "IMC report: could not parse total coverage percentage from output "
                    "(db_path=%s)",
                    db_path,
                )
                pct = 0.0
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.exception("IMC report invocation failed for '%s'", db_path)
            pct = 0.0

        return CoverageDB(path=str(db_path), overall_percentage=pct)

    def _parse_total(self, output: str) -> float | None:
        """Extract the total coverage percentage from IMC reportstats output.

        Handles common IMC 24.06 output variants:

        - ``Cumulative coverage result: 87.65 %``
        - ``Total coverage: 82.35%``
        - ``Overall coverage: 79.10 %``

        Args:
            output: Raw stdout + stderr from the ``imc`` process.

        """
        match = _TOTAL_COV_RE.search(output)
        if match:
            return float(match.group(1))
        return None

    def _verisium_merge(self, merged_dir: str) -> None:
        """Invoke Verisium ``vsif run`` on the ``.vsif`` file in *merged_dir*.

        The ``.vsif`` file encodes which merged DB directories to aggregate and
        which Verisium report templates to apply.  It must exist at
        ``{merged_dir}/merge.vsif`` before calling this method.

        Args:
            merged_dir: Directory containing the ``merge.vsif`` file.

        """
        vsif_file = Path(merged_dir) / "merge.vsif"
        if not vsif_file.exists():
            logger.warning(
                "Verisium merge skipped: %s not found.  Create or copy a .vsif file there first.",
                vsif_file,
            )
            return

        cmd = [self.vsif_path, "run", str(vsif_file)]
        logger.info("Verisium vsif: running %s", vsif_file)
        try:
            result = subprocess.run(  # noqa: S603
                cmd, capture_output=True, text=True, timeout=1800
            )
            if result.returncode != 0:
                logger.error("Verisium vsif failed:\n%s", result.stderr)
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.exception("Verisium vsif invocation failed")
