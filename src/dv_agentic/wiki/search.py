# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Wiki search index — BM25 and keyword fallback backends.

Strategy Pattern: two implementations share one ``WikiSearchIndex`` interface.

  BM25SearchIndex     — uses ``bm25s[core]`` (air-gapped, pure Python).
                        Falls back to KeywordSearchIndex when bm25s is absent.
  KeywordSearchIndex  — simple substring scoring; zero extra dependencies.

Usage::

    idx = WikiSearchIndex.create("bm25", wiki_dir)
    idx.build(wiki_dir)                         # initial build
    idx.update(page_path, new_content)          # after each ingest write
    results = idx.search("timescale", top_k=3)  # BM25 / keyword query

Install bm25s for the full BM25 experience::

    pip install "bm25s[core]"

Without it, the system transparently falls back to keyword matching so
every agent workflow keeps working.
"""

from __future__ import annotations

import abc
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Structural files excluded from the search corpus
_EXCLUDED_NAMES: frozenset[str] = frozenset({"WIKI.md", "log.md", "index.md"})

# Approximate characters per LLM token (conservative)
_CHARS_PER_TOKEN = 4

# Persistent bm25s index sub-directory inside wiki_dir
_INDEX_SUBDIR = ".search_index"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    """Single result returned by :meth:`WikiSearchIndex.search`.

    Attributes:
        page_path: Path relative to *wiki_dir*.
        score: BM25 or keyword relevance score (higher = more relevant).
        excerpt: First 200 characters of the page body.
        frontmatter: Parsed YAML frontmatter dict (may be empty).
    """

    page_path: str
    score: float
    excerpt: str
    frontmatter: dict[str, Any]


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class WikiSearchIndex(abc.ABC):
    """Abstract search index interface."""

    @abc.abstractmethod
    def build(self, wiki_dir: Path) -> None:
        """Scan *wiki_dir* and build a full index from scratch."""

    @abc.abstractmethod
    def update(self, page_path: Path, content: str) -> None:
        """Incrementally update the index entry for *page_path*."""

    @abc.abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Return up to *top_k* pages most relevant to *query*."""

    @classmethod
    def create(cls, backend: str, wiki_dir: Path) -> WikiSearchIndex:
        """Factory: instantiate the appropriate backend.

        Args:
            backend: ``"bm25"`` (recommended) or ``"none"`` (keyword only).
            wiki_dir: Wiki root directory.

        Returns:
            Concrete :class:`WikiSearchIndex` instance.

        Raises:
            ValueError: If *backend* is not recognised.
        """
        if backend == "bm25":
            return BM25SearchIndex(wiki_dir)
        if backend == "none":
            return KeywordSearchIndex(wiki_dir)
        raise ValueError(f"Unknown search backend: {backend!r}. Supported values: 'bm25', 'none'.")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _collect_pages(wiki_dir: Path) -> list[tuple[Path, str]]:
    """Return ``(path, content)`` for every indexable wiki page.

    Excludes structural files (``WIKI.md``, ``log.md``, ``index.md``) and
    ``_index.md`` sub-directory indexes.
    """
    pages: list[tuple[Path, str]] = []
    if not wiki_dir.is_dir():
        return pages
    for md in sorted(wiki_dir.rglob("*.md")):
        if md.name in _EXCLUDED_NAMES or md.name.startswith("_"):
            continue
        try:
            pages.append((md, md.read_text(encoding="utf-8")))
        except OSError:
            logger.debug("search: could not read %s", md)
    return pages


def _excerpt(body: str, max_chars: int = 200) -> str:
    stripped = body.strip()
    if len(stripped) <= max_chars:
        return stripped
    return stripped[:max_chars] + "…"


# ---------------------------------------------------------------------------
# BM25 implementation
# ---------------------------------------------------------------------------


class BM25SearchIndex(WikiSearchIndex):
    """BM25 index backed by ``bm25s[core]``.

    Falls back to :class:`KeywordSearchIndex` transparently when ``bm25s``
    is not installed, so the system keeps working in environments where the
    ``[wiki]`` optional extra is absent.

    The bm25s index is **persisted** to ``{wiki_dir}/.search_index/`` after
    each full build.  Because ``bm25s`` v0.2 does not support incremental
    updates, a full rebuild is triggered on every :meth:`update` call.
    For wiki sizes typical in DV projects (< 500 pages) this takes < 1 s.
    """

    def __init__(self, wiki_dir: Path) -> None:
        self._wiki_dir = wiki_dir
        self._index_path = wiki_dir / _INDEX_SUBDIR
        # In-memory page cache used to avoid re-reading during search
        self._pages: list[tuple[Path, str]] = []
        # Set when bm25s is unavailable
        self._fallback: KeywordSearchIndex | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def build(self, wiki_dir: Path) -> None:
        """Build BM25 index from all wiki pages, persist to disk."""
        try:
            self._build_bm25(wiki_dir)
        except ImportError:
            logger.info(
                "bm25s not installed — wiki search uses keyword fallback. "
                "Install with: pip install 'bm25s[core]'"
            )
            self._fallback = KeywordSearchIndex(wiki_dir)
            self._fallback.build(wiki_dir)

    def update(self, page_path: Path, content: str) -> None:
        """Rebuild the full index after a page is written."""
        if self._fallback is not None:
            self._fallback.update(page_path, content)
            return
        # bm25s v0.2: no incremental API — full rebuild is required
        try:
            self._build_bm25(self._wiki_dir)
        except Exception:
            logger.debug("BM25 rebuild failed after update", exc_info=True)

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """BM25 search; delegates to keyword fallback if bm25s unavailable."""
        if self._fallback is not None:
            return self._fallback.search(query, top_k)
        try:
            return self._search_bm25(query, top_k)
        except Exception:
            logger.debug("BM25 search error; rebuilding index", exc_info=True)
            self.build(self._wiki_dir)
            if self._fallback is not None:
                return self._fallback.search(query, top_k)
            try:
                return self._search_bm25(query, top_k)
            except Exception:
                logger.debug("BM25 search failed after rebuild", exc_info=True)
                return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_bm25(self, wiki_dir: Path) -> None:
        import bm25s

        pages = _collect_pages(wiki_dir)
        self._pages = pages

        if not pages:
            logger.debug("BM25: wiki is empty — skipping index build")
            return

        corpus = [content for _, content in pages]
        tokenized = bm25s.tokenize(corpus)

        retriever = bm25s.BM25()
        retriever.index(tokenized)

        self._index_path.mkdir(parents=True, exist_ok=True)
        retriever.save(str(self._index_path))
        logger.info("BM25 index built: %d pages → %s", len(pages), self._index_path)

    def _search_bm25(self, query: str, top_k: int) -> list[SearchResult]:
        import bm25s

        if not self._index_path.exists():
            self._build_bm25(self._wiki_dir)

        retriever = bm25s.BM25.load(str(self._index_path), load_corpus=False)
        pages = self._pages or _collect_pages(self._wiki_dir)
        if not pages:
            return []

        k = min(top_k, len(pages))
        tokenized_query = bm25s.tokenize([query])
        results, scores = retriever.retrieve(tokenized_query, k=k)

        from .manager import parse_page

        output: list[SearchResult] = []
        for idx, score in zip(results[0], scores[0], strict=True):
            page_path, content = pages[int(idx)]
            fm, body = parse_page(content)
            output.append(
                SearchResult(
                    page_path=str(page_path.relative_to(self._wiki_dir)),
                    score=float(score),
                    excerpt=_excerpt(body),
                    frontmatter=fm,
                )
            )
        return output


# ---------------------------------------------------------------------------
# Keyword fallback implementation (zero extra dependencies)
# ---------------------------------------------------------------------------


class KeywordSearchIndex(WikiSearchIndex):
    """Simple in-memory keyword search — counts query term occurrences.

    Used as a fallback when ``bm25s`` is not installed, and as the default
    when ``search_backend: "none"`` is set in ``project.yaml``.
    """

    def __init__(self, wiki_dir: Path) -> None:
        self._wiki_dir = wiki_dir
        self._pages: list[tuple[Path, str]] = []

    def build(self, wiki_dir: Path) -> None:
        self._pages = _collect_pages(wiki_dir)
        logger.debug("Keyword index built: %d pages", len(self._pages))

    def update(self, page_path: Path, content: str) -> None:
        for i, (path, _) in enumerate(self._pages):
            if path == page_path:
                self._pages[i] = (page_path, content)
                return
        self._pages.append((page_path, content))

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        if not self._pages:
            self._pages = _collect_pages(self._wiki_dir)

        from .manager import parse_page

        query_lower = query.lower()
        words = [w for w in re.split(r"\W+", query_lower) if w]

        scored: list[tuple[float, Path, str]] = []
        for page_path, content in self._pages:
            cl = content.lower()
            score = float(sum(cl.count(w) for w in words))
            if score > 0:
                scored.append((score, page_path, content))

        scored.sort(key=lambda x: x[0], reverse=True)

        results: list[SearchResult] = []
        for score, page_path, content in scored[:top_k]:
            fm, body = parse_page(content)
            results.append(
                SearchResult(
                    page_path=str(page_path.relative_to(self._wiki_dir)),
                    score=score,
                    excerpt=_excerpt(body),
                    frontmatter=fm,
                )
            )
        return results
