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
| Sphinx documentation compilation and autodiscovery | ✅ | Complete `docs/` build scripts and full autodiscovery of the `cli/` subpackage |
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

## Phase 6 — Session State and VCS Integration 📋 (Temporarily Postponed)

**Objective**: Achieve persistent state for Agent tasks and a complete Git workflow.

| Item | Status | Description |
|------|------|------|
| `memory.db` SQLite schema design | 📋 | Session state, known bugs, task trace |
| `tasks/{task_id}.yaml` writing logic | 📋 | Records for each iteration |
| `git checkout -b ai-task/{task_id}` automation | 📋 | Implemented in `sim_controller` / `code_generator` |
| Commit message format guardrails | 📋 | `[agent] {reason} · task:{task_id}` |
| Safe exit flow when budget is depleted | 📋 | Ensure clean branch, leave a task trace |

## Phase 7 — Subagent Installation Scripts and Tool Integration ✅ (Completed)

**Objective**: Allow users to symlink subagent `.md` files to the expected paths of Claude Code / Cursor / OpenCode with one click.

| Item | Status | Description |
|------|------|------|
| `.agent/subagents/` canonical `.md` generation logic | ✅ | Composed from base + patch by prompt loader inside install_agents.py |
| `scripts/install-agents.sh` | ✅ | Cross-platform bash script supporting Windows with auto-detection of python and virtualenvs |
| Post-installation verification script | ✅ | Generates a run-time installation validation and checks |

## Phase 8 — Research-Guided DV Agentic Optimization (NVIDIA CVDP Insights) 📋

**Objective**: Optimize the core `dv_agentic` prompt patterns, self-review checklists, and execution loops based on key testbench-only failure modes identified in state-of-the-art LLMs (e.g. Claude 3.7 / GPT-4.1) within NVIDIA's CVDP (Comprehensive Verilog Design Problems) paper, while strictly forbidding any RTL reading or writing.

### 🛡️ System Scope & RTL Access Prohibitions
The `dv_agentic` system is designed strictly for testbench development (TB-only). Reading, writing, or accessing RTL design source files is strictly prohibited. The sole sources of hardware architectural and interface definitions are the SPEC and the verification plan.

| Existing Violations | Core Correction Task |
|----------------------|-----------------------|
| **Violation 1**: `CodeGeneratorAgent._write_files()` lacks path restriction. | Add path validation in `_write_files()` using `_TB_ALLOWED_DIRS` check, raising `ValueError` on RTL paths. |
| **Violation 2**: `code_generator.md` Core Responsibilities are vague. | Update responsibilities to specify modification of TB-only files and state RTL is completely off-limits for both reading and writing (rely solely on SPEC/vplan). |
| **Violation 3**: Self-Review Checklist lacks RTL write-protection. | Add strict RTL read/write-protection assertions to the self-review constraints. |

---

### 📋 Phase 8 Optimization Tasks

| Direction | Item | Status | Description |
|-----------|------|--------|-------------|
| **Direction 1: Path Controls** | **Strict TB Root Path Enforcement** | 📋 | Implement path validation in `CodeGeneratorAgent._write_files()` to restrict writing/reading to allowed directories (e.g., `tb`, `tests`, `env`). Refine `code_generator.md` Core Responsibilities to declare RTL completely off-limits. |
| **Direction 2: Checklist** | **cid13 (Testbench Checker) Defenses** | 📋 | Expand `Self-Review Checklist` in `code_generator.md` to prevent CVDP's top failures in Checker Gen (22.77% pass rate), including missing timescales, unmatched blocks, and missing bounds checks. |
| **Direction 3: Feedback Loop** | **Fine-Grained Failure Diagnostics** | 📋 | Upgrade `LogAnalyzerAgent` to output granular failure details (not just generic `error_class`). Update `OrchestratorAgent` to stop execution and escalate to human review if failure types shift across loops. |

#### 🔍 Detailed Improvement Items

##### 1. Immediate: Path Control & Writing Constraints
* **`CodeGeneratorAgent._write_files()` Path Validation**: Verify file paths against `project.yaml` directories. Only allow writing to `paths.tb_root`, `paths.test_dir`, and general sub-folders under a permitted whitelist (e.g., `tb`, `tests`, `env`, `sequences`, `agents`, `scoreboards`). Explicitly block any reads or writes targeted at `paths.rtl_root` or any files in the RTL directories.
* **`code_generator.md` Core Responsibilities Clarification**: Explicitly state: *"Modify existing testbench files (sequences, scoreboards, coverage groups, monitors, drivers, env) to fix compile errors or simulation failures. RTL source files are completely forbidden for both reading and writing — never access or open them. The sole sources for hardware architectural and interface definitions are the SPEC and the verification plan (vplan.yaml)."*

##### 2. Immediate: Checklist Enhancements (cid13 Defenses)
Introduce a specialized, rigorous **SystemVerilog Testbench checklist** into the `Self-Review Checklist` in `code_generator.md` to prevent CVDP's top failures in Checker Gen (22.77% pass rate):
* **Timescale Declaration**: Ensure a proper ``timescale` is declared at the top of files (the largest failure cluster in CVDP `cid13`).
* **Unmatched Blocks**: Ensure every block pair (`begin`/`end`, `fork`/`join`) is perfectly balanced.
* **No Mixed Assignments**: Do not mix blocking (`=`) and non-blocking (`<=`) assignments, particularly inside `always` blocks.
* **Multiple Drivers Protection**: Check that no signal/reg is driven by more than one procedural block.
* **Initialization Guard**: All variables must be initialized before they are read.
* **Array Bounds Check**: Explicitly check index ranges before any array or queue accesses.
* **Cycle-Accurate Alignment**: Non-blocking assignments and delays must not cause state offsets or counter drifts.
* **Explicit Width Handling**: Expression results of smaller widths must be explicitly padded/concatenated (e.g. `{{4'b0}, ...}`) when assigned to larger targets (preventing ALU zero-extension bugs).
* **Coverage Verification**: Coverage bin names must match the `vplan.yaml` definitions *exactly*, and the checker must cover the full scope, including non-happy paths.

##### 3. Medium-Term: Re-evaluating the "Iterative Improvement" Assumption
* **Granular Failure Types**: `LogAnalyzerAgent` must parse compiler/simulation logs into specific categories (e.g., `syntax_error`, `timing_error`, `coverage_miss`, `interface_mismatch`).
* **Dynamic Escalation in Orchestrator**: Instead of iterating blindly through the budget:
  * If consecutive failures have the same failure type, let the agent continue.
  * If failure types shift dynamically between runs (indicating a complex, shifting error state), immediately stop and escalate to the user with a detailed diagnostics report, saving token budget.

## Long-term / Optional

| Item | Description |
|------|------|
| `WaveAnalyzerAgent` full implementation | Requires VCD / FSDB parsing libraries; low priority |
| Replace `memory.db` with vector DB | Enable semantic search (similarity matching for known bugs) |
| SVN branch support | VCS integration in Phase 6 focuses on Git initially, SVN reserved for later |
| `pip install` publish workflow | CI/CD configuration, PyPI or internal package registry |
| External CI integration (GitHub Actions) | Run full verification loop using GHDL + cocotb + lcov adapters |

## Progress Snapshot (2026-05-09)

```
Layer 1 (Shared Package)
  src/dv_agentic/tools/         ██████████  100%  Interfaces + All Adapters completed
  src/dv_agentic/agents/        ██████████  100%  All 8 agents completed and fully verified
  src/dv_agentic/prompts/       ██████████  100%  PromptLoader + Levels 0-2 context injection completed
  src/dv_agentic/cli/           ██████████  100%  All CLI entrypoints fully tested (90% global coverage) & fully documented
  src/dv_agentic/profiles/      ██████████  100%  _template/ directory and all schemas completed

Layer 2 (Profile Repo)
  sample/                       ██████████  100%  All sample team, IP-type, and VIP catalog profiles completed

Layer 3 (Project Implant)
  sample/sample-project/
    .agent/                     ██████████  100%  Project configuration system and subagent installer completed
```

**Next Milestone**: Enter Phase 8, implement research-guided optimizations for the `dv_agentic` system based on the NVIDIA CVDP paper insights. Phase 6 is temporarily postponed.
