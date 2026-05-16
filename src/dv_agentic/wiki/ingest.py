# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Wiki ingest service — writes agent analysis results into the wiki.

Phase A scope:
  ``ingest_pattern()``  — create or update ``patterns/{failure_subtype}.md``

Phase B scope (this file):
  ``ingest_bug()``      — create a new ``bugs/{TYPE}_{date}_{seq}.md`` page

Phase C will add:  ``ingest_coverage_hole()``

Design constraints
------------------
* Every write is atomic (temp-file + ``os.replace``).
* ``log.md`` is **append-only** — existing entries are never modified.
* Failures are **non-fatal**: callers catch all exceptions and log at DEBUG
  so a wiki write error never crashes an agent session.
* No LLM client is required in Phase A/B — all content is structured data
  derived from ``LogAnalyzerAgent`` / ``BugClassifierAgent`` output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .manager import (
    WikiConfig,
    atomic_write,
    now_iso,
    parse_page,
    serialize_page,
    today_str,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class WikiIngestResult:
    """Summary of a completed :class:`WikiIngestService` operation.

    Attributes:
        task_id: Originating task identifier (used for citation).
        pages_created: Relative paths of newly created wiki pages.
        pages_updated: Relative paths of updated wiki pages.
        log_entry: The text appended to ``log.md``.
        index_updated: Whether ``index.md`` was regenerated.
        search_index_updated: Whether the BM25 index was refreshed.
    """

    task_id: str
    pages_created: list[str] = field(default_factory=list)
    pages_updated: list[str] = field(default_factory=list)
    log_entry: str = ""
    index_updated: bool = False
    search_index_updated: bool = False


# ---------------------------------------------------------------------------
# Pattern page template (used only for brand-new pages)
# ---------------------------------------------------------------------------

_PATTERN_BODY_TEMPLATE = """\
# Pattern: {pattern_id}

## Description
*(Auto-generated from first occurrence. Update with a human-readable explanation.)*

## Detection Signature
```
{signature}
```

## Fix Template
*(Add the standard fix here so CodeGeneratorAgent can apply it directly.)*

## Resolution History
| Date | Task | Fix Applied | Result |
|------|------|-------------|--------|
{first_row}
"""


_BUG_BODY_TEMPLATE = """\
# Bug Report: {bug_id}

## Classification
Type: {bug_type}

## Evidence
{evidence_lines}
{log_ref}

## Analysis
*(Auto-generated. Update with root-cause analysis and affected signals.)*

## Resolution
*(Fill in when the bug is confirmed or closed.)*
"""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class WikiIngestService:
    """Writes ``LogAnalyzerAgent`` results into the wiki knowledge base.

    Args:
        wiki_config: Wiki integration configuration.
    """

    def __init__(self, wiki_config: WikiConfig) -> None:
        self.cfg = wiki_config
        self._search_index: Any | None = None  # lazy-initialised

    # ------------------------------------------------------------------
    # Phase A public API
    # ------------------------------------------------------------------

    def ingest_pattern(
        self,
        failure_subtype: str,
        error_class: str,
        context_lines: list[str],
        fix_applied: str | None,
        success: bool,
        task_id: str,
    ) -> WikiIngestResult:
        """Create or update ``patterns/{failure_subtype}.md``.

        On first occurrence the page is created from a template.  On
        subsequent calls only ``hit_count``, ``last_seen``, and the
        Resolution History table are updated.

        Args:
            failure_subtype: Granular subtype from
                :meth:`~dv_agentic.agents.log_analyzer.LogAnalyzerAgent._classify_subtype`
                (e.g. ``"missing_timescale"``).
            error_class: Top-level error class (e.g. ``"compile_error"``).
            context_lines: Lines surrounding the matched error in the log.
            fix_applied: Short description of the fix applied, or ``None``.
            success: Whether the fix led to a passing simulation.
            task_id: Task identifier used in the citation footer.

        Returns:
            :class:`WikiIngestResult` describing what was written.
        """
        result = WikiIngestResult(task_id=task_id)
        patterns_dir = self.cfg.wiki_dir / "patterns"
        patterns_dir.mkdir(parents=True, exist_ok=True)

        page_path = patterns_dir / f"{failure_subtype}.md"
        today = today_str()

        if page_path.exists():
            result = self._update_pattern_page(
                page_path, fix_applied, success, task_id, today, result
            )
        else:
            result = self._create_pattern_page(
                page_path,
                failure_subtype,
                error_class,
                context_lines,
                fix_applied,
                success,
                task_id,
                today,
                result,
            )

        # Refresh search index (non-fatal)
        try:
            idx = self._get_search_index()
            idx.update(page_path, page_path.read_text(encoding="utf-8"))
            result.search_index_updated = True
        except Exception:
            logger.debug("Wiki: search index update failed (non-fatal)", exc_info=True)

        # Append to log.md
        log_entry = self._build_log_entry(
            task_id, error_class, failure_subtype, fix_applied, success, result
        )
        result.log_entry = log_entry
        self._append_log(log_entry)

        # Regenerate patterns section of index.md
        self._update_index_patterns(patterns_dir)
        result.index_updated = True

        return result

    # ------------------------------------------------------------------
    # Phase B public API
    # ------------------------------------------------------------------

    def ingest_bug(
        self,
        bug_type: str,
        confidence: float,
        evidence: list[str],
        error_class: str,
        failure_subtype: str,
        task_id: str,
        ip_type: str = "custom",
        log_path: str = "",
    ) -> WikiIngestResult:
        """Create a new bug page in ``bugs/{TYPE}_{date}_{seq:03d}.md``.

        Every call creates a *new* page (bugs are not merged on update).
        The page ID follows: ``{RTL|TB}_{YYYYMMDD}_{seq:03d}``.

        Args:
            bug_type: ``"RTL_BUG"`` or ``"TB_BUG"``.
            confidence: Classification confidence score (0.0-1.0).
            evidence: Bullet-point evidence strings from BugClassifierAgent.
            error_class: Top-level error class from LogAnalyzerAgent.
            failure_subtype: Granular subtype from LogAnalyzerAgent.
            task_id: Task identifier used in citation and log.
            ip_type: IP type (``"axi"``, ``"pcie"``, ``"ddr"``, ``"custom"``).
            log_path: Path to the simulation log (for citation).

        Returns:
            :class:`WikiIngestResult` describing what was written.
        """
        result = WikiIngestResult(task_id=task_id)
        bugs_dir = self.cfg.wiki_dir / "bugs"
        bugs_dir.mkdir(parents=True, exist_ok=True)

        today = today_str()
        prefix = "RTL" if bug_type == "RTL_BUG" else "TB"
        date_str = today.replace("-", "")
        seq = self._next_bug_seq(bugs_dir, prefix, date_str)
        bug_id = f"{prefix}_{date_str}_{seq:03d}"
        page_path = bugs_dir / f"{bug_id}.md"

        frontmatter: dict[str, Any] = {
            "id": bug_id,
            "type": bug_type,
            "status": "open",
            "confidence": round(confidence, 4),
            "first_seen": today,
            "last_updated": today,
            "task_ids": [task_id],
            "error_class": error_class,
            "failure_subtype": failure_subtype,
            "ip_type": ip_type,
        }

        evidence_lines = "\n".join(f"- {e}" for e in evidence) if evidence else "- (none)"
        log_ref = f"(source: log: {log_path})" if log_path else ""
        body = _BUG_BODY_TEMPLATE.format(
            bug_id=bug_id,
            bug_type=bug_type,
            evidence_lines=evidence_lines,
            log_ref=log_ref,
        )
        atomic_write(page_path, serialize_page(frontmatter, body))
        rel = str(page_path.relative_to(self.cfg.wiki_dir))
        result.pages_created.append(rel)
        logger.info("Wiki: created bug page %s", bug_id)

        # Refresh search index (non-fatal)
        try:
            idx = self._get_search_index()
            idx.update(page_path, page_path.read_text(encoding="utf-8"))
            result.search_index_updated = True
        except Exception:
            logger.debug("Wiki: search index update failed (non-fatal)", exc_info=True)

        # Append to log.md
        log_entry = self._build_bug_log_entry(bug_id, bug_type, task_id, result)
        result.log_entry = log_entry
        self._append_log(log_entry)

        # Regenerate bugs section of index.md
        self._update_index_bugs(bugs_dir)
        result.index_updated = True

        return result

    # ------------------------------------------------------------------
    # Phase C public API
    # ------------------------------------------------------------------

    def ingest_coverage_hole(
        self,
        covergroup: str,
        bin_name: str,
        action_class: str,
        scenario: str,
        filled: bool,
        task_id: str,
    ) -> WikiIngestResult:
        """Create or update coverage/{covergroup}_{bin_name}.md."""
        result = WikiIngestResult(task_id=task_id)
        cov_dir = self.cfg.wiki_dir / "coverage"
        cov_dir.mkdir(parents=True, exist_ok=True)

        page_id = f"{covergroup}_{bin_name}"
        page_path = cov_dir / f"{page_id}.md"
        today = today_str()

        frontmatter: dict[str, Any] = {
            "type": "COVERAGE_HOLE",
            "covergroup": covergroup,
            "bin": bin_name,
            "action_class": action_class,
            "filled": filled,
            "last_updated": today,
            "task_id": task_id,
        }
        body = f"## Scenario\n{scenario}\n"

        if page_path.exists():
            old_fm, old_body = parse_page(page_path.read_text(encoding="utf-8"))
            frontmatter["first_seen"] = old_fm.get("first_seen", today)
            body = old_body.rstrip() + f"\n\n## Update [{today}] (Task: {task_id})\n{scenario}\n"
            result.pages_updated.append(f"coverage/{page_path.name}")
        else:
            frontmatter["first_seen"] = today
            result.pages_created.append(f"coverage/{page_path.name}")

        atomic_write(page_path, serialize_page(frontmatter, body))
        logger.info("Wiki: ingested coverage hole %s", page_path.name)

        # Search index
        try:
            idx = self._get_search_index()
            idx.update(page_path, page_path.read_text(encoding="utf-8"))
            result.search_index_updated = True
        except Exception:
            logger.debug("Wiki: search index update failed (non-fatal)")

        # log.md
        log_entry = self._build_coverage_log_entry(page_id, task_id, result)
        result.log_entry = log_entry
        self._append_log(log_entry)

        # index.md
        self._update_index_coverage(cov_dir)
        result.index_updated = True

        return result

    def ingest_session(
        self,
        session_report: str,
        failure_summary: str | None,
        classification: str | None,
        coverage_summary: str | None,
        task_id: str,
    ) -> WikiIngestResult:
        """Heuristically dispatch to pattern, bug, and coverage ingestion based on session data."""
        result = WikiIngestResult(task_id=task_id)

        error_class = "unknown"
        failure_subtype = "unknown"

        # Pattern parsing
        if failure_summary:
            for line in failure_summary.splitlines():
                if line.startswith("error_class:"):
                    error_class = line.split(":", 1)[1].strip()
                elif line.startswith("failure_subtype:"):
                    failure_subtype = line.split(":", 1)[1].strip()

            if failure_subtype != "unknown":
                p_res = self.ingest_pattern(
                    failure_subtype=failure_subtype,
                    error_class=error_class,
                    context_lines=[],
                    fix_applied=None,
                    success=False,
                    task_id=task_id,
                )
                result.pages_created.extend(p_res.pages_created)
                result.pages_updated.extend(p_res.pages_updated)

        # Bug parsing
        if classification and "BUG_TYPE" in classification:
            bug_type = "UNKNOWN"
            confidence = 0.0
            import re

            m_type = re.search(r"BUG_TYPE\s*:\s*(\w+)", classification)
            if m_type:
                bug_type = m_type.group(1)
            m_conf = re.search(r"CONFIDENCE\s*:\s*([0-9\.]+)", classification)
            if m_conf:
                import contextlib

                with contextlib.suppress(ValueError):
                    confidence = float(m_conf.group(1))
            if bug_type != "UNKNOWN":
                b_res = self.ingest_bug(
                    bug_type=bug_type,
                    confidence=confidence,
                    evidence=["Extracted from session"],
                    error_class=error_class,
                    failure_subtype=failure_subtype,
                    task_id=task_id,
                )
                result.pages_created.extend(b_res.pages_created)
                result.pages_updated.extend(b_res.pages_updated)

        # Append session report to log
        entry = f"## [{today_str()}] SESSION_REPORT | {task_id}\n\n{session_report}"
        self._append_log(entry)
        result.log_entry = entry

        return result

    # ------------------------------------------------------------------
    # Private — page creation / update
    # ------------------------------------------------------------------

    def _create_pattern_page(
        self,
        page_path: Path,
        pattern_id: str,
        error_class: str,
        context_lines: list[str],
        fix_applied: str | None,
        success: bool,
        task_id: str,
        today: str,
        result: WikiIngestResult,
    ) -> WikiIngestResult:
        """Write a new pattern page from the template."""
        fix_str = fix_applied or "—"
        fix_result = "PASS" if success else "—"
        first_row = f"| {today} | {task_id} | {fix_str} | {fix_result} |"
        signature = "\n".join(context_lines[:3]) if context_lines else "(see log)"

        frontmatter: dict[str, Any] = {
            "pattern_id": pattern_id,
            "error_class": error_class,
            "failure_subtype": pattern_id,
            "hit_count": 1,
            "first_seen": today,
            "last_seen": today,
            "fix_success_rate": None,
            "_success_count": 1 if (fix_applied and success) else 0,
        }
        body = _PATTERN_BODY_TEMPLATE.format(
            pattern_id=pattern_id,
            signature=signature,
            first_row=first_row,
        )
        atomic_write(page_path, serialize_page(frontmatter, body))
        rel = str(page_path.relative_to(self.cfg.wiki_dir))
        result.pages_created.append(rel)
        logger.info("Wiki: created pattern page %s", page_path.name)
        return result

    def _update_pattern_page(
        self,
        page_path: Path,
        fix_applied: str | None,
        success: bool,
        task_id: str,
        today: str,
        result: WikiIngestResult,
    ) -> WikiIngestResult:
        """Increment ``hit_count``, update ``last_seen``, append history row."""
        content = page_path.read_text(encoding="utf-8")
        frontmatter, body = parse_page(content)

        # --- update counters ---
        hit_count: int = int(frontmatter.get("hit_count", 0)) + 1
        frontmatter["hit_count"] = hit_count
        frontmatter["last_seen"] = today

        # Recalculate fix_success_rate when a fix was actually provided
        if fix_applied is not None:
            successes: int = int(frontmatter.get("_success_count", 0)) + (1 if success else 0)
            frontmatter["_success_count"] = successes
            frontmatter["fix_success_rate"] = round(successes / hit_count, 2)

        # --- append resolution history row ---
        fix_str = fix_applied or "—"
        fix_result = "PASS" if success else "—"
        new_row = f"| {today} | {task_id} | {fix_str} | {fix_result} |"
        body = body.rstrip() + f"\n{new_row}\n"

        atomic_write(page_path, serialize_page(frontmatter, body))
        rel = str(page_path.relative_to(self.cfg.wiki_dir))
        result.pages_updated.append(rel)
        logger.info("Wiki: updated pattern page %s (hit_count=%d)", page_path.name, hit_count)
        return result

    # ------------------------------------------------------------------
    # Private — log.md
    # ------------------------------------------------------------------

    @staticmethod
    def _build_log_entry(
        task_id: str,
        error_class: str,
        failure_subtype: str,
        fix_applied: str | None,
        success: bool,
        result: WikiIngestResult,
    ) -> str:
        today = today_str()
        fix_str = fix_applied or "—"
        lines = [
            f"## [{today}] ingest_pattern | {task_id} | {failure_subtype}",
            f"- error_class: {error_class}",
            f"- failure_subtype: {failure_subtype}",
            f"- fix_applied: {fix_str}",
            f"- success: {success}",
            "- wiki_pages_updated:",
        ]
        for p in result.pages_created + result.pages_updated:
            lines.append(f"    - {p}")
        return "\n".join(lines)

    def _append_log(self, entry: str) -> None:
        """Append *entry* to ``log.md``.  **Never** truncates or modifies
        existing content — ``log.md`` is strictly append-only.
        """
        log_path = self.cfg.wiki_dir / "log.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if not log_path.exists():
            header = "# DV Agentic Wiki Operation Log\n\n"
            atomic_write(log_path, header + entry + "\n")
        else:
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write("\n" + entry + "\n")

    # ------------------------------------------------------------------
    # Private — index.md regeneration
    # ------------------------------------------------------------------

    def _update_index_patterns(self, patterns_dir: Path) -> None:
        """Regenerate the Patterns table inside ``wiki/index.md``."""
        index_path = self.cfg.wiki_dir / "index.md"
        rows: list[str] = []

        for page in sorted(patterns_dir.glob("*.md")):
            if page.name.startswith("_"):
                continue
            try:
                fm, _ = parse_page(page.read_text(encoding="utf-8"))
                pid = fm.get("pattern_id", page.stem)
                hits = fm.get("hit_count", 0)
                rate = fm.get("fix_success_rate")
                rate_str = f"{rate:.0%}" if isinstance(rate, int | float) else "N/A"
                link = f"patterns/{page.name}"
                rows.append(f"| [{pid}]({link}) | {pid} | {hits} | {rate_str} |")
            except Exception:
                logger.debug("Wiki: could not parse pattern page %s", page)

        section = (
            f"## Patterns ({len(rows)} pages)\n"
            "| Page | failure_subtype | hit_count | fix_success_rate |\n"
            "|------|----------------|-----------|------------------|\n"
        )
        section += ("\n".join(rows) if rows else "| — | — | — | — |") + "\n"

        if not index_path.exists():
            content = (
                "# DV Agentic Wiki Index\n\n"
                f"Last updated: {now_iso()} | Total pages: {len(rows)}\n\n" + section
            )
            atomic_write(index_path, content)
            return

        existing = index_path.read_text(encoding="utf-8")
        if "## Patterns" in existing:
            before = existing[: existing.index("## Patterns")]
            rest = existing[existing.index("## Patterns") :]
            next_h2 = rest.find("\n## ", 4)
            after = rest[next_h2:] if next_h2 != -1 else ""
            new_content = before + section + after
        else:
            new_content = existing.rstrip() + "\n\n" + section

        atomic_write(index_path, new_content)

    # ------------------------------------------------------------------
    # Private — search index (lazy init)
    # ------------------------------------------------------------------

    def _get_search_index(self) -> Any:
        if self._search_index is None:
            from .search import WikiSearchIndex

            self._search_index = WikiSearchIndex.create(self.cfg.search_backend, self.cfg.wiki_dir)
            if self.cfg.wiki_dir.is_dir():
                self._search_index.build(self.cfg.wiki_dir)
        return self._search_index

    # ------------------------------------------------------------------
    # Private — Phase B helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _next_bug_seq(bugs_dir: Path, prefix: str, date_str: str) -> int:
        """Return the next available sequence number for today's bug pages.

        Scans existing ``{PREFIX}_{date_str}_NNN.md`` files and returns
        ``max_seq + 1``, or ``1`` if none exist.
        """
        import re

        pattern = re.compile(rf"^{re.escape(prefix)}_{re.escape(date_str)}_(\d{{3}})\.md$")
        max_seq = 0
        for p in bugs_dir.glob(f"{prefix}_{date_str}_*.md"):
            m = pattern.match(p.name)
            if m:
                max_seq = max(max_seq, int(m.group(1)))
        return max_seq + 1

    @staticmethod
    def _build_bug_log_entry(
        bug_id: str,
        bug_type: str,
        task_id: str,
        result: WikiIngestResult,
    ) -> str:
        today = today_str()
        lines = [
            f"## [{today}] ingest_bug | {task_id} | {bug_id}",
            f"- type: {bug_type}",
            f"- task_id: {task_id}",
            "- wiki_pages_updated:",
        ]
        for p in result.pages_created + result.pages_updated:
            lines.append(f"    - {p}")
        return "\n".join(lines)

    def _update_index_bugs(self, bugs_dir: Path) -> None:
        """Regenerate the Bugs table inside ``wiki/index.md``."""
        index_path = self.cfg.wiki_dir / "index.md"
        rows: list[str] = []

        for page in sorted(bugs_dir.glob("*.md")):
            if page.name.startswith("_"):
                continue
            try:
                fm, _ = parse_page(page.read_text(encoding="utf-8"))
                bug_id = fm.get("id", page.stem)
                btype = fm.get("type", "?")
                status = fm.get("status", "?")
                conf = fm.get("confidence", "?")
                last_upd = fm.get("last_updated", "?")
                link = f"bugs/{page.name}"
                rows.append(f"| [{bug_id}]({link}) | {btype} | {status} | {conf} | {last_upd} |")
            except Exception:
                logger.debug("Wiki: could not parse bug page %s", page)

        section = (
            f"## Bugs ({len(rows)} pages)\n"
            "| Page | Type | Status | Confidence | Last Updated |\n"
            "|------|------|--------|------------|--------------|\n"
        )
        section += ("\n".join(rows) if rows else "| — | — | — | — | — |") + "\n"

        if not index_path.exists():
            content = (
                "# DV Agentic Wiki Index\n\n"
                f"Last updated: {now_iso()} | Total pages: {len(rows)}\n\n" + section
            )
            atomic_write(index_path, content)
            return

        existing = index_path.read_text(encoding="utf-8")
        if "## Bugs" in existing:
            before = existing[: existing.index("## Bugs")]
            rest = existing[existing.index("## Bugs") :]
            next_h2 = rest.find("\n## ", 4)
            after = rest[next_h2:] if next_h2 != -1 else ""
            new_content = before + section + after
        else:
            new_content = existing.rstrip() + "\n\n" + section

        atomic_write(index_path, new_content)

    @staticmethod
    def _build_coverage_log_entry(
        page_id: str,
        task_id: str,
        result: WikiIngestResult,
    ) -> str:
        today = today_str()
        lines = [
            f"## [{today}] ingest_coverage_hole | {task_id} | {page_id}",
            f"- task_id: {task_id}",
            "- wiki_pages_updated:",
        ]
        for p in result.pages_created + result.pages_updated:
            lines.append(f"    - {p}")
        return "\n".join(lines)

    def _update_index_coverage(self, cov_dir: Path) -> None:
        """Regenerate the Coverage table inside ``wiki/index.md``."""
        index_path = self.cfg.wiki_dir / "index.md"
        rows: list[str] = []

        for page in sorted(cov_dir.glob("*.md")):
            if page.name.startswith("_"):
                continue
            try:
                fm, _ = parse_page(page.read_text(encoding="utf-8"))
                cg = fm.get("covergroup", "?")
                b_name = fm.get("bin", "?")
                acls = fm.get("action_class", "?")
                filled = fm.get("filled", "?")
                link = f"coverage/{page.name}"
                rows.append(f"| [{cg}_{b_name}]({link}) | {cg} | {b_name} | {acls} | {filled} |")
            except Exception:
                logger.debug("Wiki: could not parse coverage page %s", page)

        section = (
            f"## Coverage Holes ({len(rows)} pages)\n"
            "| Page | Covergroup | Bin | Action Class | Filled |\n"
            "|------|------------|-----|--------------|--------|\n"
        )
        section += ("\n".join(rows) if rows else "| — | — | — | — | — |") + "\n"

        if not index_path.exists():
            content = (
                "# DV Agentic Wiki Index\n\n"
                f"Last updated: {now_iso()} | Total pages: {len(rows)}\n\n" + section
            )
            atomic_write(index_path, content)
            return

        existing = index_path.read_text(encoding="utf-8")
        if "## Coverage Holes" in existing:
            before = existing[: existing.index("## Coverage Holes")]
            rest = existing[existing.index("## Coverage Holes") :]
            next_h2 = rest.find("\n## ", 4)
            after = rest[next_h2:] if next_h2 != -1 else ""
            new_content = before + section + after
        else:
            new_content = existing.rstrip() + "\n\n" + section

        atomic_write(index_path, new_content)
