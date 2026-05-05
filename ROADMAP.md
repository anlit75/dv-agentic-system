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
| `src/dv_agentic/prompts/*.md` — Standalone templates | ✅ | `code_generator`, `log_analyzer` follow standalone rules |
| `src/dv_agentic/agents/base.py` — `BaseAgent` / `AgentConfig` ABC | ✅ | `Literal["internal", "external"]` environment alignment |
| pre-commit / ruff / mypy static analysis and hooks | ✅ | 0 errors, 0 type issues, bound to git hooks |
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
| Base prompt templates (`prompts/*.md`) | ✅ | Minimal prompts for non-LLM logic if needed |

## Phase 3b — LLM-Powered Agent Implementation ✅ (Completed)

**Objective**: Implementation of Agents that leverage LLM reasoning and code generation. Prompt development is integrated into this phase.

| Agent | Status | Description |
|-------|------|------|
| `src/dv_agentic/agents/spec_analyst.py` | ✅ | Parse spec docs, generate `vplan.yaml` + `prompts/spec_analyst.md` |
| `src/dv_agentic/agents/bug_classifier.py` | ✅ | Classify DUT vs. TB bugs + `prompts/bug_classifier.md` |
| `src/dv_agentic/agents/orchestrator.py` | ✅ | Task routing, handoff coordination + `prompts/orchestrator.md` |
| `src/dv_agentic/agents/reporter.py` | ✅ | Aggregate session results + `prompts/reporter.md` |
| `src/dv_agentic/agents/code_generator.py` | ✅ | Generate / modify code + `prompts/code_generator.md` |

## Phase 4 — Profile and Project Configuration System 📋 (Planned)

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

## Progress Snapshot (2026-05-05)

```
Layer 1 (Shared Package)
  src/dv_agentic/tools/         ██████████  100%  Interfaces + All Adapters completed
  src/dv_agentic/agents/        ██████████  100%  All 8 agents (LogAnalyzer, SimController, CoverageAnalyst, SpecAnalyst, BugClassifier, Orchestrator, Reporter, CodeGenerator) completed
  src/dv_agentic/prompts/       ██████████  100%  PromptLoader + Levels 0-2 context injection fully implemented and tested
  src/dv_agentic/profiles/      █░░░░░░░░░   10%  _template/ directory exists, schemas pending

Layer 2 (Profile Repo)
  sample/                       ██░░░░░░░░   20%  Directory structure created, YAMLs pending

Layer 3 (Project Implant)
  sample/sample-project/
    .agent/                     ███░░░░░░░   30%  project.yaml example completed;
                                                  subagents/, memory.db, tasks/ pending
```

**Next Milestone**: Enter Phase 4, finalize the three-layer configuration loading system and provide full sample profiles for teams and IP protocols.
