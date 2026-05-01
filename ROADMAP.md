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
| `src/dv_agentic/tools/interface.py` — `SimulatorTool` / `CoverageTool` ABC | ✅ | Fully defined, including type hints |
| `src/dv_agentic/tools/models.py` — `SimResult` / `CompileResult` / `CoverageDB` | ✅ | `dataclass` fully implemented |
| `src/dv_agentic/tools/adapters/xcelium.py` | ✅ | `subprocess` calls, error parsing, timeout handling |
| `src/dv_agentic/tools/adapters/ghdl_cocotb.py` | ✅ | `cocotb` runner integration, environment isolation, consistent log naming |
| `src/dv_agentic/tools/adapters/__init__.py` — factory `get_simulator_adapter()` | ✅ | Supports `"xcelium"` / `"ghdl"` / `"cocotb"` |
| `src/dv_agentic/agents/base.py` — `BaseAgent` / `AgentConfig` ABC | ✅ | Run loop and budget check skeletons |
| pre-commit / ruff / mypy static analysis and hooks | ✅ | 0 errors, 0 type issues, bound to git hooks |
| `sample/sample-project/.agent/project.yaml` | ✅ | Complete `project.yaml` example |
| `sample/sample-org-dv-profiles/teams/` | 🔨 | Directory created, pending `sample_team/` contents |
| `src/dv_agentic/profiles/_template/` | 🔨 | Directory created, pending schema YAMLs |

## Phase 1 — Adapter Matrix Completion 🔨

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
| pyuvm coverage report parser | 📋 | Parse pyuvm `UVMCoverage` output, map to `CoverageDB` model; add `get_coverage_adapter("pyuvm")` |

### External CI Lightweight Simulators (Planned)

> For external CI pipelines without commercial licenses, running in different environments than `ghdl_cocotb.py`, belonging to separate adapters.

| Adapter | Status | Description |
|---------|------|------|
| `src/dv_agentic/tools/adapters/icarus.py` | 📋 | Icarus Verilog (`iverilog` / `vvp`); pure Verilog / SystemVerilog compile + run |
| `src/dv_agentic/tools/adapters/verilator.py` | 📋 | Verilator; C++ model generation, `make` execution; can be combined with `lcov` for line coverage |

**Acceptance Criteria**: All ✅ items must pass `mypy`; 📋 items must pass `mypy` upon completion, and update the factory mapping.

## Phase 2 — LLM Client Layer 📋

**Objective**: Establish an abstract LLM client, allowing Agents to switch models between internal and external environments.

| Item | Status | Description |
|------|------|------|
| `src/dv_agentic/tools/llm/api.py` — External client (Claude / GPT) | 📋 | OpenAI-compatible interface |
| `src/dv_agentic/tools/llm/opencode.py` — Internal OpenCode client | 📋 | Internal endpoint, same interface as the external client |
| LLM `BaseLLMClient` ABC definition | 📋 | Ensure consistent adapter pattern |

## Phase 3 — Core Agent Implementation 🔒 (Depends on Phase 1, 2)

**Objective**: Step-by-step implementation of 8 specialized Agents based on `BaseAgent`.

### Recommended Execution Order

```
OrchestratorAgent (Requires other agents for complete handoffs, can do routing logic first)
    ↓
SimControllerAgent ← Depends on adapter matrix (Phase 1)
    ↓
SpecAnalystAgent   ← Depends on LLM client (Phase 2)
CodeGeneratorAgent ← Depends on LLM client (Phase 2)
    ↓
LogAnalyzerAgent   ← Depends on SimController output
WaveAnalyzerAgent  ← Depends on SimController output (Optional, later stage)
    ↓
CoverageAnalystAgent ← Depends on coverage adapter (Phase 1)
BugClassifierAgent   ← Depends on LogAnalyzer output + LLM
    ↓
ReporterAgent      ← Aggregates outputs from all agents
```

| Agent | Status | Description |
|-------|------|------|
| `src/dv_agentic/agents/orchestrator.py` | 📋 | Task routing, handoff coordination |
| `src/dv_agentic/agents/sim_controller.py` | 📋 | Call adapters, branch management, feedback loop |
| `src/dv_agentic/agents/spec_analyst.py` | 📋 | Parse spec docs, generate `vplan.yaml` |
| `src/dv_agentic/agents/code_generator.py` | 📋 | Generate / modify SV / pyuvm code, commit in branch |
| `src/dv_agentic/agents/log_analyzer.py` | 📋 | Parse sim logs, classify errors, trigger `bug_classifier` |
| `src/dv_agentic/agents/wave_analyzer.py` | 📋 | Parse VCD / FSDB, provide feedback to `code_generator` |
| `src/dv_agentic/agents/coverage_analyst.py` | 📋 | Analyze coverage DB, suggest test scenarios |
| `src/dv_agentic/agents/bug_classifier.py` | 📋 | Classify DUT vs. TB bugs, confidence threshold gatekeeping |
| `src/dv_agentic/agents/reporter.py` | 📋 | Aggregate session results, output markdown / YAML |

## Phase 4 — Prompt System 🔒 (Depends on Phase 2)

**Objective**: Establish base prompt templates and a profile patch mechanism, realizing a portable "environment-agnostic" design.

| Item | Status | Description |
|------|------|------|
| `src/dv_agentic/prompts/orchestrator.md` | 📋 | — |
| `src/dv_agentic/prompts/spec_analyst.md` | 📋 | — |
| `src/dv_agentic/prompts/code_generator.md` | 📋 | — |
| `src/dv_agentic/prompts/sim_controller.md` | 📋 | — |
| `src/dv_agentic/prompts/log_analyzer.md` | 📋 | — |
| `src/dv_agentic/prompts/wave_analyzer.md` | 📋 | — |
| `src/dv_agentic/prompts/coverage_analyst.md` | 📋 | — |
| `src/dv_agentic/prompts/bug_classifier.md` | 📋 | — |
| `src/dv_agentic/prompts/reporter.md` | 📋 | — |
| Prompt composition logic (base + team patch + ip_type rules) | 📋 | Implemented in `orchestrator` or a standalone loader |

## Phase 5 — Profile and Project Configuration System 🔒 (Depends on Phase 3, 4)

**Objective**: Complete the three-layer configuration loading (`project.yaml` → team profile → ip_type rules), allowing different DV teams to use this system without changing the agent core.

| Item | Status | Description |
|------|------|------|
| `src/dv_agentic/profiles/_template/team.yaml` schema | 🔨 | Directory exists, pending YAML contents |
| `src/dv_agentic/profiles/_template/ip_type.yaml` schema | 📋 | — |
| `src/dv_agentic/profiles/_template/prompt_patch.md` formatting guide | 📋 | — |
| `project.yaml` loader (parse, validate, compose config) | 📋 | Reads `composition.*`, dynamically selects adapter |
| `sample/sample-org-dv-profiles/teams/sample_team/` full example | 🔨 | Directory exists, pending `team.yaml` / `vip_index.yaml` / `prompt_patch.md` |
| `sample/sample-org-dv-profiles/ip-types/` example | 📋 | `axi/`, `pcie/` protocol rules |

## Phase 6 — Session State and VCS Integration 🔒 (Depends on Phase 3)

**Objective**: Achieve persistent state for Agent tasks and a complete Git workflow.

| Item | Status | Description |
|------|------|------|
| `memory.db` SQLite schema design | 📋 | Session state, known bugs, task trace |
| `tasks/{task_id}.yaml` writing logic | 📋 | Records for each iteration |
| `git checkout -b agent/{task_id}` automation | 📋 | Implemented in `sim_controller` / `code_generator` |
| Commit message format guardrails | 📋 | `[agent] {reason} · task:{task_id}` |
| Safe exit flow when budget is depleted | 📋 | Ensure clean branch, leave a task trace |

## Phase 7 — Subagent Installation Scripts and Tool Integration 🔒 (Depends on Phase 5)

**Objective**: Allow users to symlink subagent `.md` files to the expected paths of Claude Code / Cursor / OpenCode with one click.

| Item | Status | Description |
|------|------|------|
| `.agent/subagents/` canonical `.md` generation logic | 📋 | Composed from base + patch by prompt loader |
| `scripts/install-agents.sh` | 📋 | Create symlinks for `.claude/agents/`, `.cursor/rules/`, `.agent/` |
| Post-installation verification script | 📋 | Confirm that tools can discover correct subagents |

## Long-term / Optional

| Item | Description |
|------|------|
| `WaveAnalyzerAgent` full implementation | Requires VCD / FSDB parsing libraries; low priority |
| Replace `memory.db` with vector DB | Enable semantic search (similarity matching for known bugs) |
| SVN branch support | VCS integration in Phase 6 focuses on Git initially, SVN reserved for later |
| `pip install` publish workflow | CI/CD configuration, PyPI or internal package registry |
| External CI integration (GitHub Actions) | Run full verification loop using GHDL + cocotb + lcov adapters |

## Current Progress Snapshot (2026-05-01)

```
Layer 1 (Shared Package)
  src/dv_agentic/tools/         ██████████  100%  Interfaces + Xcelium + GHDL completed
  src/dv_agentic/agents/        ██░░░░░░░░   15%  base.py skeleton, remaining 8 agents pending
  src/dv_agentic/prompts/       ░░░░░░░░░░    0%  Directory exists, pending contents
  src/dv_agentic/profiles/      █░░░░░░░░░   10%  _template/ directory exists, schemas pending

Layer 2 (Profile Repo)
  sample/                       ██░░░░░░░░   20%  Directory structure created, YAMLs pending

Layer 3 (Project Implant)
  sample/sample-project/
    .agent/                     ███░░░░░░░   30%  project.yaml example completed;
                                                  subagents/, memory.db, tasks/ pending
```

**Next Milestone**: Enter Phase 2, implement the abstract LLM Client layer (`src/dv_agentic/tools/llm/api.py` and `src/dv_agentic/tools/llm/opencode.py`), providing model access capabilities for the core Agents.
