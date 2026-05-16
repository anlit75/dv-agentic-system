# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Unit tests for WikiSearchIndex (Phase A).

BM25 tests are skipped automatically when bm25s is not installed so the
suite keeps passing in environments that omit the [wiki] extra.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from dv_agentic.wiki.manager import atomic_write, serialize_page
from dv_agentic.wiki.search import (
    BM25SearchIndex,
    KeywordSearchIndex,
    SearchResult,
    WikiSearchIndex,
    _collect_pages,
    _excerpt,
)

# ---------------------------------------------------------------------------
# Skip marker for BM25-specific tests
# ---------------------------------------------------------------------------

bm25s_available = importlib.util.find_spec("bm25s") is not None
skip_no_bm25s = pytest.mark.skipif(
    not bm25s_available,
    reason="bm25s not installed — install with: pip install 'bm25s[core]'",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_page(
    wiki_dir: Path,
    rel_path: str,
    pattern_id: str,
    error_class: str,
    hit_count: int,
    body: str = "",
) -> Path:
    """Write a minimal wiki page and return its path."""
    page = wiki_dir / rel_path
    fm = {
        "pattern_id": pattern_id,
        "error_class": error_class,
        "failure_subtype": pattern_id,
        "hit_count": hit_count,
        "first_seen": "2026-01-01",
        "last_seen": "2026-01-01",
        "fix_success_rate": None,
    }
    body_text = body or f"# Pattern: {pattern_id}\n\nThis is the {pattern_id} description.\n"
    atomic_write(page, serialize_page(fm, body_text))
    return page


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestWikiSearchIndexFactory:
    def test_create_bm25_returns_bm25_instance(self, tmp_path: Path) -> None:
        idx = WikiSearchIndex.create("bm25", tmp_path)
        assert isinstance(idx, BM25SearchIndex)

    def test_create_none_returns_keyword_instance(self, tmp_path: Path) -> None:
        idx = WikiSearchIndex.create("none", tmp_path)
        assert isinstance(idx, KeywordSearchIndex)

    def test_create_unknown_backend_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown search backend"):
            WikiSearchIndex.create("elastic", tmp_path)


# ---------------------------------------------------------------------------
# _collect_pages helper
# ---------------------------------------------------------------------------


class TestCollectPages:
    def test_collects_md_files(self, tmp_path: Path) -> None:
        _write_page(
            tmp_path, "patterns/missing_timescale.md", "missing_timescale", "compile_error", 3
        )
        _write_page(tmp_path, "patterns/unmatched_block.md", "unmatched_block", "compile_error", 1)
        pages = _collect_pages(tmp_path)
        names = {p.name for p, _ in pages}
        assert "missing_timescale.md" in names
        assert "unmatched_block.md" in names

    def test_excludes_structural_files(self, tmp_path: Path) -> None:
        for name in ("WIKI.md", "log.md", "index.md"):
            atomic_write(tmp_path / name, f"# {name}")
        pages = _collect_pages(tmp_path)
        names = {p.name for p, _ in pages}
        assert "WIKI.md" not in names
        assert "log.md" not in names
        assert "index.md" not in names

    def test_excludes_underscore_files(self, tmp_path: Path) -> None:
        atomic_write(tmp_path / "patterns" / "_index.md", "# sub-index")
        pages = _collect_pages(tmp_path)
        names = {p.name for p, _ in pages}
        assert "_index.md" not in names

    def test_returns_empty_list_for_missing_dir(self, tmp_path: Path) -> None:
        assert _collect_pages(tmp_path / "nonexistent") == []

    def test_recurses_into_subdirectories(self, tmp_path: Path) -> None:
        _write_page(tmp_path, "patterns/p1.md", "p1", "compile_error", 1)
        _write_page(tmp_path, "bugs/b1.md", "b1", "uvm_error", 2)
        pages = _collect_pages(tmp_path)
        names = {p.name for p, _ in pages}
        assert "p1.md" in names
        assert "b1.md" in names


# ---------------------------------------------------------------------------
# _excerpt helper
# ---------------------------------------------------------------------------


class TestExcerpt:
    def test_short_body_unchanged(self) -> None:
        body = "short text"
        assert _excerpt(body, 200) == "short text"

    def test_long_body_truncated_with_ellipsis(self) -> None:
        body = "x" * 300
        result = _excerpt(body, 200)
        assert result.endswith("…")
        assert len(result) == 201  # 200 chars + ellipsis

    def test_strips_leading_whitespace(self) -> None:
        assert _excerpt("  hello  ", 200) == "hello"


# ---------------------------------------------------------------------------
# KeywordSearchIndex
# ---------------------------------------------------------------------------


class TestKeywordSearchIndex:
    def test_build_empty_wiki(self, tmp_path: Path) -> None:
        idx = KeywordSearchIndex(tmp_path)
        idx.build(tmp_path)  # must not raise

    def test_search_empty_wiki_returns_empty_list(self, tmp_path: Path) -> None:
        idx = KeywordSearchIndex(tmp_path)
        idx.build(tmp_path)
        assert idx.search("timescale") == []

    def test_search_finds_matching_page(self, tmp_path: Path) -> None:
        _write_page(
            tmp_path,
            "patterns/missing_timescale.md",
            "missing_timescale",
            "compile_error",
            5,
            body="timescale declaration is missing from the generated file.",
        )
        idx = KeywordSearchIndex(tmp_path)
        idx.build(tmp_path)
        results = idx.search("timescale")
        assert len(results) >= 1
        assert "missing_timescale" in results[0].page_path

    def test_search_returns_search_result_type(self, tmp_path: Path) -> None:
        _write_page(tmp_path, "patterns/p1.md", "p1", "compile_error", 1)
        idx = KeywordSearchIndex(tmp_path)
        idx.build(tmp_path)
        results = idx.search("p1")
        assert all(isinstance(r, SearchResult) for r in results)

    def test_search_result_has_frontmatter(self, tmp_path: Path) -> None:
        _write_page(
            tmp_path,
            "patterns/missing_timescale.md",
            "missing_timescale",
            "compile_error",
            7,
        )
        idx = KeywordSearchIndex(tmp_path)
        idx.build(tmp_path)
        results = idx.search("missing_timescale")
        assert results[0].frontmatter.get("hit_count") == 7

    def test_search_result_has_excerpt(self, tmp_path: Path) -> None:
        _write_page(
            tmp_path,
            "patterns/p1.md",
            "p1",
            "compile_error",
            1,
            body="unique excerpt content here",
        )
        idx = KeywordSearchIndex(tmp_path)
        idx.build(tmp_path)
        results = idx.search("unique excerpt")
        assert "unique excerpt" in results[0].excerpt

    def test_search_result_page_path_is_relative(self, tmp_path: Path) -> None:
        _write_page(tmp_path, "patterns/p1.md", "p1", "compile_error", 1)
        idx = KeywordSearchIndex(tmp_path)
        idx.build(tmp_path)
        results = idx.search("p1")
        assert not Path(results[0].page_path).is_absolute()
        assert Path(results[0].page_path) == Path("patterns/p1.md")

    def test_search_respects_top_k(self, tmp_path: Path) -> None:
        for i in range(5):
            _write_page(
                tmp_path,
                f"patterns/p{i}.md",
                f"p{i}",
                "compile_error",
                1,
                body="common word repeated " * 10,
            )
        idx = KeywordSearchIndex(tmp_path)
        idx.build(tmp_path)
        results = idx.search("common", top_k=3)
        assert len(results) <= 3

    def test_search_returns_empty_for_nonexistent_term(self, tmp_path: Path) -> None:
        _write_page(tmp_path, "patterns/p1.md", "p1", "compile_error", 1, body="hello world")
        idx = KeywordSearchIndex(tmp_path)
        idx.build(tmp_path)
        assert idx.search("xyzzy_nonexistent_term") == []

    def test_update_adds_new_page(self, tmp_path: Path) -> None:
        idx = KeywordSearchIndex(tmp_path)
        idx.build(tmp_path)
        assert idx.search("brandnew") == []

        new_page = _write_page(
            tmp_path,
            "patterns/new.md",
            "new",
            "compile_error",
            1,
            body="brandnew content",
        )
        idx.update(new_page, new_page.read_text())
        results = idx.search("brandnew")
        assert len(results) >= 1

    def test_update_replaces_existing_page(self, tmp_path: Path) -> None:
        page = _write_page(
            tmp_path,
            "patterns/p1.md",
            "p1",
            "compile_error",
            1,
            body="original content alpha",
        )
        idx = KeywordSearchIndex(tmp_path)
        idx.build(tmp_path)

        # Overwrite with new content
        atomic_write(
            page,
            serialize_page(
                {
                    "pattern_id": "p1",
                    "error_class": "compile_error",
                    "failure_subtype": "p1",
                    "hit_count": 2,
                    "first_seen": "2026-01-01",
                    "last_seen": "2026-01-01",
                    "fix_success_rate": None,
                },
                "updated content beta",
            ),
        )
        idx.update(page, page.read_text())

        assert idx.search("alpha") == []
        assert len(idx.search("beta")) >= 1

    def test_scores_higher_frequency_results_first(self, tmp_path: Path) -> None:
        _write_page(
            tmp_path,
            "patterns/high.md",
            "high",
            "compile_error",
            10,
            body="timescale timescale timescale timescale timescale",
        )
        _write_page(
            tmp_path,
            "patterns/low.md",
            "low",
            "compile_error",
            1,
            body="timescale appears once here",
        )
        idx = KeywordSearchIndex(tmp_path)
        idx.build(tmp_path)
        results = idx.search("timescale", top_k=2)
        assert "high" in results[0].page_path


# ---------------------------------------------------------------------------
# BM25SearchIndex — only runs when bm25s is installed
# ---------------------------------------------------------------------------


@skip_no_bm25s
class TestBM25SearchIndex:
    def test_build_creates_index_directory(self, tmp_path: Path) -> None:
        _write_page(tmp_path, "patterns/p1.md", "p1", "compile_error", 1)
        idx = BM25SearchIndex(tmp_path)
        idx.build(tmp_path)
        assert (tmp_path / ".search_index").is_dir()

    def test_search_finds_relevant_page(self, tmp_path: Path) -> None:
        _write_page(
            tmp_path,
            "patterns/missing_timescale.md",
            "missing_timescale",
            "compile_error",
            5,
            body="timescale declaration missing from generated SV file",
        )
        idx = BM25SearchIndex(tmp_path)
        idx.build(tmp_path)
        results = idx.search("timescale declaration", top_k=3)
        assert len(results) >= 1
        assert "missing_timescale" in results[0].page_path

    def test_search_returns_search_result_type(self, tmp_path: Path) -> None:
        _write_page(tmp_path, "patterns/p1.md", "p1", "compile_error", 1)
        idx = BM25SearchIndex(tmp_path)
        idx.build(tmp_path)
        results = idx.search("p1")
        assert all(isinstance(r, SearchResult) for r in results)

    def test_search_result_has_frontmatter(self, tmp_path: Path) -> None:
        _write_page(
            tmp_path,
            "patterns/missing_timescale.md",
            "missing_timescale",
            "compile_error",
            7,
        )
        idx = BM25SearchIndex(tmp_path)
        idx.build(tmp_path)
        results = idx.search("missing_timescale")
        assert results[0].frontmatter.get("hit_count") == 7

    def test_empty_wiki_does_not_raise(self, tmp_path: Path) -> None:
        idx = BM25SearchIndex(tmp_path)
        idx.build(tmp_path)  # empty wiki — must not raise
        assert idx.search("anything") == []

    def test_update_triggers_rebuild(self, tmp_path: Path) -> None:
        idx = BM25SearchIndex(tmp_path)
        idx.build(tmp_path)

        new_page = _write_page(
            tmp_path,
            "patterns/new_pattern.md",
            "new_pattern",
            "uvm_error",
            1,
            body="new_pattern_unique_token_xyz",
        )
        idx.update(new_page, new_page.read_text())
        results = idx.search("new_pattern_unique_token_xyz")
        assert len(results) >= 1

    def test_search_respects_top_k(self, tmp_path: Path) -> None:
        for i in range(6):
            _write_page(
                tmp_path,
                f"patterns/p{i}.md",
                f"p{i}",
                "compile_error",
                1,
                body="shared keyword appears here",
            )
        idx = BM25SearchIndex(tmp_path)
        idx.build(tmp_path)
        results = idx.search("shared keyword", top_k=3)
        assert len(results) <= 3


@skip_no_bm25s
class TestBM25FallbackBehavior:
    """When bm25s IS installed, verify keyword fallback is not activated."""

    def test_fallback_is_none_when_bm25s_available(self, tmp_path: Path) -> None:
        idx = BM25SearchIndex(tmp_path)
        idx.build(tmp_path)
        assert idx._fallback is None


class TestBM25FallbackWhenMissing:
    """When bm25s is NOT installed, BM25SearchIndex must fall back silently."""

    def test_falls_back_to_keyword_index(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulate bm25s being absent by making the import raise ImportError."""
        import sys

        # Temporarily hide bm25s from the import system
        original = sys.modules.get("bm25s", None)
        sys.modules["bm25s"] = None  # type: ignore[assignment]
        try:
            _write_page(
                tmp_path,
                "patterns/p1.md",
                "p1",
                "compile_error",
                1,
                body="fallback test content",
            )
            idx = BM25SearchIndex(tmp_path)
            idx.build(tmp_path)
            # After failed bm25s import, fallback should be set
            assert idx._fallback is not None
            assert isinstance(idx._fallback, KeywordSearchIndex)
            # Search must still work via fallback
            results = idx.search("fallback test")
            assert isinstance(results, list)
        finally:
            if original is None:
                del sys.modules["bm25s"]
            else:
                sys.modules["bm25s"] = original
