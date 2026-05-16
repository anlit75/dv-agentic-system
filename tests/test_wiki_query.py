# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Unit tests for WikiQueryService (Phase A)."""

from __future__ import annotations

from pathlib import Path

import pytest

from dv_agentic.wiki.ingest import WikiIngestService
from dv_agentic.wiki.manager import WikiConfig
from dv_agentic.wiki.query import WikiQueryService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def cfg(tmp_path: Path) -> WikiConfig:
    return WikiConfig(
        enabled=True,
        wiki_dir=tmp_path / "wiki",
        search_backend="none",
        pattern_context_tokens=500,
    )


@pytest.fixture()
def svc(cfg: WikiConfig) -> WikiIngestService:
    return WikiIngestService(cfg)


@pytest.fixture()
def query(cfg: WikiConfig) -> WikiQueryService:
    return WikiQueryService(cfg)


def _populate(svc: WikiIngestService, subtype: str, error_class: str, hits: int) -> None:
    """Ingest *hits* occurrences of *subtype* so the page reflects them."""
    for i in range(hits):
        svc.ingest_pattern(subtype, error_class, [], None, False, f"task_{i}")


# ---------------------------------------------------------------------------
# get_known_error_patterns — empty wiki
# ---------------------------------------------------------------------------


class TestGetKnownErrorPatternsEmpty:
    def test_returns_empty_string_when_wiki_missing(self, query: WikiQueryService) -> None:
        assert query.get_known_error_patterns() == ""

    def test_returns_empty_string_when_patterns_dir_missing(self, cfg: WikiConfig) -> None:
        cfg.wiki_dir.mkdir(parents=True)
        q = WikiQueryService(cfg)
        assert q.get_known_error_patterns() == ""

    def test_returns_empty_string_when_patterns_dir_empty(self, cfg: WikiConfig) -> None:
        (cfg.wiki_dir / "patterns").mkdir(parents=True)
        q = WikiQueryService(cfg)
        assert q.get_known_error_patterns() == ""


# ---------------------------------------------------------------------------
# get_known_error_patterns — populated wiki
# ---------------------------------------------------------------------------


class TestGetKnownErrorPatternsPopulated:
    def test_returns_nonempty_string_when_patterns_exist(
        self, svc: WikiIngestService, query: WikiQueryService
    ) -> None:
        _populate(svc, "missing_timescale", "compile_error", 3)
        result = query.get_known_error_patterns()
        assert result != ""

    def test_result_contains_pattern_id(
        self, svc: WikiIngestService, query: WikiQueryService
    ) -> None:
        _populate(svc, "missing_timescale", "compile_error", 2)
        result = query.get_known_error_patterns()
        assert "missing_timescale" in result

    def test_result_contains_hit_count(
        self, svc: WikiIngestService, query: WikiQueryService
    ) -> None:
        _populate(svc, "missing_timescale", "compile_error", 5)
        result = query.get_known_error_patterns()
        assert "5" in result

    def test_result_contains_error_class(
        self, svc: WikiIngestService, query: WikiQueryService
    ) -> None:
        _populate(svc, "missing_timescale", "compile_error", 1)
        result = query.get_known_error_patterns()
        assert "compile_error" in result

    def test_result_contains_header(self, svc: WikiIngestService, query: WikiQueryService) -> None:
        _populate(svc, "missing_timescale", "compile_error", 1)
        result = query.get_known_error_patterns()
        assert "Known Error Patterns" in result

    def test_sorts_by_hit_count_descending(
        self, svc: WikiIngestService, query: WikiQueryService
    ) -> None:
        _populate(svc, "width_mismatch", "compile_error", 1)
        _populate(svc, "missing_timescale", "compile_error", 7)
        _populate(svc, "unmatched_block", "compile_error", 3)

        result = query.get_known_error_patterns()
        idx_ts = result.index("missing_timescale")
        idx_ub = result.index("unmatched_block")
        idx_wm = result.index("width_mismatch")

        assert idx_ts < idx_ub < idx_wm

    def test_top_k_limits_results(self, svc: WikiIngestService, query: WikiQueryService) -> None:
        subtypes = [
            "missing_timescale",
            "unmatched_block",
            "width_mismatch",
            "multiple_drivers",
            "mixed_assignment",
        ]
        for st in subtypes:
            _populate(svc, st, "compile_error", 1)

        result = query.get_known_error_patterns(top_k=2)
        # Only 2 pattern blocks expected (plus header)
        count = result.count("→ Fix template:")
        assert count == 2


# ---------------------------------------------------------------------------
# get_known_error_patterns — filtering
# ---------------------------------------------------------------------------


class TestGetKnownErrorPatternsFilter:
    def test_filter_by_error_class(self, svc: WikiIngestService, query: WikiQueryService) -> None:
        _populate(svc, "missing_timescale", "compile_error", 2)
        _populate(svc, "scoreboard_fail", "uvm_error", 2)

        result = query.get_known_error_patterns(error_class="compile_error")
        assert "missing_timescale" in result
        assert "scoreboard_fail" not in result

    def test_filter_by_failure_subtype(
        self, svc: WikiIngestService, query: WikiQueryService
    ) -> None:
        _populate(svc, "missing_timescale", "compile_error", 3)
        _populate(svc, "unmatched_block", "compile_error", 1)

        result = query.get_known_error_patterns(failure_subtype="missing_timescale")
        assert "missing_timescale" in result
        assert "unmatched_block" not in result

    def test_filter_returns_empty_when_no_match(
        self, svc: WikiIngestService, query: WikiQueryService
    ) -> None:
        _populate(svc, "missing_timescale", "compile_error", 2)
        result = query.get_known_error_patterns(error_class="uvm_fatal")
        assert result == ""


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------


class TestTokenBudget:
    def test_respects_pattern_context_tokens(self, tmp_path: Path) -> None:
        """Result must not substantially exceed the token budget."""
        tiny_cfg = WikiConfig(
            enabled=True,
            wiki_dir=tmp_path / "wiki",
            search_backend="none",
            pattern_context_tokens=50,  # very small budget
        )
        svc = WikiIngestService(tiny_cfg)
        q = WikiQueryService(tiny_cfg)

        # Ingest many patterns
        subtypes = [
            "missing_timescale",
            "unmatched_block",
            "width_mismatch",
            "multiple_drivers",
            "mixed_assignment",
            "interface_mismatch",
        ]
        for st in subtypes:
            _populate(svc, st, "compile_error", 1)

        result = q.get_known_error_patterns(top_k=10)
        # 50 tokens x 4 chars/token = 200 chars budget.
        # Some overflow is acceptable (the truncation message itself may push
        # slightly over), but result should be far less than the full corpus.
        assert len(result) < 600


# ---------------------------------------------------------------------------
# get_pattern_page
# ---------------------------------------------------------------------------


class TestGetPatternPage:
    def test_returns_page_content(self, svc: WikiIngestService, query: WikiQueryService) -> None:
        _populate(svc, "missing_timescale", "compile_error", 1)
        content = query.get_pattern_page("missing_timescale")
        assert content is not None
        assert "missing_timescale" in content

    def test_returns_none_for_nonexistent_pattern(self, query: WikiQueryService) -> None:
        assert query.get_pattern_page("no_such_pattern") is None

    def test_returned_content_has_frontmatter(
        self, svc: WikiIngestService, query: WikiQueryService
    ) -> None:
        from dv_agentic.wiki.manager import parse_page

        _populate(svc, "missing_timescale", "compile_error", 2)
        content = query.get_pattern_page("missing_timescale")
        assert content is not None
        fm, _ = parse_page(content)
        assert fm["hit_count"] == 2


# ---------------------------------------------------------------------------
# get_pattern_summary
# ---------------------------------------------------------------------------


class TestGetPatternSummary:
    def test_returns_empty_when_no_patterns(self, query: WikiQueryService) -> None:
        assert query.get_pattern_summary() == ""

    def test_returns_table_with_header(
        self, svc: WikiIngestService, query: WikiQueryService
    ) -> None:
        _populate(svc, "missing_timescale", "compile_error", 3)
        summary = query.get_pattern_summary()
        assert "Pattern" in summary
        assert "Hits" in summary

    def test_table_contains_all_patterns(
        self, svc: WikiIngestService, query: WikiQueryService
    ) -> None:
        subtypes = ["missing_timescale", "unmatched_block", "scoreboard_fail"]
        for st in subtypes:
            _populate(svc, st, "compile_error", 1)
        summary = query.get_pattern_summary()
        for st in subtypes:
            assert st in summary


# ---------------------------------------------------------------------------
# Phase B / C stubs — must return empty string, not raise
# ---------------------------------------------------------------------------


class TestPhaseStubs:
    def test_get_known_rtl_bugs_returns_empty(self, query: WikiQueryService) -> None:
        assert query.get_known_rtl_bugs() == ""

    def test_get_coverage_history_returns_empty(self, query: WikiQueryService) -> None:
        assert query.get_coverage_history() == ""

    def test_stubs_never_raise(self, svc: WikiIngestService, query: WikiQueryService) -> None:
        # Populate wiki so it is not trivially empty
        _populate(svc, "missing_timescale", "compile_error", 1)
        # None of these should raise
        query.get_known_rtl_bugs(ip_type="axi", status="open", top_k=5)
        query.get_coverage_history(covergroup="axi_cov", top_k=3)
