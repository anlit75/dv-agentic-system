# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Tests for Phase C Coverage Archiving and Reporter Integration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from dv_agentic.wiki.ingest import WikiIngestService
from dv_agentic.wiki.manager import WikiConfig, parse_page
from dv_agentic.wiki.query import WikiQueryService


@pytest.fixture
def wiki_cfg(tmp_path: Path) -> WikiConfig:
    return WikiConfig(
        enabled=True,
        wiki_dir=tmp_path / "wiki",
        search_backend="none",
        coverage_context_tokens=500,
    )


class TestWikiCoverageIngest:
    def test_ingest_coverage_hole_creates_page(self, wiki_cfg: WikiConfig) -> None:
        ingest = WikiIngestService(wiki_cfg)
        ingest.ingest_coverage_hole(
            covergroup="cg_dma",
            bin_name="burst_max",
            action_class="actionable",
            scenario="Memory boundary unaligned",
            filled=False,
            task_id="t_cov",
        )

        cov_dir = wiki_cfg.wiki_dir / "coverage"
        assert cov_dir.exists()
        page = cov_dir / "cg_dma_burst_max.md"
        assert page.exists()

        fm, body = parse_page(page.read_text(encoding="utf-8"))
        assert fm["type"] == "COVERAGE_HOLE"
        assert fm["covergroup"] == "cg_dma"
        assert fm["bin"] == "burst_max"
        assert fm["action_class"] == "actionable"
        assert fm["filled"] is False
        assert "Memory boundary unaligned" in body

    def test_ingest_coverage_hole_updates_index_and_log(self, wiki_cfg: WikiConfig) -> None:
        ingest = WikiIngestService(wiki_cfg)
        ingest.ingest_coverage_hole(
            covergroup="cg_axi",
            bin_name="xact_write",
            action_class="protocol_blocked",
            scenario="AXI protocol violation",
            filled=True,
            task_id="t_cov2",
        )

        # Check log.md
        log_md = wiki_cfg.wiki_dir / "log.md"
        assert log_md.exists()
        log_content = log_md.read_text(encoding="utf-8")
        assert "cg_axi_xact_write" in log_content
        assert "t_cov2" in log_content

        # Check index.md
        idx_md = wiki_cfg.wiki_dir / "index.md"
        assert idx_md.exists()
        idx_content = idx_md.read_text(encoding="utf-8")
        assert "## Coverage Holes" in idx_content
        assert "cg_axi_xact_write" in idx_content


class TestWikiCoverageQuery:
    def test_get_coverage_history(self, wiki_cfg: WikiConfig) -> None:
        ingest = WikiIngestService(wiki_cfg)
        ingest.ingest_coverage_hole("cg_1", "bin_a", "actionable", "s1", False, "t1")
        ingest.ingest_coverage_hole("cg_1", "bin_b", "design_excluded", "s2", True, "t2")

        query = WikiQueryService(wiki_cfg)
        res = query.get_coverage_history(top_k=5)

        assert "### Coverage History" in res
        assert "cg_1_bin_a" in res
        assert "actionable" in res
        assert "cg_1_bin_b" in res

    def test_get_coverage_history_filters_by_covergroup(self, wiki_cfg: WikiConfig) -> None:
        ingest = WikiIngestService(wiki_cfg)
        ingest.ingest_coverage_hole("cg_A", "b1", "actionable", "s1", False, "t1")
        ingest.ingest_coverage_hole("cg_B", "b1", "actionable", "s1", False, "t1")

        query = WikiQueryService(wiki_cfg)
        res = query.get_coverage_history(covergroup="cg_A", top_k=5)

        assert "cg_A_b1" in res
        assert "cg_B_b1" not in res


class TestWikiIngestSession:
    def test_ingest_session_parses_and_dispatches(self, wiki_cfg: WikiConfig) -> None:
        ingest = WikiIngestService(wiki_cfg)

        # We need mock functions on WikiIngestService since we want to verify calls
        with (
            patch.object(ingest, "ingest_pattern") as mock_pattern,
            patch.object(ingest, "ingest_bug") as mock_bug,
            patch.object(ingest, "ingest_coverage_hole"),
        ):
            # The test input from the agents
            session_report = "### Session\nFinished ok"
            failure_summary = "error_class: compile_error\nfailure_subtype: missing_timescale"
            classification = "BUG_TYPE: RTL_BUG\nCONFIDENCE: 0.9\nEVIDENCE:\nsome ev"
            coverage_summary = "### Coverage Summary\nbelow_threshold: True"  # Just dummy

            ingest.ingest_session(
                session_report=session_report,
                failure_summary=failure_summary,
                classification=classification,
                coverage_summary=coverage_summary,
                task_id="t_sess",
            )

            mock_pattern.assert_called_once()
            mock_bug.assert_called_once()
            # mock_cov might not be called since we didn't put specific coverage hole info
            # in coverage_summary, but let's just test that the parsing logic tries to call
            # pattern and bug.

    def test_ingest_session_updates_log(self, wiki_cfg: WikiConfig) -> None:
        ingest = WikiIngestService(wiki_cfg)
        ingest.ingest_session(
            session_report="Session OK",
            failure_summary=None,
            classification=None,
            coverage_summary=None,
            task_id="t_sess_2",
        )

        log_md = wiki_cfg.wiki_dir / "log.md"
        assert log_md.exists()
        assert "t_sess_2" in log_md.read_text(encoding="utf-8")
        assert "SESSION_REPORT" in log_md.read_text(encoding="utf-8")
