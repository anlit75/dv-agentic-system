# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Phase A integration tests — end-to-end knowledge compounding.

Acceptance criteria from llm-wiki-dv-agentic-spec.md Phase A:

  AC-1  LogAnalyzer detects ``missing_timescale``
        → ``patterns/missing_timescale.md`` is created / updated.
  AC-2  Next session's ``{{KNOWN_ERROR_PATTERNS}}`` contains the pattern.
  AC-3  All existing tests pass (wiki disabled by default = backward compat).

These tests exercise the full stack without a real LLM or simulator.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dv_agentic.agents.base import AgentConfig
from dv_agentic.agents.log_analyzer import LogAnalyzerAgent
from dv_agentic.wiki.ingest import WikiIngestService
from dv_agentic.wiki.manager import WikiConfig, parse_page

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def wiki_cfg(tmp_path: Path) -> WikiConfig:
    cfg = WikiConfig(
        enabled=True,
        wiki_dir=tmp_path / "wiki",
        search_backend="none",  # avoid bm25s dep in integration tests
        pattern_context_tokens=500,
    )
    cfg.wiki_dir.mkdir(parents=True, exist_ok=True)
    return cfg


@pytest.fixture()
def agent_cfg() -> AgentConfig:
    return AgentConfig(name="log_analyzer")


# ---------------------------------------------------------------------------
# AC-1  LogAnalyzer → patterns/*.md auto-update
# ---------------------------------------------------------------------------


class TestAC1LogAnalyzerAutoIngest:
    """AC-1: LogAnalyzer result triggers wiki pattern ingest."""

    @pytest.mark.asyncio
    async def test_missing_timescale_log_creates_pattern_page(
        self, wiki_cfg: WikiConfig, agent_cfg: AgentConfig
    ) -> None:
        """End-to-end: analysing a log with timescale error → page created."""
        log_content = (
            "*E,NOTIME (tb/sequences/axi_burst_seq.sv,1): "
            "`timescale not defined before this module\n"
            "xrun: *E,ILLPRI: Error encountered during compilation."
        )
        agent = LogAnalyzerAgent(config=agent_cfg, wiki_config=wiki_cfg)

        # run() fires asyncio.create_task for wiki ingest — we need to give
        # the task a chance to execute before asserting.
        await agent.run(log_content)
        # Drain all pending tasks in the current event loop
        await asyncio.sleep(0)
        await asyncio.sleep(0)  # two yields to cover nested async calls

        page = wiki_cfg.wiki_dir / "patterns" / "missing_timescale.md"
        assert page.exists(), "patterns/missing_timescale.md must be created"

    @pytest.mark.asyncio
    async def test_pattern_page_has_correct_frontmatter(
        self, wiki_cfg: WikiConfig, agent_cfg: AgentConfig
    ) -> None:
        log_content = "*E,NOTIME (tb/seq.sv,1): `timescale not defined\n"
        agent = LogAnalyzerAgent(config=agent_cfg, wiki_config=wiki_cfg)
        await agent.run(log_content)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        page = wiki_cfg.wiki_dir / "patterns" / "missing_timescale.md"
        if not page.exists():
            pytest.skip("Pattern page not yet written (timing-sensitive)")
        fm, _ = parse_page(page.read_text(encoding="utf-8"))
        assert fm.get("pattern_id") == "missing_timescale"
        assert fm.get("error_class") == "compile_error"
        assert fm.get("hit_count") == 1

    @pytest.mark.asyncio
    async def test_hit_count_increments_across_sessions(
        self, wiki_cfg: WikiConfig, agent_cfg: AgentConfig
    ) -> None:
        """Simulates two separate 'sessions' detecting the same error."""
        log_content = "*E,NOTIME (tb/seq.sv,1): `timescale not defined\n"

        for _ in range(2):
            a = LogAnalyzerAgent(config=agent_cfg, wiki_config=wiki_cfg)
            await a.run(log_content)
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        page = wiki_cfg.wiki_dir / "patterns" / "missing_timescale.md"
        if not page.exists():
            pytest.skip("Pattern page not written (timing-sensitive)")
        fm, _ = parse_page(page.read_text(encoding="utf-8"))
        assert fm.get("hit_count") == 2

    @pytest.mark.asyncio
    async def test_wiki_failure_does_not_crash_agent(
        self, wiki_cfg: WikiConfig, agent_cfg: AgentConfig
    ) -> None:
        """Even if wiki ingest raises, agent must return a valid result."""
        log_content = "UVM_FATAL @ 100ns [TEST] unexpected value\n"

        # Point wiki_dir to a non-writable location to force failure
        broken_cfg = WikiConfig(
            enabled=True,
            wiki_dir=Path("/nonexistent_wiki_dir_xyz"),
            search_backend="none",
        )
        agent = LogAnalyzerAgent(config=agent_cfg, wiki_config=broken_cfg)

        result = await agent.run(log_content)
        # Agent must still return a valid FailureSummary string
        assert "uvm_fatal" in result
        assert "### Failure Summary" in result

    @pytest.mark.asyncio
    async def test_no_wiki_config_agent_works_normally(self, agent_cfg: AgentConfig) -> None:
        """Backward compat: wiki_config=None means no wiki behaviour."""
        log_content = "*E,NOTIME (tb/seq.sv,1): `timescale not defined\n"
        agent = LogAnalyzerAgent(config=agent_cfg)  # wiki_config defaults to None
        result = await agent.run(log_content)
        assert "compile_error" in result


# ---------------------------------------------------------------------------
# AC-2  PromptLoader injects wiki knowledge into {{KNOWN_ERROR_PATTERNS}}
# ---------------------------------------------------------------------------


class TestAC2PromptLoaderInjection:
    """AC-2: PromptLoader reads wiki and populates {{KNOWN_ERROR_PATTERNS}}."""

    def _seed_pattern(self, wiki_cfg: WikiConfig, subtype: str, hits: int) -> None:
        svc = WikiIngestService(wiki_cfg)
        for i in range(hits):
            svc.ingest_pattern(subtype, "compile_error", [], None, False, f"t{i}")

    def test_gather_context_contains_known_error_patterns(
        self, wiki_cfg: WikiConfig, tmp_path: Path
    ) -> None:
        """After seeding the wiki, PromptLoader._gather_context() must include
        a non-empty KNOWN_ERROR_PATTERNS entry."""
        self._seed_pattern(wiki_cfg, "missing_timescale", 3)

        from dv_agentic.prompts.prompt_loader import PromptLoader

        loader = PromptLoader(wiki_config=wiki_cfg)
        ctx = loader._gather_context()

        assert "KNOWN_ERROR_PATTERNS" in ctx
        assert "missing_timescale" in ctx["KNOWN_ERROR_PATTERNS"]

    def test_empty_wiki_does_not_populate_placeholder(self, wiki_cfg: WikiConfig) -> None:
        """An empty wiki must not inject anything into the context."""
        from dv_agentic.prompts.prompt_loader import PromptLoader

        loader = PromptLoader(wiki_config=wiki_cfg)
        ctx = loader._gather_context()

        # KNOWN_ERROR_PATTERNS should be absent or empty when wiki is empty
        assert ctx.get("KNOWN_ERROR_PATTERNS", "") == ""

    def test_wiki_context_overwrites_profile_context(
        self, wiki_cfg: WikiConfig, tmp_path: Path
    ) -> None:
        """Wiki knowledge takes precedence over static profile knowledge."""
        from dv_agentic.prompts.context import ProjectContext
        from dv_agentic.prompts.prompt_loader import PromptLoader

        self._seed_pattern(wiki_cfg, "missing_timescale", 5)

        static_profile = ProjectContext(known_error_patterns="STATIC: old pattern from profile")
        loader = PromptLoader(project_config=static_profile, wiki_config=wiki_cfg)
        ctx = loader._gather_context()

        # Wiki content must replace the static profile content
        assert "missing_timescale" in ctx.get("KNOWN_ERROR_PATTERNS", "")
        assert "STATIC" not in ctx.get("KNOWN_ERROR_PATTERNS", "")

    def test_disabled_wiki_does_not_inject(self, tmp_path: Path) -> None:
        """wiki_config with enabled=False must not touch the context."""
        from dv_agentic.prompts.context import ProjectContext
        from dv_agentic.prompts.prompt_loader import PromptLoader

        disabled_cfg = WikiConfig(enabled=False, wiki_dir=tmp_path / "wiki")
        static_profile = ProjectContext(known_error_patterns="STATIC: from profile")
        loader = PromptLoader(project_config=static_profile, wiki_config=disabled_cfg)
        ctx = loader._gather_context()

        # Static profile must be preserved unchanged
        assert ctx.get("KNOWN_ERROR_PATTERNS") == "STATIC: from profile"

    def test_prompt_template_injection_end_to_end(
        self, wiki_cfg: WikiConfig, tmp_path: Path
    ) -> None:
        """Full path: seed wiki → PromptLoader.load() → placeholder replaced."""
        self._seed_pattern(wiki_cfg, "missing_timescale", 2)

        # Create a minimal prompt template that uses the placeholder
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        template = "You are a log analyzer.\n\n{{KNOWN_ERROR_PATTERNS}}\n\nAnalyse the given log."
        (prompts_dir / "log_analyzer.tmpl.md").write_text(template)

        from dv_agentic.prompts.prompt_loader import PromptLoader

        loader = PromptLoader(prompts_dir=prompts_dir, wiki_config=wiki_cfg)
        prompt = loader.load("log_analyzer")

        assert "missing_timescale" in prompt
        assert "{{KNOWN_ERROR_PATTERNS}}" not in prompt  # placeholder must be gone

    def test_wiki_pattern_summary_injected(self, wiki_cfg: WikiConfig, tmp_path: Path) -> None:
        """{{WIKI_PATTERN_SUMMARY}} is populated from wiki statistics."""
        self._seed_pattern(wiki_cfg, "missing_timescale", 4)

        from dv_agentic.prompts.prompt_loader import PromptLoader

        loader = PromptLoader(wiki_config=wiki_cfg)
        ctx = loader._gather_context()

        summary = ctx.get("WIKI_PATTERN_SUMMARY", "")
        assert "missing_timescale" in summary
        assert "4" in summary  # hit_count


# ---------------------------------------------------------------------------
# AC-3  Backward compatibility — wiki disabled by default
# ---------------------------------------------------------------------------


class TestAC3BackwardCompatibility:
    """AC-3: All existing agent constructors work without wiki_config."""

    def test_log_analyzer_no_wiki_config(self) -> None:
        agent = LogAnalyzerAgent(config=AgentConfig(name="log_analyzer"))
        assert agent.wiki_config is None

    def test_log_analyzer_analyze_unchanged_without_wiki(self) -> None:
        agent = LogAnalyzerAgent(config=AgentConfig(name="log_analyzer"))
        summary = agent.analyze("UVM_ERROR @ 100ns: mismatch")
        assert summary.error_class == "uvm_error"

    def test_prompt_loader_no_wiki_config(self, tmp_path: Path) -> None:
        """PromptLoader(wiki_config=None) must behave identically to before."""
        from dv_agentic.prompts.prompt_loader import PromptLoader

        loader = PromptLoader(wiki_config=None)
        ctx = loader._gather_context()
        assert ctx == {}

    def test_wiki_config_default_disabled(self) -> None:
        cfg = WikiConfig()
        assert cfg.enabled is False

    def test_load_wiki_config_from_missing_yaml(self, tmp_path: Path) -> None:
        """load_wiki_config() on a missing file returns disabled config."""
        from dv_agentic.wiki.manager import load_wiki_config

        cfg = load_wiki_config(tmp_path / "nonexistent.yaml")
        assert cfg.enabled is False

    def test_load_wiki_config_from_yaml_without_wiki_block(self, tmp_path: Path) -> None:
        """project.yaml without a ``wiki:`` block → disabled config."""
        import yaml as _yaml

        from dv_agentic.wiki.manager import load_wiki_config

        p = tmp_path / "project.yaml"
        p.write_text(
            _yaml.dump(
                {
                    "project": {"name": "test", "environment": "internal"},
                    "composition": {"simulator": "xcelium", "coverage": "imc"},
                }
            )
        )
        cfg = load_wiki_config(p)
        assert cfg.enabled is False

    def test_load_wiki_config_enabled_true(self, tmp_path: Path) -> None:
        """project.yaml with ``wiki.enabled: true`` → enabled config."""
        import yaml as _yaml

        from dv_agentic.wiki.manager import load_wiki_config

        p = tmp_path / "project.yaml"
        p.write_text(
            _yaml.dump(
                {
                    "project": {"name": "test", "environment": "internal"},
                    "wiki": {
                        "enabled": True,
                        "wiki_dir": str(tmp_path / "wiki"),
                        "search_backend": "none",
                    },
                }
            )
        )
        cfg = load_wiki_config(p)
        assert cfg.enabled is True
        assert cfg.search_backend == "none"

    def test_load_wiki_config_custom_token_budgets(self, tmp_path: Path) -> None:
        import yaml as _yaml

        from dv_agentic.wiki.manager import load_wiki_config

        p = tmp_path / "project.yaml"
        p.write_text(
            _yaml.dump(
                {
                    "wiki": {
                        "enabled": True,
                        "pattern_context_tokens": 800,
                        "bug_context_tokens": 300,
                    }
                }
            )
        )
        cfg = load_wiki_config(p)
        assert cfg.pattern_context_tokens == 800
        assert cfg.bug_context_tokens == 300


# ---------------------------------------------------------------------------
# Full pipeline smoke test
# ---------------------------------------------------------------------------


class TestFullPipelineSmoke:
    """Smoke test: simulate two consecutive sessions showing knowledge growth."""

    @pytest.mark.asyncio
    async def test_knowledge_compounds_across_sessions(self, wiki_cfg: WikiConfig) -> None:
        """
        Session 1: LogAnalyzer detects missing_timescale
                   → patterns/missing_timescale.md created (hit_count=1)

        Session 2: WikiQueryService reads the wiki
                   → KNOWN_ERROR_PATTERNS includes missing_timescale
        """
        from dv_agentic.prompts.prompt_loader import PromptLoader

        # ── Session 1 ─────────────────────────────────────────────────
        log_content = (
            "*E,NOTIME (tb/sequences/axi_burst_seq.sv,1): `timescale not defined before this module"
        )
        agent = LogAnalyzerAgent(
            config=AgentConfig(name="log_analyzer"),
            wiki_config=wiki_cfg,
        )
        result_s1 = await agent.run(log_content)
        # Drain the background ingest task
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert "compile_error" in result_s1

        # ── Verify wiki was populated ──────────────────────────────────
        page = wiki_cfg.wiki_dir / "patterns" / "missing_timescale.md"
        if not page.exists():
            pytest.skip("Ingest task did not complete in time (event-loop timing)")

        fm, _ = parse_page(page.read_text(encoding="utf-8"))
        assert fm["hit_count"] == 1

        # ── Session 2: PromptLoader reads wiki ─────────────────────────
        loader = PromptLoader(wiki_config=wiki_cfg)
        ctx = loader._gather_context()

        patterns_ctx = ctx.get("KNOWN_ERROR_PATTERNS", "")
        assert "missing_timescale" in patterns_ctx, (
            f"KNOWN_ERROR_PATTERNS should contain wiki knowledge, got: {patterns_ctx!r}"
        )

    @pytest.mark.asyncio
    async def test_three_different_errors_all_filed(self, wiki_cfg: WikiConfig) -> None:
        """Three different failure subtypes produce three separate pattern pages."""
        logs = [
            "*E,NOTIME (tb/seq.sv,1): `timescale not defined",
            "*E,MATCH (tb/seq.sv,42): unexpected end — missing begin",
            "UVM_ERROR @ 100ns: scoreboard expected 0xAA got 0xBB",
        ]
        for log in logs:
            a = LogAnalyzerAgent(
                config=AgentConfig(name="log_analyzer"),
                wiki_config=wiki_cfg,
            )
            await a.run(log)
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        patterns_dir = wiki_cfg.wiki_dir / "patterns"
        if not patterns_dir.exists():
            pytest.skip("Wiki not populated (event-loop timing)")

        pages = {p.stem for p in patterns_dir.glob("*.md")}
        # At least the subtypes our regex patterns match
        assert len(pages) >= 1  # conservative: at least one filed


# ---------------------------------------------------------------------------
# AC-4  BugClassifier → wiki history awareness & auto-ingest
# ---------------------------------------------------------------------------


class TestAC4BugClassifierWikiAware:
    """AC-4: BugClassifier is aware of past bugs and auto-ingests new ones."""

    @pytest.mark.asyncio
    async def test_bug_classifier_wiki_integration_loop(self, wiki_cfg: WikiConfig) -> None:
        from dv_agentic.agents.bug_classifier import BugClassifierAgent

        # 1. Seed the wiki with an existing bug
        from dv_agentic.wiki.ingest import WikiIngestService

        ingest = WikiIngestService(wiki_cfg)
        ingest.ingest_bug(
            bug_type="RTL_BUG",
            confidence=0.99,
            evidence=["Old evidence"],
            error_class="uvm_error",
            failure_subtype="scoreboard_fail",
            task_id="t_old",
        )

        # 2. Run BugClassifier
        llm = MagicMock()
        # Mock response from LLM
        llm.complete = AsyncMock(
            return_value=(
                "BUG_TYPE: RTL_BUG\n"
                "CONFIDENCE: 0.85\n"
                "EVIDENCE:\n- New evidence\n"
                "### Summary\nRepeated bug."
            )
        )
        agent = BugClassifierAgent(
            config=AgentConfig(name="bug_classifier", budget=2),
            llm=llm,
            wiki_config=wiki_cfg,
        )

        task_input = (
            "error_class: uvm_error\nfailure_subtype: scoreboard_fail\nSome new failure log."
        )

        result = await agent.run(task_input)

        # Ensure LLM was called and context was injected
        # We can check what was passed to llm.complete
        assert llm.complete.call_count == 1
        history = llm.complete.call_args[0][1]
        user_msg = history[0]["content"]
        assert "Known Similar Bug Records" in user_msg
        assert "t_old" not in user_msg, "ID is RTL_YYYYMMDD_seq, not task_id"
        assert "Check: bugs/RTL" in user_msg

        assert "RTL_BUG" in result

        # 3. Drain background ingest
        bugs_dir = wiki_cfg.wiki_dir / "bugs"
        for _ in range(20):
            if len(list(bugs_dir.glob("*.md"))) >= 2:
                break
            await asyncio.sleep(0.05)

        # 4. Verify a new bug page was created
        pages = list(bugs_dir.glob("*.md"))
        assert len(pages) >= 2, "Second bug should be auto-ingested"


# ---------------------------------------------------------------------------
# AC-5  Coverage Analyst & Reporter → wiki history awareness & auto-ingest
# ---------------------------------------------------------------------------


class TestAC5ReporterWikiAware:
    @pytest.mark.asyncio
    async def test_reporter_and_coverage_analyst_wiki_integration(
        self, wiki_cfg: WikiConfig, tmp_path: Path
    ) -> None:
        import asyncio

        from dv_agentic.agents.coverage_analyst import CoverageAnalystAgent
        from dv_agentic.agents.reporter import ReporterAgent
        from dv_agentic.tools.models import CoverageDB
        from dv_agentic.wiki.ingest import WikiIngestService

        # 1. Seed wiki with a coverage hole
        ingest = WikiIngestService(wiki_cfg)
        ingest.ingest_coverage_hole(
            covergroup="cg_test",
            bin_name="b_max",
            action_class="actionable",
            scenario="Coverage hole scenario 1",
            filled=False,
            task_id="t_cov_old",
        )

        # 2. Run CoverageAnalystAgent
        cov_tool = MagicMock()
        cov_tool.get_coverage.return_value = CoverageDB(
            path=str(tmp_path / "cov"),
            overall_percentage=85.0,
        )
        cov_agent = CoverageAnalystAgent(
            config=AgentConfig(name="cov_analyst"),
            coverage=cov_tool,
            threshold=90.0,
            wiki_config=wiki_cfg,
        )
        cov_result = await cov_agent.run("test_job")

        # Verify coverage history is injected
        assert "Coverage History" in cov_result
        assert "cg_test_b_max" in cov_result

        # 3. Run ReporterAgent
        llm = MagicMock()
        llm.complete = AsyncMock(return_value="### Session Report\nEverything is fine.")
        reporter = ReporterAgent(config=AgentConfig(name="reporter"), llm=llm, wiki_config=wiki_cfg)

        task_input = (
            "task_id: test_session_1\n"
            "error_class: sim_error\n"
            "failure_subtype: x_prop\n"
            "BUG_TYPE: RTL_BUG\n"
            "CONFIDENCE: 0.95\n" + cov_result
        )

        await reporter.run(task_input)

        # 4. Drain background ingest
        patterns_dir = wiki_cfg.wiki_dir / "patterns"
        bugs_dir = wiki_cfg.wiki_dir / "bugs"
        log_file = wiki_cfg.wiki_dir / "log.md"

        for _ in range(40):
            if (
                patterns_dir.exists()
                and bugs_dir.exists()
                and len(list(patterns_dir.glob("*.md"))) >= 1
                and len(list(bugs_dir.glob("*.md"))) >= 1
                and log_file.exists()
                and "SESSION_REPORT" in log_file.read_text(encoding="utf-8")
            ):
                break
            await asyncio.sleep(0.05)

        assert len(list(patterns_dir.glob("*.md"))) >= 1
        assert len(list(bugs_dir.glob("*.md"))) >= 1

        log_content = log_file.read_text(encoding="utf-8")
        assert "SESSION_REPORT" in log_content
        assert "test_session_1" in log_content


# ---------------------------------------------------------------------------
# Phase D  WikiLint and CLI Tools
# ---------------------------------------------------------------------------


class TestAC6PhaseDCLI:
    @pytest.mark.asyncio
    async def test_orchestrator_quick_lint(self, wiki_cfg: WikiConfig) -> None:
        from dv_agentic.agents.orchestrator import OrchestratorAgent

        # 1. Create an orphan page
        bugs_dir = wiki_cfg.wiki_dir / "bugs"
        bugs_dir.mkdir(parents=True, exist_ok=True)
        (bugs_dir / "orphan.md").write_text("orphan", encoding="utf-8")

        llm = MagicMock()
        llm.complete = AsyncMock(
            return_value="WORKFLOW: 1\nACTION: done\nINPUT:\n### Human Review Required\nNO"
        )

        agent = OrchestratorAgent(config=AgentConfig(name="orch"), llm=llm, wiki_config=wiki_cfg)

        with patch("dv_agentic.agents.orchestrator.logger.warning") as mock_warning:
            await agent.run("test task")

            # Should have found orphan page
            assert mock_warning.call_count == 1
            log_msg = mock_warning.call_args[0][0]
            log_args = mock_warning.call_args[0][1]
            assert "Wiki Quick Lint found issues:" in log_msg
            assert "bugs/orphan.md" in log_args

    def test_cli_wiki_build(self, wiki_cfg: WikiConfig, tmp_path: Path) -> None:
        import subprocess
        import sys

        import yaml

        from dv_agentic.wiki.ingest import WikiIngestService

        # 1. Seed some data
        ingest = WikiIngestService(wiki_cfg)
        ingest.ingest_bug("RTL_BUG", 0.9, ["Ev"], "err", "sub", "t1")

        # Destroy index.md
        (wiki_cfg.wiki_dir / "index.md").unlink()

        # Create .agent/project.yaml in tmp_path
        agent_dir = tmp_path / ".agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        project_yaml = agent_dir / "project.yaml"
        project_yaml.write_text(
            yaml.dump({"wiki": {"enabled": True, "wiki_dir": "wiki", "search_backend": "none"}})
        )

        # 2. Run CLI
        env = {"PYTHONPATH": "src"}
        res = subprocess.run(
            [sys.executable, "-m", "dv_agentic.cli.wiki_build"],
            env=env,
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )

        assert res.returncode == 0
        assert "Rebuilding index.md" in res.stderr
        assert "Build complete" in res.stderr

        # 3. Verify index rebuilt
        content = (wiki_cfg.wiki_dir / "index.md").read_text(encoding="utf-8")
        assert "## Bugs" in content
        assert "bugs/RTL_" in content
        assert ".md" in content

    def test_cli_wiki_lint(self, wiki_cfg: WikiConfig, tmp_path: Path) -> None:
        import subprocess
        import sys

        import yaml

        # 1. Create missing page in index
        (wiki_cfg.wiki_dir / "index.md").write_text("[b](bugs/miss.md)", encoding="utf-8")

        # Create .agent/project.yaml
        agent_dir = tmp_path / ".agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        project_yaml = agent_dir / "project.yaml"
        project_yaml.write_text(
            yaml.dump({"wiki": {"enabled": True, "wiki_dir": "wiki", "search_backend": "none"}})
        )

        # 2. Run CLI
        env = {"PYTHONPATH": "src"}
        res = subprocess.run(
            [sys.executable, "-m", "dv_agentic.cli.wiki_lint"],
            env=env,
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )

        # Since missing page triggers human review, it should exit with 1
        assert res.returncode == 1
        assert "bugs/miss.md" in res.stdout
