# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.1] - 2026-05-18

### Added

- **Offline dependency bundling & environments**:
  - Added parallel matrix builds supporting both Python 3.11 and 3.12 packages for release tagging in `.github/workflows/offline-bundle.yml`.
  - Restructured workflow into sequential jobs (`prep` -> `build-bundle` matrix -> `release`) to prevent parallel GitHub API race conditions when generating a release.
  - Integrated `dv-agentic-system[wiki]` dependencies (via `--with-wiki` flag) in `scripts/offline-download.sh` so the BM25 offline wiki search RAG feature is fully functional and bundled by default in tag releases.
  - Automatically bundled essential files and directories into the offline tarball: `.env.example`, `AGENTS.md`, `.gitignore`, `.gitattributes`, `uv.lock`, `.python-version`, and reference `sample/` and `commands/` directories to facilitate robust local setup and deployment.

## [0.8.0] - 2026-05-16

### Added

- **Internal services layer** (`src/dv_agentic/tools/services/`): Extracted deterministic, non-LLM workflows from standalone agents into reusable services aligned with single-orchestrator design (`AGENTS.md`).
  - `services/log_analyzer.py` — `LogAnalyzerService` with `FailureSummary` parsing, wiki-aware pattern ingest hooks, and `run(log_content)`.
  - `services/coverage_analyst.py` — `CoverageAnalystService` with threshold checks and wiki hole-history context.
  - `services/sim_controller.py` — `SimControllerService` with `run(task, max_runs=10)` (replaces `BaseAgent.step()` loop), compile/run orchestration, and `SimReport` output.
- **Orchestrator auto-chain**: After `run_code_generator`, the Orchestrator automatically invokes `SimControllerService` then `LogAnalyzerService` without an extra LLM routing turn; log output is fed back as the effective code-generator step result. Dynamic escalation on shifting `failure_subtype` remains active during the chain.
- **`OrchestratorAgent._build_sim_task()`**: Parses inline JSON, fenced JSON blocks, or heuristic `test=` / `seed:` fields from decision `INPUT` into a `SimTask` so auto-chain does not pass Code Generator markdown to the simulator.
- **`PromptLoader.load_temperature()`**: Reads `temperature` from prompt YAML frontmatter; defaults to `0.0` when missing or invalid.
- **LLM temperature passthrough**: `BaseLLMClient.complete(..., temperature=None)`; `LLMAPIClient` and `LocalLLMClient` include `temperature` in request payloads when set. All LLM agents load frontmatter temperature in `_load_system_prompt()`.
- **Tests**:
  - `tests/test_prompts.py` — `TestLoadTemperature` (9 cases) for frontmatter parsing and package templates.
  - `tests/test_orchestrator.py` — coverage dispatch via `_cov_svc`, `TestBuildSimTask`, auto-chain `SimTask` wiring.
  - `tests/test_cli.py` — `test_orchestrator_cli_wires_simulator_and_coverage_services` verifies CLI passes adapters into `OrchestratorAgent`, not `sub_agents`.
- `.pre-commit-config.yaml`: Local `no-cjk-in-source-and-docs` hook (`language: pygrep`) blocks CJK Unified Ideographs (UTF-8) in `src/`, `tests/`, `tools/`, `scripts/`, `agents/`, `skills/`, `docs/`, `.github/`, and root project docs (`README.md`, `CHANGELOG.md`, `ROADMAP.md`, `AGENTS.md`, `mkdocs.yml`, `pyproject.toml`); excludes `sample/`, `_build/`, and `.venv/`. Enforces English-only source, prompts, and documentation per `AGENTS.md`.

### Changed

- **Architecture (8 agents → 5 LLM agents + 3 services)**: `Orchestrator`, `SpecAnalyst`, `CodeGenerator`, `BugClassifier`, and `Reporter` remain LLM agents; `LogAnalyzer`, `CoverageAnalyst`, and `SimController` are internal services invoked by the Orchestrator (or standalone CLI). Documented in `docs/agentic-system.md` and `docs/agentic-system-structure.md`.
- **`OrchestratorAgent` routing**: `VALID_ACTIONS` reduced to seven — `run_code_generator`, `run_coverage_analyst`, `run_bug_classifier`, `run_spec_analyst`, `run_reporter`, `done`, `escalate`. Removed `run_sim_controller` and `run_log_analyzer` (handled by auto-chain).
- **`run_coverage_analyst` dispatch**: Uses injected `CoverageAnalystService` (`_cov_svc`) when a coverage adapter is present; no longer requires `sub_agents["coverage_analyst"]`.
- **`cli/orchestrator.py`**: `_build_sub_agents()` builds four LLM sub-agents only; passes `simulator` and `coverage` adapters directly to `OrchestratorAgent`.
- **Compatibility shims** (`agents/log_analyzer.py`, `coverage_analyst.py`, `sim_controller.py`): Thin subclasses delegating to services; preserve `LogAnalyzerAgent`, `CoverageAnalystAgent`, and `SimControllerAgent` import paths and standalone CLIs.
- **Prompt templates**:
  - `orchestrator.tmpl.md` — workflow diagram and valid actions aligned with implementation; `temperature: 0`; explicit note not to emit removed sim/log actions.
  - `bug_classifier.tmpl.md` — `temperature: 0` for deterministic classification.
  - `log_analyzer.tmpl.md`, `coverage_analyst.tmpl.md`, `sim_controller.tmpl.md` — standalone CLI notes when used outside the Orchestrator.
- **OpenCode TypeScript wrappers** (`tools/log_analyzer.ts`, `coverage_analyst.ts`, `sim_controller.ts`): Minor CLI flag alignment with service entry points.

### Fixed

- `tests/test_adapter_factory.py`: Guard `importlib.util.find_spec("cocotb.runner")` with try/except so collection does not fail when cocotb is not installed.
- `tools/llm/api.py` and `tools/llm/local.py`: Renamed HTTP response variable to avoid mypy `no-redef` on `body`.
- Service shim `__init__` signatures: Added type annotations and explicit `__all__` exports for `FailureSummary`, `CoverageSummary`, and `SimReport`.

## [0.7.0] - 2026-05-16

### Added

- **Wiki module** (`src/dv_agentic/wiki/`): Introduced the LLM Wiki Knowledge Integration layer — a Git-versioned Markdown knowledge base (`.agent/wiki/`) that compounds verification knowledge across sessions, eliminating per-session knowledge reset.
  - `wiki/manager.py` — `WikiConfig` dataclass (parsed from `project.yaml` `wiki:` block), `load_wiki_config()`, `atomic_write()`, `parse_page()`, `serialize_page()`, and `today_str()` / `now_iso()` shared utilities. All page I/O uses temp-file + `os.replace` to prevent partial writes.
  - `wiki/ingest.py` — `WikiIngestService` with `ingest_pattern()` (Phase A: auto-create / update `patterns/{failure_subtype}.md` with hit-count and fix-history) and `ingest_bug()` (Phase B: create `bugs/{RTL|TB}_{date}_{id}.md` with YAML frontmatter and evidence). Returns `WikiIngestResult` with lists of pages created / updated.
  - `wiki/query.py` — `WikiQueryService` with `get_known_error_patterns()`, `get_pattern_summary()`, `get_pattern_page()`, `get_known_rtl_bugs()` (Phase B), and `get_coverage_history()` (Phase C stub). All methods degrade gracefully to `""` on empty wiki or I/O error.
  - `wiki/search.py` — `WikiSearchIndex` abstract base; `BM25SearchIndex` (uses `bm25s[core]`, air-gapped RHEL 8.4 compatible, persistent index at `.agent/wiki/.search_index/`) with transparent fallback to `KeywordSearchIndex` (zero extra dependencies) when `bm25s` is not installed.
  - `wiki/lint.py` — `WikiLintService` with `run(depth="quick"|"full")` checking orphan pages, broken Markdown links, stale open bugs (> 90 days), missing pages referenced by `index.md`, and uncited claims.
- **Wiki CLI** (`src/dv_agentic/cli/`): Three new CLI entry-points for direct wiki operations.
  - `cli/wiki_search.py` — `python -m dv_agentic.cli.wiki_search "<query>" [--category bugs|patterns|coverage]`
  - `cli/wiki_lint.py` — `python -m dv_agentic.cli.wiki_lint [--depth quick|full]`
  - `cli/wiki_build.py` — `python -m dv_agentic.cli.wiki_build` (rebuild BM25 index from scratch)
- **Agent wiki integration** (five agents updated with optional wiki-awareness):
  - `agents/reporter.py` — `_ingest_to_wiki()` async background task (non-blocking `asyncio.create_task`) triggered at end of `run()` when `wiki_config.auto_ingest` is enabled.
  - `agents/orchestrator.py` — `_run_wiki_lint_quick()` async background lint on session start; logs warnings if `human_review_required`.
  - `agents/bug_classifier.py` — `_load_wiki_context()` queries `wiki/bugs/` before classifying, prepending similar historical bugs to raise confidence.
  - `agents/coverage_analyst.py` — loads `{{COVERAGE_HOLE_HISTORY}}` from wiki before analysis to avoid re-attempting protocol-blocked bins.
  - `agents/log_analyzer.py` — passes `failure_subtype` metadata to `WikiIngestService.ingest_pattern()` after each analysis.
- **PromptLoader wiki context injection** (`src/dv_agentic/prompts/prompt_loader.py`): Extended `_gather_context()` with `_load_wiki_context()` that populates four new placeholders — `{{KNOWN_ERROR_PATTERNS}}`, `{{KNOWN_RTL_BUGS}}`, `{{COVERAGE_HOLE_HISTORY}}`, `{{WIKI_PATTERN_SUMMARY}}` — from the wiki; wiki values override static profile values when present.
- **Config loader wiki block** (`src/dv_agentic/config/config_loader.py`): Parses and validates the new `wiki:` section in `project.yaml`; builds `WikiConfig`. Defaults to `enabled: false` for full backward compatibility.
- **Wiki test suite** (`tests/`): Seven new test modules covering unit and integration scenarios.
  - `test_wiki_ingest.py` — pattern creation, hit-count accumulation, bug page creation, append-only `log.md`, and atomic-write failure safety.
  - `test_wiki_query.py` — top-K ordering, empty-wiki graceful degradation, token-budget enforcement.
  - `test_wiki_search.py` — index build, BM25 relevance, incremental update; `bm25s`-conditional tests auto-skipped when the package is absent.
  - `test_wiki_lint.py` — orphan detection, stale-bug detection, clean-wiki pass.
  - `test_wiki_bug.py` — bug classification integration with wiki pre-query.
  - `test_wiki_coverage.py` — coverage hole ingest and history retrieval.
  - `test_wiki_integration.py` — three-session compounding workflow verifying hit-count growth and confidence lift; backward-compatibility check (`wiki.enabled: false`); wiki-failure non-fatal check.
- **Design specification** (`docs/llm-wiki-dv-agentic-spec.md`): Complete LLM Wiki × DV Agentic System integration specification covering architecture, data models, component interfaces, agent integration seam points, CLI spec, search-layer design, phased implementation plan, test strategy, and anti-patterns.

### Changed

- `pyproject.toml`: Added `wiki` optional-dependency group (`bm25s[core]>=0.2.0`); install with `pip install "dv-agentic-system[wiki]"`. No impact when `wiki.enabled: false`.
- `pyproject.toml` (`[tool.ruff.lint.per-file-ignores]`): Suppressed `T201` (print) for `cli/wiki_search.py` since `print()` is intentional in the CLI output path.

## [0.6.2] - 2026-05-16

### Added

- `ProjectContext` & `PromptLoader`: Implemented **Standardized Agent Discovery Paths** by refactoring core logic to use a canonical `project_root` convention.
- **Root Asset Directories**: Established `agents/`, `tools/`, and `skills/` at the project root as the industry-standard discovery locations for Claude Code and OpenCode.
- **Canonical tools directory**: Moved OpenCode TypeScript adapters plus `_run_agent.sh` under repository root `tools/` for installer mirroring into `.claude/tools/` and `.opencode/tools/`.
- `scripts/install-agents.sh`: Implemented a **Tiered Execution Strategy** with automated fallback logic (`uv` -> `virtualenv` -> `system python`) to ensure reliability in both connected and restricted environments.
- `tests/test_install_agents.py`: Tests for mirrored tools/skills assets and dual-format agent file generation.
- `.pre-commit-config.yaml`: Integrated the `add-license-header` hook to enforce SPDX license headers automatically across Python (`.py`), Shell (`.sh`), and TypeScript (`.ts`) source files.

### Changed

- `scripts/offline-download.sh`: Enhanced the offline bundling logic to include the new standard asset directories (`agents/`, `tools/`, `skills/`), ensuring complete functional parity in air-gapped deployments.
- `src/dv_agentic/cli/install_agents.py`: Refactored the CLI installer to prioritize project-level asset discovery, renamed legacy `worktree` references to `project_root`, split helper functions for maintainability, and writes **separate** `.claude/agents/` (Claude Code YAML) and `.opencode/agents/` (OpenCode YAML preserved from `*.tmpl.md`) outputs.
- `src/dv_agentic/cli/install_agents.py`: Mirrored `tools/` now includes underscore-prefixed helpers (e.g. `_run_agent.sh`); only dot-prefixed entries are skipped.
- `README.md`, `docs/agentic-system-structure.md`, `docs/prompt-system.md`, `ROADMAP.md`: Documentation aligned with dual-format agents and standard discovery paths.
- `README.md`: Upgraded the static version badge to a dynamic, Shields.io-powered GitHub Release badge that automatically syncs with the latest published version.
- Codebase-wide: Applied standardized SPDX-compliant copyright headers (`SPDX-FileCopyrightText` and `SPDX-License-Identifier`) recursively across all source code files.

## [0.6.1] - 2026-05-12

### Fixed

- `scripts/offline-download.sh` / `.github/workflows/offline-bundle.yml`: Resolved a critical compatibility issue where hardcoded Python 3.11 dependency wheels in the automated offline bundle made the installation fail or unusable on target Red Hat Enterprise Linux 8 (RH8) environments using other Python versions (such as Python 3.12). Refactored build workflows and release assets to compile and bundle dependencies dynamically matching the target Python version.
- `scripts/offline-install.sh`: Corrected the minimum Python environment version requirements check output from `>= 3.8` to `>= 3.11` to match the actual package metadata constraint in `pyproject.toml`, preventing confusing installation errors on air-gapped target hosts.

## [0.6.0] - 2026-05-11

### Added

- `scripts/offline-download.sh`: Added an automated dependency downloader script for internet-connected hosts that compiles a lean package tree (via `uv pip compile`), downloads dependencies as wheels (including `hatchling`, `pip`, `setuptools`, and `wheel`), and nests files cleanly under a `dv-agentic-system/` parent directory before archiving into `dv-agentic-system.tar.gz` to prevent tarbombing.
- `scripts/offline-install.sh`: Added a bulletproof, cross-platform offline installation script for air-gapped target machines (Linux & Windows Git Bash) that automates venv setup, offline local installations, and sub-agent prompt template compilation.
- `README.md`: Added **Option C: Air-Gapped Offline Setup** quickstart guide with optimized download and installation one-liners.

### Changed

- `scripts/offline-install.sh`: Enhanced Python executable detection to verify execution capability (via `python -c "import sys"`), preventing crashes and silent aborts caused by Windows Store dummy Python aliases (which return exit code 49).
- `scripts/offline-install.sh`: Switched from editable installation (`-e .`) to standard installation (`.`) to fully bypass the `editables` packaging requirement of the hatchling build backend, ensuring bulletproof offline pip compilation.
- `pyproject.toml`: Refactored `cocotb` and `pyuvm` from core `dependencies` to `[project.optional-dependencies]` (extras), ensuring a lightweight, pure enterprise UVM environment by default.
- `.gitignore`: Configured ignores to mask local wheel downloads (`dv_wheels/`) and all archive bundles (`*.tar.gz`).

## [0.5.1] - 2026-05-10

### Added

- `mkdocs.yml`: Added full configuration for MkDocs Material theme, including dark/light color palettes, code copying, dynamic highlights, admonitions, and `mkdocstrings` automatic docstrings-to-markdown rendering.
- `docs/index.md`: Created an elegant documentation homepage featuring system overviews, capability checklists, architectural mermaid diagrams, and quick-start instructions.
- `docs/api/agents.md`, `docs/api/tools.md`, `docs/api/cli.md`: Created structured documentation templates utilizing the `mkdocstrings` Python handler to dynamically extract and cross-reference docstrings.

### Changed

- `pyproject.toml`: Removed legacy `sphinx` and `sphinx-rtd-theme` dependencies; added `mkdocs`, `mkdocs-material`, and `mkdocstrings[python]`.
- `src/dv_agentic/docs.py`: Rewrote the build script to run `mkdocs build -d _build/html`, placing compiled outputs outside the source folder to prevent nesting loops.
- `.gitignore`: Replaced obsolete Sphinx exclusion rules with modern root-level `_build/` and `site/` ignores.
- `.github/workflows/docs.yml`: Swapped the GitHub Pages publishing directory from `./docs/_build/html` to `./_build/html`.
- `ROADMAP.md`: Updated Phase 0 and Phase 8 (NVIDIA CVDP Insights) statuses to fully Completed (✅) and advanced the project snapshot and next milestones.

### Removed

- Deleted legacy Sphinx boilerplate files including `docs/conf.py`, `docs/index.rst`, `docs/modules.rst`, and all autogenerated `docs/dv_agentic*.rst` API files.

## [0.5.0] - 2026-05-10

### Added

- `tests/test_log_analyzer_subtype.py`: Added a separate test suite to verify the granular, CVDP-informed failure subtype classification patterns.
- `tests/test_dynamic_escalation.py`: Added a separate test suite to verify the Orchestrator's immediate escalation behavior when failure subtypes shift.

### Changed

- `src/dv_agentic/agents/log_analyzer.py`: Implemented CVDP-informed failure subtype classification matching (e.g., `missing_timescale`, `unmatched_block`, `mixed_assignment`, etc.) to target mechanical error clusters in UVM/pyuvm verification, and added `failure_subtype` to the structured `FailureSummary` output.
- `src/dv_agentic/agents/orchestrator.py`: Implemented a dynamic escalation check that tracks failure subtypes from consecutive log analyzer results and escalates immediately when a subtype shift is detected, preventing unproductive agent iteration and saving token budget.

## [0.4.1] - 2026-05-10

### Added

- `src/dv_agentic/cli/main.py`: Added a high-visibility orange terminal safety warning alerting developers whenever the `--no-tb-guard` safety bypass flag is active.

### Changed

- `src/dv_agentic/prompts/`: Standardized the base prompt templates to use the `.tmpl.md` suffix (e.g., `code_generator.tmpl.md`, `sim_controller.tmpl.md`) to clearly segregate template definitions from live subagent configuration instances.
- `src/dv_agentic/config/config_loader.py` & `src/dv_agentic/prompts/prompt_loader.py`: Renamed `loader.py` files to resolve namespace collisions and import race conditions under strict python module scanning.
- `tests/ts_wrappers.test.ts`: Renamed TypeScript wrapper check script from `test_ts_wrappers.test.ts` to follow post-suffix style conventions cleanly.
- `src/dv_agentic/cli/_helpers.py`: Refactored standard shell termination helper function `die()` into modern, explicit `exit_with_error()`.
- `src/dv_agentic/agents/sim_controller.py`: Retargeted automatic VCS task-branch generation to use the `ai-task/{task_id}` prefix instead of `agent/{task_id}` to separate agent execution lines in shared git records.
- `docs/agentic-system-structure.md` & `ROADMAP.md`: Synchronized all documentation structures to reflect `.tmpl.md` file layout and the new `ai-task/` VCS workflow standard.

## [0.4.0] - 2026-05-10

### Added

- `src/dv_agentic/config/loader.py` & `__init__.py`: Completed the Three-Layer Configuration Loading system (Project -> Team Profile -> IP Protocol rules) supporting 4 levels of profiles directory resolution and robust fallback degradation.
- `src/dv_agentic/profiles/_template/`: Added canonical YAML and Markdown schema templates for DV team configs (`team.yaml`), IP rules (`ip_type.yaml`), and prompt patches (`prompt_patch.md`).
- `sample/sample-org-dv-profiles/`: Created concrete, realistic sample profiles for AXI and PCIe protocol rules and custom prompt patch overrides.
- `tests/test_config_loader.py`: Added 32 exhaustive unit tests covering environment overrides, loading behaviors, folder mapping priorities, and graceful degradation paths.
- `src/dv_agentic/cli/install_agents.py`: Implemented a dynamic sub-agent prompt template generator and compiler that injects level-1 profiles and formats frontmatter cleanly for Claude Code and Cursor.
- `scripts/install-agents.sh`: Implemented a cross-platform shell script wrapper supporting Windows MSYS/Git-Bash environment with auto-detection of python and virtualenv.
- `src/dv_agentic/cli/`: Fully implemented CLI entrypoints for all 8 Agents (`bug_classifier`, `code_generator`, `coverage_analyst`, `log_analyzer`, `orchestrator`, `reporter`, `sim_controller`, `spec_analyst`).
- `src/dv_agentic/cli/__init__.py`: Package-level initializer with Google-style/Sphinx module documentation enabling autodoc discovery.
- `src/dv_agentic/cli/_factory.py` & `_helpers.py`: Private CLI factory for dynamic LLM backend selection and CLI stream/error helper utilities.
- `src/dv_agentic/prompts/`: Standardized standalone prompt markdown templates for `bug_classifier.md`, `orchestrator.md`, `reporter.md`, and `spec_analyst.md`.
- `tests/test_cli.py`: Comprehensive CLI unit testing suite for all entrypoints and helper utilities, lifting global repository test coverage to **90%**.
- `.opencode/tools/`: TypeScript wrapper scripts matching each CLI tool for cross-platform integration in OpenCode/VSCode.
- `tests/test_ts_wrappers.test.ts`: Bun-based TypeScript test suite for wrapper scripts validation.

### Changed

- `.github/workflows/ci.yml`: Expanded CI pipeline to execute Pytest with coverage reports, pre-commit quality checks (Ruff, Mypy), and TypeScript Bun test execution.

## [0.3.0] - 2026-05-05

### Added

- `src/dv_agentic/tools/llm/api.py`: External LLM client (OpenAI-compatible) for Claude/GPT integration.
- `src/dv_agentic/tools/llm/local.py`: Internal/Local LLM client for on-premise model endpoints.
- `src/dv_agentic/agents/log_analyzer.py`: Regex-based simulation log analysis agent (Phase 3a).
- `src/dv_agentic/agents/sim_controller.py`: Agent for managing simulation execution loops and adapter coordination.
- `src/dv_agentic/agents/spec_analyst.py`: LLM-powered agent for parsing specifications into structured verification plans.
- `src/dv_agentic/agents/bug_classifier.py`: LLM-powered agent for root-cause classification (DUT vs. TB) of simulation failures.
- `src/dv_agentic/agents/orchestrator.py`: Multi-agent coordination agent for task routing and handoff management.
- `src/dv_agentic/agents/reporter.py`: Agent for aggregating session results into professional verification reports.
- `src/dv_agentic/agents/code_generator.py`: LLM-powered agent for SystemVerilog/UVM code generation and modification.
- Refactored `SimControllerAgent`, `LogAnalyzerAgent`, and `CoverageAnalystAgent` to offload blocking I/O and subprocess operations to separate threads using `asyncio.to_thread`.
- `src/dv_agentic/agents/coverage_analyst.py`: Agent for analyzing coverage results and suggesting test scenarios.
- `src/dv_agentic/tools/models.py`: Added `SimTask` dataclass for structured simulation task definitions.
- `tests/test_llm_clients.py`: Unit tests for local and API-based LLM clients.
- `tests/test_log_analyzer.py`: Comprehensive test suite for log failure classification patterns.
- `tests/test_sim_controller.py`: Unit tests for simulation controller task handling.
- `tests/test_coverage_analyst.py`: Unit tests for coverage analysis logic.
- `.env.example`: Template for required environment variables (LLM keys, base URLs).
- `pyproject.toml`: Added `pytest-asyncio` as a development dependency.

### Changed

- `AGENTS.md`: Added detailed behavioral guidelines (Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution).
- `ROADMAP.md`: Updated Phase 2 and Phase 3a status to reflect completion of LLM clients and non-LLM agents.
- `docs/agentic-system-structure.md`: Updated architecture diagram to include `local.py` LLM client.
- `docs/agentic-system.md`: Refined LLM access terminology for internal environments.
- `src/dv_agentic/agents/__init__.py`: Exported `LogAnalyzerAgent`, `SimControllerAgent`, and `CoverageAnalystAgent`.
- `src/dv_agentic/tools/llm/__init__.py`: Exported `LocalLLMClient` and `LLMAPIClient`.
- `.gitignore`: Added `.env` to ignore list.

## [0.2.0] - 2026-05-01

### Added

- `src/dv_agentic/tools/adapters/cocotb_base.py`: New `CocotbBaseAdapter` to centralize logic for `cocotb.runner` based simulators.
- `src/dv_agentic/agents/base.py`: `step()` method for automated budget management and iteration tracking.
- `tests/test_prompts.py`: Comprehensive unit tests for `PromptLoader` covering levels 0-2 context injection, indentation preservation, and blank line compression.
- `tests/test_agents.py`: New unit tests for agent budget management and budget exhaustion.
- `tests/test_adapters_impl.py`: Added missing unit tests for `GHDLCocotbAdapter` and error handling cases (build/sim failure).
- `src/dv_agentic/prompts/loader.py`: `PromptLoader` with Level 0-2 context injection and automated placeholder cleaning.
- `src/dv_agentic/prompts/context.py`: Type-safe schemas (`ProjectContext`, `SimulatorConfig`, `VCSConfig`) for structured prompt enrichment.
- `src/dv_agentic/tools/llm/interface.py`: `BaseLLMClient` abstract base class for tool-agnostic LLM integration.
- `docs/prompt-system.md`: Comprehensive documentation for the "Prompt as First-Class Citizen" architecture.
- New agent prompt templates: `code_generator.md`, `log_analyzer.md`, `sim_controller.md`, `coverage_analyst.md`.
- `tests/test_models.py` — parametrized unit tests for `CompileResult` (status × 2), `SimResult` (defaults, error summary, `cov_db_path`, timeout, field preservation), `CoverageDB` (boundary percentages 0 / 50 / 87.5 / 100)
- `tests/test_adapter_factory.py` — parametrized tests for factory case-insensitivity and unknown-name error paths (including empty string); GHDL/cocotb cases auto-skipped when `cocotb.runner` is unavailable (Linux-only)
- `tests/test_adapters_impl.py` — unit tests for the new Phase 1 adapters with mock-based validation and file-discovery checks
- `[tool.pytest.ini_options]` in `pyproject.toml`: `testpaths = ["tests"]`, `addopts = "--tb=short"`
- `[tool.ruff.lint.per-file-ignores]` — suppress `S101` (assert) for `tests/**`
- `src/dv_agentic/tools/adapters/icarus.py` — new adapter for Icarus Verilog simulator using `cocotb.runner`
- `src/dv_agentic/tools/adapters/verilator.py` — new adapter for Verilator simulator using `cocotb.runner`
- `src/dv_agentic/tools/adapters/pyuvm.py` — new adapter for pyuvm functional coverage parsing from text logs

### Changed

- `src/dv_agentic/tools/adapters/`: Refactored `ghdl_cocotb.py`, `icarus.py`, and `verilator.py` to inherit from `CocotbBaseAdapter`, reducing code duplication by ~60%.
- `tests/test_adapters_impl.py`: Enabled cocotb-based adapter tests on all platforms (including Windows) by mocking the `cocotb.runner` interface.
- `src/dv_agentic/tools/adapters/cocotb_base.py`: Improved `run()` method with robust testcase parsing (handles both `module` and `module.testcase` safely).
- `src/dv_agentic/prompts/loader.py`: Removed unused internal function `replace_match` and optimized injection logic.
- `src/dv_agentic/tools/models.py`: Added `wall_time_sec` to `SimResult` to support performance-aware budget management.
- `src/dv_agentic/agents/base.py`: Aligned `AgentConfig.environment` with the `internal`/`external` standard.
- `src/dv_agentic/tools/adapters/`: Refactored all `cocotb`-based adapters to use lazy-loading, ensuring module compatibility in lightweight CI environments.
- `src/dv_agentic/tools/adapters/__init__.py` — replaced eager top-level imports with lazy `importlib.import_module()` via `_load()` helper; registered `icarus`, `verilator`, and `pyuvm` in the factory registries
- `.github/workflows/ci.yml` — corrected `--cov=agents --cov=tools` to `--cov=dv_agentic` (matches the installed package name under `src/` layout)
- `ROADMAP.md` — Integrated Prompt System into Phase 0 Infrastructure and updated all current project statuses.

### Fixed

- `PromptLoader` safety: Replaced `assert` statements with `RuntimeError` in path validation logic (S101).
- `[tool.mypy]` config with `strict = true` and `[[tool.mypy.overrides]]` to suppress `import-not-found` for `cocotb.*`, which ships no PEP 561 stubs
- Removed stale `# type: ignore[arg-type]` annotation in `test_models.py` (flagged as `unused-ignore` by mypy strict)

## [0.1.0] - 2026-05-01

### Added

**Infrastructure & Toolchain (Phase 0)**

- `pyproject.toml` with `uv` lockfile; requires Python ≥ 3.11
- `pre-commit` hooks — `ruff` (lint + format) and `mypy` (strict type checking)
- GitHub Actions CI workflow (`.github/workflows/ci.yml`)

**Core Tool Abstractions**

- `src/dv_agentic/tools/interface.py` — `SimulatorTool` / `CoverageTool` ABCs with full type hints
- `src/dv_agentic/tools/models.py` — `SimResult`, `CompileResult`, `CoverageDB` dataclasses

**Simulator / Coverage Adapters**

- `src/dv_agentic/tools/adapters/xcelium.py` — Cadence Xcelium 25.03; compile, run, error parsing, timeout handling
- `src/dv_agentic/tools/adapters/imc.py` — Cadence IMC 24.06 coverage DB reader; `imc -reportstats` parser; Verisium 25.12 `vsif` merge support
- `src/dv_agentic/tools/adapters/ghdl_cocotb.py` — GHDL LLVM/MCO backend; `cocotb` runner; environment isolation; consistent log naming
- `src/dv_agentic/tools/adapters/__init__.py` — `get_simulator_adapter()` factory supporting `"xcelium"` / `"ghdl"` / `"cocotb"`

**Agent Foundation**

- `src/dv_agentic/agents/base.py` — `BaseAgent` / `AgentConfig` ABCs; run-loop and budget-check skeletons

**Sample Files & Documentation**

- `sample/sample-project/.agent/project.yaml` — complete `project.yaml` reference example
- `sample/sample-org-dv-profiles/teams/sample_team/team.yaml` — team profile skeleton
- `sample/sample-org-dv-profiles/ip-types/axi/protocol_rules.yaml` — AXI protocol rules example
- `docs/agentic-system.md` — system design document
- `docs/agentic-system-structure.md` — three-layer architecture specification
- `ROADMAP.md` — phased implementation plan (Phase 0 – 7)
- `AGENTS.md` — agent development guidelines and coding conventions

[Unreleased]: https://github.com/anlit75/dv-agentic-system/compare/v0.8.1...HEAD
[0.8.1]: https://github.com/anlit75/dv-agentic-system/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/anlit75/dv-agentic-system/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/anlit75/dv-agentic-system/compare/v0.6.2...v0.7.0
[0.6.2]: https://github.com/anlit75/dv-agentic-system/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/anlit75/dv-agentic-system/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/anlit75/dv-agentic-system/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/anlit75/dv-agentic-system/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/anlit75/dv-agentic-system/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/anlit75/dv-agentic-system/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/anlit75/dv-agentic-system/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/anlit75/dv-agentic-system/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/anlit75/dv-agentic-system/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/anlit75/dv-agentic-system/releases/tag/v0.1.0
