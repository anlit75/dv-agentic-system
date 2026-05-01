# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Add `[tool.mypy]` config with `strict = true` and `[[tool.mypy.overrides]]` to suppress `import-not-found` for `cocotb.*`, which ships no PEP 561 stubs

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
