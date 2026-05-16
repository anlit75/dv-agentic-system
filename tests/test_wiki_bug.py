# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Unit and integration tests for Phase B: Bug archiving and query.

Covers:
  - WikiIngestService.ingest_bug()
  - WikiQueryService.get_known_rtl_bugs()
  - BugClassifierAgent wiki_config seam
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from dv_agentic.wiki.ingest import WikiIngestResult, WikiIngestService
from dv_agentic.wiki.manager import WikiConfig, parse_page
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
    )


@pytest.fixture()
def svc(cfg: WikiConfig) -> WikiIngestService:
    return WikiIngestService(cfg)


def _ingest_rtl_bug(
    svc: WikiIngestService,
    *,
    bug_type: str = "RTL_BUG",
    confidence: float = 0.92,
    evidence: list[str] | None = None,
    error_class: str = "uvm_error",
    failure_subtype: str = "scoreboard_fail",
    task_id: str = "task_001",
    ip_type: str = "axi",
    log_path: str = "sim.log",
) -> WikiIngestResult:
    return svc.ingest_bug(
        bug_type=bug_type,
        confidence=confidence,
        evidence=evidence or ["BRESP returned SLVERR on boundary write"],
        error_class=error_class,
        failure_subtype=failure_subtype,
        task_id=task_id,
        ip_type=ip_type,
        log_path=log_path,
    )


# ---------------------------------------------------------------------------
# B1 — ingest_bug(): page creation
# ---------------------------------------------------------------------------


class TestIngestBugCreate:
    def test_creates_bugs_directory(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        _ingest_rtl_bug(svc)
        assert (cfg.wiki_dir / "bugs").is_dir()

    def test_creates_bug_page(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = _ingest_rtl_bug(svc)
        assert len(result.pages_created) == 1
        page = cfg.wiki_dir / "bugs" / Path(result.pages_created[0]).name
        assert page.exists()

    def test_page_id_format(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = _ingest_rtl_bug(svc, bug_type="RTL_BUG")
        page_name = Path(result.pages_created[0]).name
        # Must match RTL_YYYYMMDD_NNN.md
        import re

        assert re.match(r"RTL_\d{8}_\d{3}\.md", page_name), f"Bad format: {page_name!r}"

    def test_tb_bug_page_id_format(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = _ingest_rtl_bug(svc, bug_type="TB_BUG")
        page_name = Path(result.pages_created[0]).name
        import re

        assert re.match(r"TB_\d{8}_\d{3}\.md", page_name), f"Bad format: {page_name!r}"

    def test_frontmatter_type(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = _ingest_rtl_bug(svc, bug_type="RTL_BUG")
        page = cfg.wiki_dir / "bugs" / Path(result.pages_created[0]).name
        fm, _ = parse_page(page.read_text(encoding="utf-8"))
        assert fm.get("type") == "RTL_BUG"

    def test_frontmatter_status_open(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = _ingest_rtl_bug(svc)
        page = cfg.wiki_dir / "bugs" / Path(result.pages_created[0]).name
        fm, _ = parse_page(page.read_text(encoding="utf-8"))
        assert fm.get("status") == "open"

    def test_frontmatter_confidence(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = _ingest_rtl_bug(svc, confidence=0.88)
        page = cfg.wiki_dir / "bugs" / Path(result.pages_created[0]).name
        fm, _ = parse_page(page.read_text(encoding="utf-8"))
        assert abs(float(fm.get("confidence", 0)) - 0.88) < 0.001

    def test_frontmatter_task_id(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = _ingest_rtl_bug(svc, task_id="my_task_007")
        page = cfg.wiki_dir / "bugs" / Path(result.pages_created[0]).name
        fm, _ = parse_page(page.read_text(encoding="utf-8"))
        assert "my_task_007" in (fm.get("task_ids") or [])

    def test_frontmatter_error_class(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = _ingest_rtl_bug(svc, error_class="uvm_fatal")
        page = cfg.wiki_dir / "bugs" / Path(result.pages_created[0]).name
        fm, _ = parse_page(page.read_text(encoding="utf-8"))
        assert fm.get("error_class") == "uvm_fatal"

    def test_frontmatter_ip_type(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = _ingest_rtl_bug(svc, ip_type="pcie")
        page = cfg.wiki_dir / "bugs" / Path(result.pages_created[0]).name
        fm, _ = parse_page(page.read_text(encoding="utf-8"))
        assert fm.get("ip_type") == "pcie"

    def test_evidence_appears_in_body(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = _ingest_rtl_bug(svc, evidence=["BRESP returned SLVERR on boundary write"])
        page = cfg.wiki_dir / "bugs" / Path(result.pages_created[0]).name
        body_content = page.read_text(encoding="utf-8")
        assert "SLVERR" in body_content

    def test_result_pages_updated_empty(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = _ingest_rtl_bug(svc)
        assert result.pages_updated == []


# ---------------------------------------------------------------------------
# B1 — ingest_bug(): sequence numbering
# ---------------------------------------------------------------------------


class TestIngestBugSequence:
    def test_two_ingests_create_two_pages(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        r1 = _ingest_rtl_bug(svc, task_id="t1")
        r2 = _ingest_rtl_bug(svc, task_id="t2")
        assert r1.pages_created[0] != r2.pages_created[0]

    def test_sequence_increments(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        r1 = _ingest_rtl_bug(svc, task_id="t1")
        r2 = _ingest_rtl_bug(svc, task_id="t2")
        name1 = Path(r1.pages_created[0]).stem  # e.g. RTL_20260515_001
        name2 = Path(r2.pages_created[0]).stem  # e.g. RTL_20260515_002
        seq1 = int(name1.split("_")[-1])
        seq2 = int(name2.split("_")[-1])
        assert seq2 == seq1 + 1

    def test_three_pages_exist_after_three_ingests(
        self, svc: WikiIngestService, cfg: WikiConfig
    ) -> None:
        for i in range(3):
            _ingest_rtl_bug(svc, task_id=f"t{i}")
        pages = list((cfg.wiki_dir / "bugs").glob("*.md"))
        assert len(pages) == 3


# ---------------------------------------------------------------------------
# B1 — log.md
# ---------------------------------------------------------------------------


class TestIngestBugLogMd:
    def test_log_md_created(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        _ingest_rtl_bug(svc)
        assert (cfg.wiki_dir / "log.md").exists()

    def test_log_md_contains_task_id(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        _ingest_rtl_bug(svc, task_id="bug_task_99")
        log = (cfg.wiki_dir / "log.md").read_text(encoding="utf-8")
        assert "bug_task_99" in log

    def test_log_md_contains_bug_type(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        _ingest_rtl_bug(svc, bug_type="TB_BUG")
        log = (cfg.wiki_dir / "log.md").read_text(encoding="utf-8")
        assert "TB_BUG" in log

    def test_log_md_is_append_only(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        _ingest_rtl_bug(svc, task_id="t1")
        first = (cfg.wiki_dir / "log.md").read_text(encoding="utf-8")
        _ingest_rtl_bug(svc, task_id="t2")
        second = (cfg.wiki_dir / "log.md").read_text(encoding="utf-8")
        assert first.rstrip() in second


# ---------------------------------------------------------------------------
# B1 — index.md
# ---------------------------------------------------------------------------


class TestIngestBugIndexMd:
    def test_index_md_created(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        _ingest_rtl_bug(svc)
        assert (cfg.wiki_dir / "index.md").exists()

    def test_index_md_contains_bugs_section(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        _ingest_rtl_bug(svc)
        index = (cfg.wiki_dir / "index.md").read_text(encoding="utf-8")
        assert "## Bugs" in index

    def test_index_md_contains_bug_id(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        result = _ingest_rtl_bug(svc)
        page_id = Path(result.pages_created[0]).stem
        index = (cfg.wiki_dir / "index.md").read_text(encoding="utf-8")
        assert page_id in index

    def test_index_md_lists_multiple_bugs(self, svc: WikiIngestService, cfg: WikiConfig) -> None:
        r1 = _ingest_rtl_bug(svc, bug_type="RTL_BUG", task_id="t1")
        r2 = _ingest_rtl_bug(svc, bug_type="TB_BUG", task_id="t2")
        index = (cfg.wiki_dir / "index.md").read_text(encoding="utf-8")
        id1 = Path(r1.pages_created[0]).stem
        id2 = Path(r2.pages_created[0]).stem
        assert id1 in index
        assert id2 in index


# ---------------------------------------------------------------------------
# B2 — get_known_rtl_bugs()
# ---------------------------------------------------------------------------


def _seed_bug(
    cfg: WikiConfig,
    *,
    bug_type: str = "RTL_BUG",
    confidence: float = 0.90,
    status: str = "open",
    ip_type: str = "axi",
    task_id: str = "t1",
) -> str:
    """Seed a bug page and return the page stem (ID)."""
    svc = WikiIngestService(cfg)
    result = svc.ingest_bug(
        bug_type=bug_type,
        confidence=confidence,
        evidence=["test evidence"],
        error_class="uvm_error",
        failure_subtype="scoreboard_fail",
        task_id=task_id,
        ip_type=ip_type,
    )
    # Optionally patch status after creation
    if status != "open":
        page = cfg.wiki_dir / "bugs" / Path(result.pages_created[0]).name
        from dv_agentic.wiki.manager import atomic_write, serialize_page

        fm, body = parse_page(page.read_text(encoding="utf-8"))
        fm["status"] = status
        atomic_write(page, serialize_page(fm, body))
    return Path(result.pages_created[0]).stem


class TestGetKnownRtlBugsEmpty:
    def test_returns_empty_string_when_no_bugs_dir(self, cfg: WikiConfig) -> None:
        q = WikiQueryService(cfg)
        assert q.get_known_rtl_bugs() == ""

    def test_returns_empty_string_when_bugs_dir_empty(self, cfg: WikiConfig) -> None:
        (cfg.wiki_dir / "bugs").mkdir(parents=True)
        q = WikiQueryService(cfg)
        assert q.get_known_rtl_bugs() == ""

    def test_returns_empty_when_no_open_bugs(self, cfg: WikiConfig) -> None:
        _seed_bug(cfg, status="closed", task_id="t1")
        q = WikiQueryService(cfg)
        assert q.get_known_rtl_bugs(status="open") == ""


class TestGetKnownRtlBugsPopulated:
    def test_returns_nonempty_string(self, cfg: WikiConfig) -> None:
        _seed_bug(cfg)
        q = WikiQueryService(cfg)
        assert q.get_known_rtl_bugs() != ""

    def test_result_contains_bug_id(self, cfg: WikiConfig) -> None:
        bug_id = _seed_bug(cfg)
        q = WikiQueryService(cfg)
        result = q.get_known_rtl_bugs()
        assert bug_id in result

    def test_result_contains_header(self, cfg: WikiConfig) -> None:
        _seed_bug(cfg)
        q = WikiQueryService(cfg)
        assert "### Known RTL Bugs" in q.get_known_rtl_bugs()

    def test_filters_by_status_closed(self, cfg: WikiConfig) -> None:
        _seed_bug(cfg, status="open", task_id="t_open")
        closed_id = _seed_bug(cfg, status="closed", task_id="t_closed")
        q = WikiQueryService(cfg)
        result = q.get_known_rtl_bugs(status="closed")
        assert closed_id in result

    def test_filters_by_ip_type(self, cfg: WikiConfig) -> None:
        axi_id = _seed_bug(cfg, ip_type="axi", task_id="t_axi")
        pcie_id = _seed_bug(cfg, ip_type="pcie", task_id="t_pcie")
        q = WikiQueryService(cfg)
        result_axi = q.get_known_rtl_bugs(ip_type="axi")
        assert axi_id in result_axi
        assert pcie_id not in result_axi

    def test_top_k_limits_results(self, cfg: WikiConfig) -> None:
        for i in range(5):
            _seed_bug(cfg, task_id=f"t{i}")
        q = WikiQueryService(cfg)
        result = q.get_known_rtl_bugs(top_k=2)
        # Can't count exactly, but result must not be empty
        assert result != ""

    def test_sorts_by_confidence_descending(self, cfg: WikiConfig) -> None:
        low_id = _seed_bug(cfg, confidence=0.50, task_id="t_low")
        high_id = _seed_bug(cfg, confidence=0.95, task_id="t_high")
        q = WikiQueryService(cfg)
        result = q.get_known_rtl_bugs()
        # High confidence should appear before low
        assert result.index(high_id) < result.index(low_id)


class TestBugQueryTokenBudget:
    def test_result_within_token_budget(self, cfg: WikiConfig) -> None:
        cfg = WikiConfig(
            enabled=True,
            wiki_dir=cfg.wiki_dir,
            search_backend="none",
            bug_context_tokens=50,  # Very tight budget
        )
        for i in range(10):
            _seed_bug(cfg, task_id=f"t{i}")
        q = WikiQueryService(cfg)
        result = q.get_known_rtl_bugs()
        # 50 tokens * 4 chars/token = 200 chars max
        assert len(result) <= 50 * 4 + 50  # small slack for header


# ---------------------------------------------------------------------------
# B2b — BugClassifierAgent wiki seam
# ---------------------------------------------------------------------------


class TestBugClassifierWikiSeam:
    def test_no_wiki_config_backward_compat(self) -> None:
        """BugClassifierAgent must accept no wiki_config (Phase A compat)."""
        from unittest.mock import MagicMock

        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.bug_classifier import BugClassifierAgent

        llm = MagicMock()
        agent = BugClassifierAgent(
            config=AgentConfig(name="bug_classifier", budget=1),
            llm=llm,
        )
        assert agent.wiki_config is None

    def test_wiki_config_stored(self, cfg: WikiConfig) -> None:
        from unittest.mock import MagicMock

        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.bug_classifier import BugClassifierAgent

        llm = MagicMock()
        agent = BugClassifierAgent(
            config=AgentConfig(name="bug_classifier", budget=1),
            llm=llm,
            wiki_config=cfg,
        )
        assert agent.wiki_config is cfg

    @pytest.mark.asyncio
    async def test_ingest_fires_after_successful_classification(self, cfg: WikiConfig) -> None:
        """After a confident RTL_BUG classification, bugs/ page must appear."""
        from unittest.mock import AsyncMock, MagicMock

        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.bug_classifier import BugClassifierAgent

        llm = MagicMock()
        llm.complete = AsyncMock(
            return_value=(
                "BUG_TYPE: RTL_BUG\n"
                "CONFIDENCE: 0.95\n"
                "EVIDENCE:\n- BRESP SLVERR on boundary\n"
                "### Summary\nRTL does not handle 256-byte boundary correctly."
            )
        )
        agent = BugClassifierAgent(
            config=AgentConfig(name="bug_classifier", budget=2),
            llm=llm,
            wiki_config=cfg,
        )
        result = await agent.run(
            "### Failure Summary\nerror_class: uvm_error\nfailure_subtype: scoreboard_fail"
        )
        assert "RTL_BUG" in result

        # Drain create_task (using to_thread means it runs in a real thread, so we wait briefly)
        bugs_dir = cfg.wiki_dir / "bugs"
        for _ in range(20):
            if bugs_dir.exists():
                break
            await asyncio.sleep(0.05)

        assert bugs_dir.exists(), "bugs/ directory must be created after ingest"
        pages = list(bugs_dir.glob("*.md"))
        assert len(pages) >= 1, "At least one bug page must be created"

    @pytest.mark.asyncio
    async def test_unknown_does_not_ingest(self, cfg: WikiConfig) -> None:
        """UNKNOWN classification must NOT trigger wiki ingest."""
        from unittest.mock import AsyncMock, MagicMock

        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.bug_classifier import BugClassifierAgent

        llm = MagicMock()
        llm.complete = AsyncMock(
            return_value=(
                "BUG_TYPE: UNKNOWN\n"
                "CONFIDENCE: 0.3\n"
                "EVIDENCE:\n- insufficient data\n"
                "### Summary\nCannot determine cause."
            )
        )
        agent = BugClassifierAgent(
            config=AgentConfig(name="bug_classifier", budget=1),
            llm=llm,
            wiki_config=cfg,
        )
        await agent.run("some failure log")
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        bugs_dir = cfg.wiki_dir / "bugs"
        pages = list(bugs_dir.glob("*.md")) if bugs_dir.exists() else []
        assert len(pages) == 0, "UNKNOWN must not create bug pages"

    @pytest.mark.asyncio
    async def test_wiki_failure_does_not_crash_classifier(self, tmp_path: Path) -> None:
        """Even if wiki ingest raises, BugClassifier must return a valid result."""
        from unittest.mock import AsyncMock, MagicMock

        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.bug_classifier import BugClassifierAgent

        broken_cfg = WikiConfig(
            enabled=True,
            wiki_dir=Path("/nonexistent_wiki_xyz"),
            search_backend="none",
        )
        llm = MagicMock()
        llm.complete = AsyncMock(
            return_value=(
                "BUG_TYPE: RTL_BUG\n"
                "CONFIDENCE: 0.90\n"
                "EVIDENCE:\n- boundary fault\n"
                "### Summary\nRTL bug."
            )
        )
        agent = BugClassifierAgent(
            config=AgentConfig(name="bug_classifier", budget=2),
            llm=llm,
            wiki_config=broken_cfg,
        )
        result = await agent.run("failure log")
        assert "RTL_BUG" in result  # Agent must still succeed
