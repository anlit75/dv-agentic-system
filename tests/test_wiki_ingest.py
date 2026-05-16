# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Unit tests for WikiIngestService (Phase A: ingest_pattern)."""

from __future__ import annotations

from pathlib import Path

import pytest

from dv_agentic.wiki.ingest import WikiIngestService
from dv_agentic.wiki.manager import WikiConfig, parse_page

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def cfg(tmp_path: Path) -> WikiConfig:
    """A WikiConfig pointing to a fresh temp directory."""
    return WikiConfig(
        enabled=True,
        wiki_dir=tmp_path / "wiki",
        search_backend="none",  # avoid bm25s dependency in unit tests
    )


@pytest.fixture()
def svc(cfg: WikiConfig) -> WikiIngestService:
    return WikiIngestService(cfg)


# ---------------------------------------------------------------------------
# ingest_pattern — first occurrence (create)
# ---------------------------------------------------------------------------


class TestIngestPatternCreate:
    def test_creates_patterns_directory(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        assert (cfg.wiki_dir / "patterns").is_dir()

    def test_creates_pattern_page(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        assert (cfg.wiki_dir / "patterns" / "missing_timescale.md").exists()

    def test_frontmatter_hit_count_is_one(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        content = (cfg.wiki_dir / "patterns" / "missing_timescale.md").read_text(encoding="utf-8")
        fm, _ = parse_page(content)
        assert fm["hit_count"] == 1

    def test_frontmatter_pattern_id(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        svc.ingest_pattern("unmatched_block", "compile_error", [], None, False, "t1")
        content = (cfg.wiki_dir / "patterns" / "unmatched_block.md").read_text(encoding="utf-8")
        fm, _ = parse_page(content)
        assert fm["pattern_id"] == "unmatched_block"

    def test_frontmatter_error_class(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        svc.ingest_pattern("scoreboard_fail", "uvm_error", [], None, False, "t1")
        content = (cfg.wiki_dir / "patterns" / "scoreboard_fail.md").read_text(encoding="utf-8")
        fm, _ = parse_page(content)
        assert fm["error_class"] == "uvm_error"

    def test_first_seen_equals_today(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        from dv_agentic.wiki.manager import today_str

        svc.ingest_pattern("width_mismatch", "compile_error", [], None, False, "t1")
        content = (cfg.wiki_dir / "patterns" / "width_mismatch.md").read_text(encoding="utf-8")
        fm, _ = parse_page(content)
        assert fm["first_seen"] == today_str()

    def test_context_lines_appear_in_signature(
        self, svc: WikiIngestService, cfg: WikiConfig
    ) -> None:
        ctx = ["*E,NOTIME (tb/seq.sv,1): `timescale not defined"]
        svc.ingest_pattern("missing_timescale", "compile_error", ctx, None, False, "t1")
        content = (cfg.wiki_dir / "patterns" / "missing_timescale.md").read_text(encoding="utf-8")
        assert "`timescale" in content

    def test_result_reports_page_created(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        assert len(result.pages_created) == 1
        assert "missing_timescale.md" in result.pages_created[0]
        assert result.pages_updated == []

    def test_result_task_id(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = svc.ingest_pattern(
            "missing_timescale", "compile_error", [], None, False, "task_99"
        )
        assert result.task_id == "task_99"


# ---------------------------------------------------------------------------
# ingest_pattern — second occurrence (update)
# ---------------------------------------------------------------------------


class TestIngestPatternUpdate:
    def test_hit_count_increments_on_second_call(
        self, svc: WikiIngestService, cfg: WikiConfig
    ) -> None:
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t2")
        content = (cfg.wiki_dir / "patterns" / "missing_timescale.md").read_text(encoding="utf-8")
        fm, _ = parse_page(content)
        assert fm["hit_count"] == 2

    def test_hit_count_after_three_calls(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        for i in range(3):
            svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, f"t{i}")
        content = (cfg.wiki_dir / "patterns" / "missing_timescale.md").read_text(encoding="utf-8")
        fm, _ = parse_page(content)
        assert fm["hit_count"] == 3

    def test_result_reports_page_updated_not_created(
        self, svc: WikiIngestService, cfg: WikiConfig
    ) -> None:
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        result = svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t2")
        assert result.pages_created == []
        assert len(result.pages_updated) == 1

    def test_fix_success_rate_calculated_when_fix_applied(
        self, svc: WikiIngestService, cfg: WikiConfig
    ) -> None:
        # First call: no fix
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        # Second call: fix applied and succeeded
        svc.ingest_pattern("missing_timescale", "compile_error", [], "add timescale", True, "t2")
        content = (cfg.wiki_dir / "patterns" / "missing_timescale.md").read_text(encoding="utf-8")
        fm, _ = parse_page(content)
        assert fm["fix_success_rate"] is not None

    def test_resolution_history_row_appended(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        svc.ingest_pattern("missing_timescale", "compile_error", [], "add timescale", True, "t2")
        content = (cfg.wiki_dir / "patterns" / "missing_timescale.md").read_text(encoding="utf-8")
        assert "t2" in content
        assert "add timescale" in content


# ---------------------------------------------------------------------------
# log.md
# ---------------------------------------------------------------------------


class TestLogMd:
    def test_log_md_created_on_first_ingest(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        assert (cfg.wiki_dir / "log.md").exists()

    def test_log_md_contains_task_id(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "task_42")
        log = (cfg.wiki_dir / "log.md").read_text(encoding="utf-8")
        assert "task_42" in log

    def test_log_md_is_append_only(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        first_content = (cfg.wiki_dir / "log.md").read_text(encoding="utf-8")

        svc.ingest_pattern("unmatched_block", "compile_error", [], None, False, "t2")
        second_content = (cfg.wiki_dir / "log.md").read_text(encoding="utf-8")

        # All content from first write must still be present
        assert first_content.rstrip() in second_content
        # Second write added new content
        assert "unmatched_block" in second_content
        assert "missing_timescale" in second_content

    def test_log_md_contains_failure_subtype(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        svc.ingest_pattern("width_mismatch", "compile_error", [], None, False, "t1")
        log = (cfg.wiki_dir / "log.md").read_text(encoding="utf-8")
        assert "width_mismatch" in log


# ---------------------------------------------------------------------------
# index.md
# ---------------------------------------------------------------------------


class TestIndexMd:
    def test_index_md_created_after_ingest(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        assert (cfg.wiki_dir / "index.md").exists()

    def test_index_md_contains_pattern_link(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        index = (cfg.wiki_dir / "index.md").read_text()
        assert "missing_timescale" in index
        assert "patterns/missing_timescale.md" in index

    def test_index_md_hit_count_updated(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        for i in range(3):
            svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, f"t{i}")
        index = (cfg.wiki_dir / "index.md").read_text()
        assert "3" in index  # hit_count=3 should appear in the table


# ---------------------------------------------------------------------------
# Atomic write — no partial files on failure
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    def test_no_partial_file_on_write_failure(
        self, svc: WikiIngestService, cfg: WikiConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If os.replace raises, the temp file is cleaned up and
        the original page (if any) remains intact."""
        import os as _os

        def fail_replace(src: str, dst: str) -> None:
            Path(src).unlink()
            raise OSError("Simulated disk full")

        # First ingest succeeds
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        original_content = (cfg.wiki_dir / "patterns" / "missing_timescale.md").read_text(
            encoding="utf-8"
        )

        monkeypatch.setattr(_os, "replace", fail_replace)

        # Second ingest fails atomically
        with pytest.raises(OSError, match="Simulated disk full"):
            svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t2")

        # Original content untouched
        current_content = (cfg.wiki_dir / "patterns" / "missing_timescale.md").read_text(
            encoding="utf-8"
        )
        assert current_content == original_content

    def test_no_tmp_files_left_after_success(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        tmp_files = list((cfg.wiki_dir / "patterns").glob("*.wiki.tmp"))
        assert tmp_files == []


# ---------------------------------------------------------------------------
# Multiple subtypes
# ---------------------------------------------------------------------------


class TestMultipleSubtypes:
    def test_different_subtypes_create_separate_pages(
        self, svc: WikiIngestService, cfg: WikiConfig
    ) -> None:
        svc.ingest_pattern("missing_timescale", "compile_error", [], None, False, "t1")
        svc.ingest_pattern("unmatched_block", "compile_error", [], None, False, "t2")
        svc.ingest_pattern("scoreboard_fail", "uvm_error", [], None, False, "t3")

        pages = list((cfg.wiki_dir / "patterns").glob("*.md"))
        names = {p.stem for p in pages}
        assert "missing_timescale" in names
        assert "unmatched_block" in names
        assert "scoreboard_fail" in names

    def test_index_lists_all_patterns(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        subtypes = ["missing_timescale", "unmatched_block", "width_mismatch"]
        for st in subtypes:
            svc.ingest_pattern(st, "compile_error", [], None, False, "t1")
        index = (cfg.wiki_dir / "index.md").read_text()
        for st in subtypes:
            assert st in index
