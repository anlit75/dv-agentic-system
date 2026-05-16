# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Wiki configuration and shared page utilities.

All page I/O uses atomic_write() (temp-file + os.replace) to prevent
partial writes from corrupting the knowledge base.

Exported symbols used by other wiki sub-modules:
  WikiConfig       — configuration parsed from project.yaml wiki: block
  load_wiki_config — convenience parser (no changes to existing load_project())
  parse_page       — split YAML frontmatter + body
  serialize_page   — join frontmatter dict + body back to markdown
  atomic_write     — safe file write
  today_str        — YYYY-MM-DD helper
  now_iso          — UTC ISO-8601 helper
"""

from __future__ import annotations

import contextlib
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class WikiConfig:
    """Wiki integration configuration parsed from project.yaml ``wiki:`` block.

    Attributes:
        enabled: Whether wiki integration is active.  Defaults to ``False``
            so all existing projects are unaffected until they opt in.
        wiki_dir: Root directory for wiki Markdown files.
        max_context_tokens: Total token budget for wiki context injected
            into agent system prompts via PromptLoader.
        auto_ingest: Whether ReporterAgent auto-triggers ingest after each run.
        search_backend: Search implementation (``"bm25"`` | ``"none"``).
        lint_on_startup: Whether OrchestratorAgent runs a quick lint check
            on session startup.
        lint_interval_sessions: Full lint trigger interval (every N sessions).
        pattern_context_tokens: Token budget for ``{{KNOWN_ERROR_PATTERNS}}``.
        bug_context_tokens: Token budget for ``{{KNOWN_RTL_BUGS}}``.
        coverage_context_tokens: Token budget for ``{{COVERAGE_HOLE_HISTORY}}``.
        summary_context_tokens: Token budget for ``{{WIKI_PATTERN_SUMMARY}}``.
    """

    enabled: bool = False
    wiki_dir: Path = field(default_factory=lambda: Path(".agent/wiki"))
    max_context_tokens: int = 2000
    auto_ingest: bool = True
    search_backend: str = "bm25"
    lint_on_startup: bool = True
    lint_interval_sessions: int = 10
    pattern_context_tokens: int = 500
    bug_context_tokens: int = 500
    coverage_context_tokens: int = 500
    summary_context_tokens: int = 500


def load_wiki_config(
    project_yaml_path: str | Path = ".agent/project.yaml",
) -> WikiConfig:
    """Parse ``WikiConfig`` from the ``wiki:`` block in *project_yaml_path*.

    This is a standalone parser that does **not** change the existing
    ``load_project()`` return signature.  Call it independently wherever
    wiki awareness is needed (CLI, PromptLoader, Orchestrator).

    Args:
        project_yaml_path: Path to ``.agent/project.yaml``.

    Returns:
        Populated :class:`WikiConfig`.  Returns a disabled config (``enabled=False``)
        if the file does not exist or ``wiki.enabled`` is absent / false.
    """
    path = Path(project_yaml_path)
    if not path.exists():
        return WikiConfig(enabled=False)

    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        logger.warning("load_wiki_config: failed to parse %s", path)
        return WikiConfig(enabled=False)

    if not isinstance(raw, dict):
        return WikiConfig(enabled=False)

    section: dict[str, Any] = raw.get("wiki") or {}
    if not section.get("enabled", False):
        return WikiConfig(enabled=False)

    def _get(key: str, default: Any) -> Any:
        return section.get(key, default)

    wiki_dir_str: str = _get("wiki_dir", ".agent/wiki")
    return WikiConfig(
        enabled=True,
        wiki_dir=Path(wiki_dir_str),
        max_context_tokens=int(_get("max_context_tokens", 2000)),
        auto_ingest=bool(_get("auto_ingest", True)),
        search_backend=str(_get("search_backend", "bm25")),
        lint_on_startup=bool(_get("lint_on_startup", True)),
        lint_interval_sessions=int(_get("lint_interval_sessions", 10)),
        pattern_context_tokens=int(_get("pattern_context_tokens", 500)),
        bug_context_tokens=int(_get("bug_context_tokens", 500)),
        coverage_context_tokens=int(_get("coverage_context_tokens", 500)),
        summary_context_tokens=int(_get("summary_context_tokens", 500)),
    )


# ---------------------------------------------------------------------------
# Page I/O utilities
# ---------------------------------------------------------------------------


def parse_page(content: str) -> tuple[dict[str, Any], str]:
    """Split a wiki Markdown page into its YAML frontmatter and body.

    Args:
        content: Raw file content starting with an optional ``---`` block.

    Returns:
        ``(frontmatter_dict, body_str)``.  If no valid frontmatter is found,
        returns ``({}, content)``.

    Example::

        fm, body = parse_page(path.read_text())
        hit_count = fm.get("hit_count", 0)
    """
    if not content.startswith("---"):
        return {}, content

    try:
        closing = content.index("\n---", 3)
    except ValueError:
        return {}, content

    frontmatter_str = content[3:closing].strip()
    body = content[closing + 4 :].strip()  # skip the "\n---" (4 chars)

    try:
        frontmatter: dict[str, Any] = yaml.safe_load(frontmatter_str) or {}
    except yaml.YAMLError:
        logger.warning("parse_page: YAML frontmatter parse error; treating as no frontmatter")
        return {}, content

    return frontmatter, body


def serialize_page(frontmatter: dict[str, Any], body: str) -> str:
    """Combine *frontmatter* and *body* into a Markdown page string.

    Args:
        frontmatter: Key-value pairs to encode as YAML front matter.
        body: Markdown body text (must not start with ``---``).

    Returns:
        Complete page content with ``---`` delimited YAML front matter.
    """
    fm_str = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    return f"---\n{fm_str}---\n\n{body.strip()}\n"


def atomic_write(path: Path, content: str) -> None:
    """Write *content* to *path* atomically (temp-file + ``Path.replace``).

    Creates parent directories if they do not exist.  Ensures readers
    never see a partial write.

    Args:
        path: Destination file path.
        content: UTF-8 text to write.

    Raises:
        OSError: If the write or rename fails.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".wiki.tmp")
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        tmp_path.replace(path)
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


def today_str() -> str:
    """Return today's date as ``YYYY-MM-DD`` (local time)."""
    return date.today().isoformat()


def now_iso() -> str:
    """Return current UTC datetime as ISO-8601 (``YYYY-MM-DDTHH:MM:SSZ``)."""
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
