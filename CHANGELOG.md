# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `tests/test_models.py` — parametrized unit tests for `CompileResult` (status × 2), `SimResult` (defaults, error summary, `cov_db_path`, timeout, field preservation), `CoverageDB` (boundary percentages 0 / 50 / 87.5 / 100)
- `tests/test_adapter_factory.py` — parametrized tests for factory case-insensitivity and unknown-name error paths (including empty string); GHDL/cocotb cases auto-skipped when `cocotb.runner` is unavailable (Linux-only)
- `tests/test_adapters_impl.py` — unit tests for the new Phase 1 adapters with mock-based validation and file-discovery checks
- `[tool.pytest.ini_options]` in `pyproject.toml`: `testpaths = ["tests"]`, `addopts = "--tb=short"`
- `[tool.ruff.lint.per-file-ignores]` — suppress `S101` (assert) for `tests/**`
- `src/dv_agentic/tools/adapters/icarus.py` — new adapter for Icarus Verilog simulator using `cocotb.runner`
- `src/dv_agentic/tools/adapters/verilator.py` — new adapter for Verilator simulator using `cocotb.runner`
- `src/dv_agentic/tools/adapters/pyuvm.py` — new adapter for pyuvm functional coverage parsing from text logs

### Changed

- `src/dv_agentic/tools/adapters/__init__.py` — replaced eager top-level imports with lazy `importlib.import_module()` via `_load()` helper; registered `icarus`, `verilator`, and `pyuvm` in the factory registries
- `.github/workflows/ci.yml` — corrected `--cov=agents --cov=tools` to `--cov=dv_agentic` (matches the installed package name under `src/` layout)
- `ROADMAP.md` — marked Phase 1 (Adapter Matrix Completion) as completed

### Fixed

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

[Unreleased]: https://github.com/anlit75/dv-agentic-system/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/anlit75/dv-agentic-system/releases/tag/v0.1.0
