# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/anlit75/dv-agentic-system/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/anlit75/dv-agentic-system/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/anlit75/dv-agentic-system/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/anlit75/dv-agentic-system/releases/tag/v0.1.0
