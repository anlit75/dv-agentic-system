# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from dv_agentic.wiki.lint import WikiLintService
from dv_agentic.wiki.manager import WikiConfig


@pytest.fixture
def wiki_cfg(tmp_path: Path) -> WikiConfig:
    """Provides a temporary wiki directory configuration."""
    cfg = WikiConfig(enabled=True, wiki_dir=tmp_path / ".agent" / "wiki")
    cfg.wiki_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def test_lint_clean(wiki_cfg: WikiConfig) -> None:
    svc = WikiLintService(wiki_cfg)
    report = svc.run()
    assert report.is_clean()


def test_orphan_pages(wiki_cfg: WikiConfig) -> None:
    (wiki_cfg.wiki_dir / "index.md").write_text("No links", encoding="utf-8")

    bugs_dir = wiki_cfg.wiki_dir / "bugs"
    bugs_dir.mkdir()
    (bugs_dir / "orphan.md").write_text("orphan", encoding="utf-8")

    svc = WikiLintService(wiki_cfg)
    report = svc.run()
    assert not report.is_clean()
    assert "bugs/orphan.md" in report.orphan_pages
    assert report.human_review_required


def test_missing_pages(wiki_cfg: WikiConfig) -> None:
    (wiki_cfg.wiki_dir / "index.md").write_text("[bug](bugs/missing.md)", encoding="utf-8")

    svc = WikiLintService(wiki_cfg)
    report = svc.run()
    assert not report.is_clean()
    assert "bugs/missing.md" in report.missing_pages
    assert report.human_review_required


def test_stale_open_bugs(wiki_cfg: WikiConfig) -> None:
    (wiki_cfg.wiki_dir / "index.md").write_text("[bug](bugs/stale.md)", encoding="utf-8")
    bugs_dir = wiki_cfg.wiki_dir / "bugs"
    bugs_dir.mkdir()

    old_date = (datetime.now(UTC) - timedelta(days=95)).strftime("%Y-%m-%d")

    content = f"""---
status: open
first_seen: {old_date}
---
body
"""
    (bugs_dir / "stale.md").write_text(content, encoding="utf-8")

    svc = WikiLintService(wiki_cfg)
    report = svc.run()
    assert "bugs/stale.md" in report.stale_open_bugs


def test_broken_links_full_depth(wiki_cfg: WikiConfig) -> None:
    (wiki_cfg.wiki_dir / "index.md").write_text("[pat](patterns/pat1.md)", encoding="utf-8")
    pat_dir = wiki_cfg.wiki_dir / "patterns"
    pat_dir.mkdir()

    (pat_dir / "pat1.md").write_text("link to [pat2](pat2.md)", encoding="utf-8")

    svc = WikiLintService(wiki_cfg)
    report = svc.run(depth="full")
    assert ("patterns/pat1.md", "pat2.md") in report.broken_links
    assert report.human_review_required


def test_uncited_claims_full_depth(wiki_cfg: WikiConfig) -> None:
    (wiki_cfg.wiki_dir / "index.md").write_text("[bug](bugs/b1.md)", encoding="utf-8")
    bugs_dir = wiki_cfg.wiki_dir / "bugs"
    bugs_dir.mkdir()

    content = """---
status: open
---
- It fails because of X.
"""
    (bugs_dir / "b1.md").write_text(content, encoding="utf-8")

    svc = WikiLintService(wiki_cfg)
    report = svc.run(depth="full")
    assert ("bugs/b1.md", 4) in report.uncited_claims
