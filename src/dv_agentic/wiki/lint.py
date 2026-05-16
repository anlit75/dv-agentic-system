# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Wiki linting service.

Checks the knowledge base for internal consistency.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from .manager import WikiConfig, parse_page

logger = logging.getLogger(__name__)


@dataclass
class LintReport:
    """Output report from a wiki linting run."""

    orphan_pages: list[str] = field(default_factory=list)
    broken_links: list[tuple[str, str]] = field(default_factory=list)
    stale_open_bugs: list[str] = field(default_factory=list)
    missing_pages: list[str] = field(default_factory=list)
    uncited_claims: list[tuple[str, int]] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    human_review_required: bool = False

    def is_clean(self) -> bool:
        return not (
            self.orphan_pages
            or self.broken_links
            or self.stale_open_bugs
            or self.missing_pages
            or self.uncited_claims
        )

    def to_str(self) -> str:
        lines = []
        if self.is_clean():
            return "Wiki is clean."

        if self.orphan_pages:
            lines.append("Orphan Pages:")
            for p in self.orphan_pages:
                lines.append(f"  - {p}")
        if self.missing_pages:
            lines.append("Missing Pages (listed in index.md but not on disk):")
            for p in self.missing_pages:
                lines.append(f"  - {p}")
        if self.broken_links:
            lines.append("Broken Links:")
            for src, target in self.broken_links:
                lines.append(f"  - {src} -> {target}")
        if self.stale_open_bugs:
            lines.append("Stale Open Bugs (>90 days):")
            for p in self.stale_open_bugs:
                lines.append(f"  - {p}")
        if self.uncited_claims:
            lines.append("Uncited Claims:")
            for p, ln in self.uncited_claims:
                lines.append(f"  - {p}:{ln}")
        if self.suggestions:
            lines.append("Suggestions:")
            for s in self.suggestions:
                lines.append(f"  - {s}")
        return "\n".join(lines)


class WikiLintService:
    """Periodically checks wiki consistency.

    Triggered by OrchestratorAgent (quick) or CLI (full).
    """

    def __init__(self, config: WikiConfig) -> None:
        self.config = config
        self.wiki_dir = config.wiki_dir

        self._link_re = re.compile(r"\[.*?\]\((.*?\.md)\)")
        # _claim_re identifies potential claims (list items) in patterns/bugs.
        # Citation validation (source:, task_id:) is performed during full lint.
        self._claim_re = re.compile(r"^(?:- |\* |\d+\.\s+)(.*?)$")

    def run(self, depth: Literal["quick", "full"] = "quick") -> LintReport:
        """Run lint checks.

        Args:
            depth: "quick" checks only index vs disk mapping and stale bugs.
                   "full" parses page contents for links and citations.
        """
        report = LintReport()
        if not self.config.enabled:
            return report

        if not self.wiki_dir.exists():
            return report

        index_path = self.wiki_dir / "index.md"
        indexed_pages = self._get_indexed_pages(index_path)
        actual_pages = self._get_actual_pages()

        # 1. Missing pages: in index, not on disk
        for p in indexed_pages:
            # indexed_pages might have relative paths like "bugs/..."
            if p not in actual_pages:
                report.missing_pages.append(p)
                report.human_review_required = True
                report.suggestions.append(f"Remove '{p}' from index.md or recreate the file.")

        # 2. Orphan pages: on disk, not in index
        # index.md and log.md are excluded from this check
        for p in actual_pages:
            if p not in indexed_pages and p not in ("index.md", "log.md"):
                report.orphan_pages.append(p)
                report.human_review_required = True
                report.suggestions.append(f"Add '{p}' to index.md or run 'dv-agentic wiki-build'.")

        # 3. Stale open bugs
        bugs_dir = self.wiki_dir / "bugs"
        if bugs_dir.exists():
            now = datetime.now(UTC).date()
            for f in bugs_dir.glob("*.md"):
                try:
                    fm, _ = parse_page(f.read_text(encoding="utf-8"))
                    if fm.get("status") == "open" and "first_seen" in fm:
                        first_seen = fm["first_seen"]
                        if isinstance(first_seen, str):
                            dt = datetime.strptime(first_seen, "%Y-%m-%d").date()
                        else:
                            # Assume it's a date or datetime object from PyYAML
                            dt = getattr(first_seen, "date", lambda fs=first_seen: fs)()

                        if (now - dt).days > 90:
                            report.stale_open_bugs.append(f"bugs/{f.name}")
                except Exception as e:
                    logger.debug("Lint: Failed to parse %s for stale check: %s", f.name, e)

        if depth == "full":
            self._full_lint(actual_pages, report)

        return report

    def _full_lint(self, actual_pages: set[str], report: LintReport) -> None:
        for p in actual_pages:
            if p == "log.md":
                continue
            path = self.wiki_dir / p
            if not path.exists():
                continue

            try:
                content = path.read_text(encoding="utf-8")

                # Check broken links
                for match in self._link_re.finditer(content):
                    target = match.group(1)
                    # Resolve relative target if needed.
                    # Simple resolution since we only have flat subdirs
                    # (bugs/, patterns/, coverage/).
                    # If target is "bugs/foo.md", and p is "index.md", target works.
                    # If p is "bugs/bar.md" and target is "foo.md", relative to bugs/
                    if "/" not in target and "/" in p:
                        target = f"{p.split('/')[0]}/{target}"

                    if target not in actual_pages and target != "index.md" and target != "log.md":
                        report.broken_links.append((p, match.group(1)))
                        report.human_review_required = True

                # Check uncited claims (only in bugs and patterns)
                if p.startswith("bugs/") or p.startswith("patterns/"):
                    lines = content.splitlines()
                    for i, line in enumerate(lines, start=1):
                        # Very heuristic check: list items that don't have sources
                        if self._claim_re.match(line):
                            # If it's a claim, does it have citation?
                            lower = line.lower()
                            if ("because" in lower or "due to" in lower) and not any(
                                x in lower for x in ["source:", "task_id:", "log.md"]
                            ):
                                report.uncited_claims.append((p, i))
                                # Don't require human review for this, it's just a warning.

            except Exception:
                logger.debug("Lint: Failed to full-lint %s", p)

    def _get_indexed_pages(self, index_path: Path) -> set[str]:
        if not index_path.exists():
            return set()
        pages = set()
        content = index_path.read_text(encoding="utf-8")
        # index.md contains links like [label](bugs/foo.md)
        # we extract the relative paths
        link_re = re.compile(r"\[.*?\]\((.*?\.md)\)")
        for match in link_re.finditer(content):
            pages.add(match.group(1))
        return pages

    def _get_actual_pages(self) -> set[str]:
        pages = set()
        for root, _, files in os.walk(self.wiki_dir):
            root_path = Path(root)
            for f in files:
                if f.endswith(".md"):
                    rel = root_path.relative_to(self.wiki_dir) / f
                    # Use posixpath for consistency
                    pages.add(rel.as_posix())
        return pages
