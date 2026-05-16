# ROADMAP — dv-agentic-system

> AI Agentic System for UVM / pyuvm Verification
> Written according to `docs/agentic-system-structure.md` specifications, reflecting the current implementation progress of the repo.
>
> **Tool Environment**
> | Environment | Simulator | Coverage | OS |
> |------|-----------|----------|---------|
> | Internal | Xcelium 25.03.007 | IMC 24.06.a001 + Verisium 25.12.081 | RHEL 8.4 |
> | External | GHDL (LLVM/MCO backend) + cocotb | pyuvm functional coverage | — |

## Legend

| Symbol | Description |
|------|------|
| ✅ | Completed (Usable) |
| 🔨 | Skeleton created, pending implementation |
| 📋 | Specification defined, pending implementation |
| 🔒 | Blocked until previous items are completed |

## Phase 0 — Infrastructure ✅ (Completed)

**Objective**: Establish an executable Python package skeleton, ensuring the toolchain is available.

| Item | Status | Description |
|------|------|------|
| `pyproject.toml` and `uv` environment | ✅ | `requires-python >= 3.11`; `uv.lock` locked |
| `.env.example` and secret management | ✅ | Added `.env` to `.gitignore` and provided template |
| `src/dv_agentic/tools/interface.py` — `SimulatorTool` / `CoverageTool` ABC | ✅ | Fully defined, including type hints |
| `src/dv_agentic/tools/models.py` — `SimResult` / `CompileResult` / `CoverageDB` | ✅ | `dataclass` fully implemented; `wall_time_sec` added |
| `src/dv_agentic/tools/adapters/` (Lazy loading) | ✅ | cocotb lazy loading implemented for all adapters |
| `src/dv_agentic/prompts/loader.py` — `PromptLoader` | ✅ | Level 0-2 injection, type-safe context mapping |
| `src/dv_agentic/prompts/context.py` — Context Schemas | ✅ | `ProjectContext`, `SimulatorConfig`, `VCSConfig` dataclasses |
| `src/dv_agentic/prompts/*.tmpl.md` — Standalone templates | ✅ | `code_generator`, `log_analyzer` follow standalone rules |
| `src/dv_agentic/agents/base.py` — `BaseAgent` / `AgentConfig` ABC | ✅ | `Literal["internal", "external"]` environment alignment |
| pre-commit / ruff / mypy static analysis and hooks | ✅ | 0 errors, 0 type issues, bound to git hooks |
| MkDocs Material documentation with mkdocstrings | ✅ | Modern documentation portal with auto-docstring extraction, dark/light theme, and live-reload |
| CLI test suite and coverage reinforcement | ✅ | Comprehensive unit/integration testing, raising global coverage to 90% |
| `sample/sample-project/.agent/project.yaml` | ✅ | Complete `project.yaml` example |
| `sample/sample-org-dv-profiles/teams/` | 🔨 | Directory created, pending `sample_team/` contents |
| `src/dv_agentic/profiles/_template/` | 📋 | Directory created, pending schema YAMLs |

## Phase 1 — Adapter Matrix Completion ✅ (Completed)

**Objective**: Complete the remaining simulator and coverage adapters, covering official internal tools and lightweight external CI tools.

### Internal (Xcelium + IMC + Verisium on RHEL 8.4)

| Adapter | Status | Description |
|---------|------|------|
| `src/dv_agentic/tools/adapters/xcelium.py` | ✅ | Xcelium 25.03.007; compile, run, error parse, timeout |
| `src/dv_agentic/tools/adapters/imc.py` | ✅ | Read IMC 24.06.a001 coverage DB; parse `imc -reportstats`; Verisium 25.12.081 `vsif` merge |

### External (GHDL LLVM/MCO + cocotb + pyuvm)

| Adapter | Status | Description |
|---------|------|------|
| `src/dv_agentic/tools/adapters/ghdl_cocotb.py` | ✅ | GHDL LLVM/MCO backend; `cocotb` runner; environment isolation; consistent log naming |
| pyuvm coverage report parser | ✅ | Parse pyuvm `UVMCoverage` output, map to `CoverageDB` model; add `get_coverage_adapter("pyuvm")` |

### External CI Lightweight Simulators (Planned)

> For external CI pipelines without commercial licenses, running in different environments than `ghdl_cocotb.py`, belonging to separate adapters.

| Adapter | Status | Description |
|---------|------|------|
| `src/dv_agentic/tools/adapters/icarus.py` | ✅ | Icarus Verilog (`iverilog` / `vvp`); pure Verilog / SystemVerilog compile + run |
| `src/dv_agentic/tools/adapters/verilator.py` | ✅ | Verilator; C++ model generation, `make` execution; can be combined with `lcov` for line coverage |

**Acceptance Criteria**: All ✅ items must pass `mypy`; 📋 items must pass `mypy` upon completion, and update the factory mapping.

## Phase 2 — LLM Client Layer ✅ (Completed)

**Objective**: Establish an abstract LLM client, allowing Agents to switch models between internal and external environments.

| Item | Status | Description |
|------|------|------|
| `src/dv_agentic/tools/llm/interface.py` — `BaseLLMClient` ABC | ✅ | Unified interface for all LLM clients |
| `src/dv_agentic/tools/llm/api.py` — External client (Claude / GPT) | ✅ | OpenAI-compatible interface |
| `src/dv_agentic/tools/llm/local.py` — Internal/Local LLM client | ✅ | Internal endpoint, same interface as the external client |

## Phase 3a — Non-LLM Agent Implementation ✅ (Completed)

**Objective**: Implementation of specialized Agents that do not require LLM access, enabling parallel development with Phase 2.

| Agent | Status | Description |
|-------|------|------|
| `src/dv_agentic/agents/sim_controller.py` | ✅ | Call adapters, branch management, feedback loop |
| `src/dv_agentic/agents/log_analyzer.py` | ✅ | Parse sim logs, classify errors, regex-based parsing |
| `src/dv_agentic/agents/coverage_analyst.py` | ✅ | Analyze coverage DB, suggest test scenarios based on stats |
| Base prompt templates (`prompts/*.tmpl.md`) | ✅ | Minimal prompts for non-LLM logic if needed |

## Phase 3b — LLM-Powered Agent Implementation ✅ (Completed)

**Objective**: Implementation of Agents that leverage LLM reasoning and code generation. Prompt development is integrated into this phase.

| Agent | Status | Description |
|-------|------|------|
| `src/dv_agentic/agents/spec_analyst.py` | ✅ | Parse spec docs, generate `vplan.yaml` + `prompts/spec_analyst.tmpl.md` |
| `src/dv_agentic/agents/bug_classifier.py` | ✅ | Classify DUT vs. TB bugs + `prompts/bug_classifier.tmpl.md` |
| `src/dv_agentic/agents/orchestrator.py` | ✅ | Task routing, handoff coordination + `prompts/orchestrator.tmpl.md` |
| `src/dv_agentic/agents/reporter.py` | ✅ | Aggregate session results + `prompts/reporter.tmpl.md` |
| `src/dv_agentic/agents/code_generator.py` | ✅ | Generate / modify code + `prompts/code_generator.tmpl.md` |

## Phase 4 — Profile and Project Configuration System ✅ (Completed)

**Objective**: Complete the three-layer configuration loading (`project.yaml` → team profile → ip_type rules), allowing different DV teams to use this system without changing the agent core.

| Item | Status | Description |
|------|------|------|
| `src/dv_agentic/profiles/_template/team.yaml` schema | ✅ | Schema YAML template for DV team profiles |
| `src/dv_agentic/profiles/_template/ip_type.yaml` schema | ✅ | Schema YAML template for IP-type protocol and coverage guidelines |
| `src/dv_agentic/profiles/_template/prompt_patch.md` formatting guide | ✅ | Template for adding custom organization prompt overrides |
| `project.yaml` loader (parse, validate, compose config) | ✅ | Fully implemented in config/loader.py with 4-level resolution |
| `sample/sample-org-dv-profiles/teams/sample_team/` full example | ✅ | Realistic team.yaml, vip_index.yaml, and prompt_patch.md examples |
| `sample/sample-org-dv-profiles/ip-types/` example | ✅ | Fully structured AXI and PCIe protocol rules |

## Phase 6 — VCS Integration and Task Tracking 📋 (Temporarily Postponed)

**Objective**: Achieve persistent task tracking and a complete Git workflow.

| Item | Status | Description |
|------|------|------|
| `tasks/{task_id}.yaml` writing logic | 📋 | Records for each iteration |
| `git checkout -b ai-task/{task_id}` automation | 📋 | Implemented in `sim_controller` / `code_generator` |
| Commit message format guardrails | 📋 | `[agent] {reason} · task:{task_id}` |
| Safe exit flow when budget is depleted | 📋 | Ensure clean branch, leave a task trace |

## Phase 7 — Subagent Installation Scripts and Tool Integration ✅ (Completed)

**Objective**: Install sub-agent `.md` files and mirrored `tools/` / `skills/` assets into Claude Code (`.claude/`) and OpenCode (`.opencode/`) discovery paths.

| Item | Status | Description |
|------|------|------|
| Dual-format agent installs (`.claude/agents/`, `.opencode/agents/`) | ✅ | Composed from `*.tmpl.md` via PromptLoader inside `install_agents.py`; OpenCode YAML preserved for OpenCode |
| `scripts/install-agents.sh` | ✅ | Cross-platform bash script supporting Windows with auto-detection of python and virtualenvs |
| Post-installation verification script | ✅ | Generates a run-time installation validation and checks |

## Phase 8 — Research-Guided DV Agentic Optimization (NVIDIA CVDP Insights) ✅ (Completed)

**Objective**: Optimize the core `dv_agentic` prompt patterns, self-review checklists, and execution loops based on key testbench-only failure modes identified in state-of-the-art LLMs (e.g. Claude 3.7 / GPT-4.1) within NVIDIA's CVDP (Comprehensive Verilog Design Problems) paper, while strictly forbidding any RTL reading or writing.

### 🛡️ System Scope & RTL Access Prohibitions
The `dv_agentic` system is designed strictly for testbench development (TB-only). Reading, writing, or accessing RTL design source files is strictly prohibited. The sole sources of hardware architectural and interface definitions are the SPEC and the verification plan.

| Resolved Violations | Resolution Action |
|----------------------|-----------------------|
| **Violation 1 Resolved**: `CodeGeneratorAgent._write_files()` lacks path restriction. | Implemented `_validate_path()` in `_write_files()` checking against `DEFAULT_TB_ALLOWED_DIRS` and raising `ValueError` on RTL or traversal paths. |
| **Violation 2 Resolved**: `code_generator.tmpl.md` Core Responsibilities are vague. | Refined core responsibilities in `code_generator.tmpl.md` to explicitly declare RTL completely forbidden and testbench-only scopes. |
| **Violation 3 Resolved**: Self-Review Checklist lacks RTL write-protection. | Added clear, strict instructions in the `code_generator` system prompt asserting RTL as completely off-limits for reading and writing. |

---

### ✅ Phase 8 Optimization Tasks

| Direction | Item | Status | Description |
|-----------|------|--------|-------------|
| **Direction 1: Path Controls** | **Strict TB Root Path Enforcement** | ✅ | Implemented strict path validation in `CodeGeneratorAgent._write_files()` restricting writes to permitted subdirectories. Refined `code_generator.tmpl.md` to make RTL completely off-limits. |
| **Direction 2: Checklist** | **cid13 (Testbench Checker) Defenses** | ✅ | Implemented a highly rigorous, specialized SystemVerilog Testbench checklist in `code_generator.tmpl.md` covering timescales, unmatched blocks, assignments, multi-drivers, indices bounds, widths padding, etc. |
| **Direction 3: Feedback Loop** | **Fine-Grained Failure Diagnostics** | ✅ | Configured `LogAnalyzerAgent` to output granular, regex-backed failure subtypes. Upgraded `OrchestratorAgent` to dynamically detect failure subtype shifts across iterations and immediately escalate with detailed diagnostic reports. |

#### 🔍 Detailed Improvement Items

##### 1. Path Control & Writing Constraints ✅ (Completed)
* **`CodeGeneratorAgent._write_files()` Path Validation**: Verifies file paths against `project.yaml` directories. Only allows writing to `paths.tb_root`, `paths.test_dir`, and general sub-folders under a permitted whitelist (`tb`, `tests`, `env`, `sequences`, `agents`, `scoreboards`, `monitors`, `drivers`, `coverage`, `checkers`, `assertions`). Explicitly blocks any reads/writes targeted at RTL files or using `..` path traversal.
* **`code_generator.tmpl.md` Core Responsibilities Clarification**: Explicitly states: *"Modify existing testbench files (sequences, scoreboards, coverage groups, monitors, drivers, env) to fix compile errors or simulation failures. RTL source files are completely forbidden for both reading and writing — never access or open them. The sole sources for hardware architectural and interface definitions are the SPEC and the verification plan (vplan.yaml)."*

##### 2. Checklist Enhancements (cid13 Defenses) ✅ (Completed)
Introduced a specialized, rigorous **SystemVerilog Testbench checklist** into the `Self-Review Checklist` in `code_generator.tmpl.md` to prevent CVDP's top failures in Checker Gen (22.77% pass rate):
* **Timescale Declaration**: Ensures a proper ``timescale` is declared at the top of files (the largest failure cluster in CVDP `cid13`).
* **Unmatched Blocks**: Ensures every block pair (`begin`/`end`, `fork`/`join`) is perfectly balanced.
* **No Mixed Assignments**: Mixed blocking (`=`) and non-blocking (`<=`) assignments are strictly forbidden in state-holding logic.
* **Multiple Drivers Protection**: Verifies that no signal/reg is driven by more than one procedural block.
* **Initialization Guard**: All variables must be initialized before they are read.
* **Array Bounds Check**: Explicitly checks index ranges before any array or queue accesses.
* **Cycle-Accurate Alignment**: Non-blocking assignments and delays must not cause state offsets or counter drifts.
* **Explicit Width Handling**: Expression results of smaller widths must be explicitly padded/concatenated (e.g. `{{4'b0}, ...}`) when assigned to larger targets (preventing ALU zero-extension bugs).
* **Coverage Verification**: Coverage bin names must match the `vplan.yaml` definitions *exactly*, and the checker must cover the full scope, including non-happy paths.

##### 3. Dynamic Escalation & Failure Diagnostics ✅ (Completed)
* **Granular Failure Types**: `LogAnalyzerAgent` parses compiler/simulation logs into specific categories (e.g., `syntax_error`, `timing_error`, `coverage_miss`, `interface_mismatch`).
* **Dynamic Escalation in Orchestrator**: Instead of iterating blindly through the budget:
  * If consecutive failures have the same failure type, the agent continues.
  * If failure types shift dynamically between runs (indicating a complex, shifting error state), it immediately stops and escalates to the user with a detailed diagnostics report, saving token budget.

## Phase 9 — LLM Wiki Knowledge Integration ✅ (Completed, v0.7.0)

**Objective**: Eliminate per-session knowledge reset by introducing a Git-versioned Markdown wiki (`.agent/wiki/`) that compounds verification knowledge across sessions. Based on Karpathy's LLM Wiki pattern — knowledge is compiled at write time, not re-derived at query time.

> **Architecture**: Three-layer separation — Raw Source (immutable sim logs/coverage reports) → Wiki Layer (LLM-maintained Markdown) → Schema Layer (PromptLoader injection via placeholders). No existing Agent logic is modified; integration uses three seam points only.

### Phase 9A — Minimal Viable Integration ✅

| Item | Status | Description |
|------|------|------|
| `src/dv_agentic/wiki/manager.py` — `WikiConfig` dataclass | ✅ | Parse `project.yaml` `wiki:` block; `enabled: false` default for backward compatibility |
| `src/dv_agentic/wiki/ingest.py` — `WikiIngestService.ingest_pattern()` | ✅ | Auto-update `patterns/{failure_subtype}.md` hit count and fix history after each session |
| `src/dv_agentic/wiki/query.py` — `WikiQueryService.get_known_error_patterns()` | ✅ | Return top-K pattern summaries within token budget (≤ 500 tokens per category) |
| `src/dv_agentic/wiki/search.py` — `BM25SearchIndex` | ✅ | Pure-Python BM25 search via `bm25s[core]`; air-gapped RHEL 8.4 compatible; persistent index at `.agent/wiki/.search_index/`; transparent fallback to `KeywordSearchIndex` when `bm25s` absent |
| `src/dv_agentic/prompts/prompt_loader.py` — `_load_wiki_context()` | ✅ | Extended `_gather_context()` to inject `{{KNOWN_ERROR_PATTERNS}}`, `{{KNOWN_RTL_BUGS}}`, `{{COVERAGE_HOLE_HISTORY}}`, `{{WIKI_PATTERN_SUMMARY}}` from wiki (wiki values override static profile values) |
| `src/dv_agentic/config/config_loader.py` — wiki block parsing | ✅ | Parse and validate `wiki:` section in `project.yaml`; build `WikiConfig` |
| `src/dv_agentic/cli/wiki_search.py` | ✅ | `python -m dv_agentic.cli.wiki_search "<query>" [--category bugs\|patterns\|coverage]` |
| `tests/test_wiki_*.py` | ✅ | Unit tests with mocked `bm25s`; verify backward compatibility when `wiki.enabled: false` |

**Acceptance Criteria Met**: `missing_timescale` hit count auto-increments across sessions; `{{KNOWN_ERROR_PATTERNS}}` populated on next session start; all existing tests pass.

### Phase 9B — Bug Archiving and Classifier History Awareness ✅

| Item | Status | Description |
|------|------|------|
| `WikiIngestService.ingest_bug()` | ✅ | Create/update `bugs/RTL_{date}_{id}.md` or `bugs/TB_{date}_{id}.md` with evidence and YAML frontmatter |
| `BugClassifierAgent` wiki pre-query | ✅ | Query `wiki/bugs/` before classifying; inject similar historical bugs to raise confidence (target: +0.1 vs. cold start) |
| `wiki/log.md` append-only writes | ✅ | Every ingest appends a structured entry; no deletion or modification of existing entries |
| `wiki/index.md` auto-update | ✅ | Atomically updated after every ingest; reflects all pages with frontmatter metadata |

**Acceptance Criteria Met**: `BugClassifier` confidence ≥ 0.1 higher with historical bugs than cold-start; `bugs/_index.md` correctly lists all open bugs.

### Phase 9C — Coverage Archiving and Reporter Auto-Ingest ✅

| Item | Status | Description |
|------|------|------|
| `WikiIngestService.ingest_coverage_hole()` | ✅ | Create/update `coverage/{covergroup}_{bin}.md` with action class and fill history |
| `WikiIngestService.ingest_session()` | ✅ | Orchestrate all three ingest methods from `ReporterAgent` output |
| `ReporterAgent` async auto-ingest | ✅ | Non-blocking `asyncio.create_task()` at end of `run()`; failure is non-fatal |
| `CoverageAnalystAgent` wiki pre-query | ✅ | Load `{{COVERAGE_HOLE_HISTORY}}` before analysis to avoid re-attempting protocol-blocked bins |

### Phase 9D — Wiki Lint and Full CLI ✅

| Item | Status | Description |
|------|------|------|
| `src/dv_agentic/wiki/lint.py` — `WikiLintService` | ✅ | Detect orphan pages, broken links, stale open bugs (> 90 days), missing pages, uncited claims |
| `OrchestratorAgent` startup quick lint | ✅ | Non-blocking `asyncio.create_task()` on session start; logs warnings if human review required |
| `src/dv_agentic/cli/wiki_lint.py` | ✅ | `python -m dv_agentic.cli.wiki_lint [--depth quick\|full]` |
| `src/dv_agentic/cli/wiki_build.py` | ✅ | Rebuild BM25 index from scratch: `python -m dv_agentic.cli.wiki_build` |
| Integration test: knowledge compounding | ✅ | 3-session workflow verifying hit_count increments and confidence lift |

**Optional dependency**: `pip install "dv-agentic-system[wiki]"` (adds `bm25s[core]>=0.2.0`; no impact when `wiki.enabled: false`).

---

## Long-term / Optional

| Item | Description |
|------|------|
| `WaveAnalyzerAgent` full implementation | Requires VCD / FSDB parsing libraries; low priority |
| Phase 9E — Semantic search upgrade | When wiki > 500 pages, switch `search_backend: "qmd"` in `project.yaml`; `QMDSearchIndex` implements same `WikiSearchIndex` ABC — no Agent changes required |
| SVN branch support | VCS integration in Phase 6 focuses on Git initially, SVN reserved for later |
| `pip install` publish workflow | CI/CD configuration, PyPI or internal package registry |
| External CI integration (GitHub Actions) | Run full verification loop using GHDL + cocotb + lcov adapters |

## Progress Snapshot (2026-05-16)

```
Layer 1 (Shared Package)
  src/dv_agentic/tools/         ██████████  100%  Interfaces + All Adapters completed
  src/dv_agentic/agents/        ██████████  100%  All 8 agents completed + Phase 8 CVDP optimizations + Phase 9 wiki-awareness
  src/dv_agentic/prompts/       ██████████  100%  PromptLoader + Levels 0-2 context injection + wiki context injection
  src/dv_agentic/cli/           ██████████  100%  All CLI entrypoints (+ wiki_search, wiki_lint, wiki_build) fully tested
  src/dv_agentic/profiles/      ██████████  100%  _template/ directory and all schemas completed
  src/dv_agentic/wiki/          ██████████  100%  Phase 9A-9D completed (ingest, query, search, lint, manager)

Layer 2 (Profile Repo)
  sample/                       ██████████  100%  All sample team, IP-type, and VIP catalog profiles completed

Layer 3 (Project Implant)
  sample/sample-project/
    .agent/                     ██████████  100%  Project configuration system and subagent installer completed
```

**Next Milestone**: Phase 6 (VCS Integration and Task Tracking) — persistent `tasks/{task_id}.yaml` writing, `git checkout -b ai-task/{task_id}` automation, commit message format guardrails, and safe exit flow when budget is depleted. Phase 9E (semantic search upgrade to `qmd`) activates when wiki exceeds 500 pages.
