# Agentic System File Structure

## Layer Overview

```
Four independent existence layers:

  [1] dv-agentic-system/      ← Shared package (pip install)
  [2] {org}-dv-profiles/      ← Profile repo for each DV Team (per-org or per-team)
  [3] {project}/              ← Each verification project (existing UVM env)
       └── .agent/            ← Config & state (`project.yaml`, tasks, memory)
       └── tools/, skills/, .claude/, .opencode/  ← Standard discovery paths populated by install scripts
```

## Layer 1: dv-agentic-system/ (Shared Package)

```
dv-agentic-system/
│
├── src/
│   └── dv_agentic/
│       ├── agents/                        # Core logic for 8 Agents
│       │   ├── base.py                    # run loop, budget, handoff base
│       │   ├── orchestrator.py
│       │   ├── spec_analyst.py
│       │   ├── code_generator.py
│       │   ├── sim_controller.py
│       │   ├── log_analyzer.py
│       │   ├── wave_analyzer.py
│       │   ├── coverage_analyst.py
│       │   ├── bug_classifier.py
│       │   └── reporter.py
│       │
│       ├── tools/                         # Interface + all Adapter implementations (choose one)
│       │   ├── interface.py               # ABC definitions (SimulatorTool, CoverageTool, etc.)
│       │   ├── models.py                  # Shared return types (SimResult, CompileResult, etc.)
│       │   ├── adapters/
│       │   │   ├── xcelium.py             # Xcelium 25.03.007 (Internal Simulator)
│       │   │   ├── ghdl_cocotb.py         # GHDL LLVM/MCO + cocotb + pyuvm (External Simulator)
│       │   │   ├── imc.py                 # IMC 24.06 + Verisium 25.12 coverage (Internal)
│       │   │   ├── icarus.py              # Icarus Verilog (External CI, Planned)
│       │   │   └── verilator.py           # Verilator (External CI, Planned)
│       │   └── llm/
│       │       ├── local.py               # Internal/Local LLM client
│       │       └── api.py                 # External API client (Claude / GPT)
│       │
│       ├── prompts/                       # Base prompt templates (plain text, no environment knowledge)
│       │   ├── orchestrator.tmpl.md
│       │   ├── spec_analyst.tmpl.md
│       │   ├── code_generator.tmpl.md
│       │   ├── sim_controller.tmpl.md
│       │   ├── log_analyzer.tmpl.md
│       │   ├── wave_analyzer.tmpl.md
│       │   ├── coverage_analyst.tmpl.md
│       │   ├── bug_classifier.tmpl.md
│       │   └── reporter.tmpl.md
│       │
│       └── profiles/
│           └── _template/                 # Schema only, defines fields a profile should have
│               ├── team.yaml              # Field descriptions + example values
│               ├── ip_type.yaml
│               └── prompt_patch.md        # Patch format description
│
├── tools/                               # OpenCode TS tool adapters + `_run_agent.sh` (mirrored into `.opencode/tools/` / `.claude/tools/`)
├── skills/
│
├── scripts/
│   └── install-agents.sh                # Runs `install_agents`: agents + tools + skills into `.claude/` and `.opencode/`
│
├── pyproject.toml
└── README.md
```

## Layer 2: {org}-dv-profiles/ (Team Profile Repo)

```
{org}-dv-profiles/                 # Maintained by each DV Team, separate git repo
│                                  # Referenced via git submodule or pip
│
├── teams/
│   ├── team_cpu/
│   │   ├── team.yaml              # simulator, license server, coding rules
│   │   ├── vip_index.yaml         # Key VIP API references used by this team
│   │   └── prompt_patch.md        # Team-specific rules appended to base prompt
│   │
│   ├── team_mem/
│   │   ├── team.yaml
│   │   ├── vip_index.yaml
│   │   └── prompt_patch.md
│   │
│   └── team_io/
│       ├── team.yaml
│       ├── vip_index.yaml
│       └── prompt_patch.md
│
├── ip-types/                      # Protocol knowledge (sharable across multiple teams)
│   ├── axi/
│   │   ├── protocol_rules.yaml    # Legal state machines, timing constraints
│   │   └── coverage_taxonomy.yaml # Coverage bin categorization conventions
│   ├── pcie/
│   │   └── ...
│   └── ddr/
│       └── ...
│
└── vip_knowledge/                 # Structured VIP API documents (the only knowledge worth sharing)
    ├── axi_vip/
    │   ├── sequences.yaml         # Available sequences and parameters
    │   └── config_objects.yaml
    └── pcie_vip/
        └── ...
```

## Layer 3: {project}/ (Existing Verification Project)

```
{project_root}/                    # Existing UVM / pyuvm environment, structure untouched
│
├── .agent/                        # ← Config & session state for the agentic layer
│   │
│   ├── project.yaml               # Project config (compose profile, set budgets)
│   │
│   ├── vplan.yaml                 # SPEC Analyst generated / manually maintained vplan
│   │
│   ├── memory.db                  # SQLite, stores session state, known bugs
│   │
│   └── tasks/                     # Task records (includes agent trace for debug)
│       ├── {task_id}.yaml         # In-progress or completed tasks
│       └── ...
│
├── tools/                         # Standard root copy of OpenCode adapters + `_run_agent.sh` (source for installer)
├── skills/                        # Optional skill bundles (mirrored into tool-specific dirs)
│
├── .claude/
│   ├── agents/                    # Generated: Claude Code YAML + enriched prompt body
│   ├── tools/                     # Symlinks / copies from `tools/`
│   └── skills/                    # Symlinks / copies from `skills/`
│
├── .opencode/
│   ├── agents/                    # Generated: OpenCode YAML (same shape as `*.tmpl.md`) + enriched body
│   ├── tools/                     # Symlinks / copies from `tools/` (includes `_run_agent.sh`)
│   └── skills/                    # Symlinks / copies from `skills/`
│
├── tb/                            # Existing UVM environment (agents don't modify directly)
├── tests/                         #   ↑ Agents modify on a git branch
├── env/                           #     Merged only after human PR/MR review
└── ...
```

### project.yaml

```yaml
project:
  name: "soc_pcie_ep_verify"
  environment: internal            # internal | external

composition:
  team: team_io                   # → {org}-dv-profiles/teams/team_io/
  ip_types: [pcie, axi]           # → {org}-dv-profiles/ip-types/
  simulator: questa                # → tools/adapters/questa.py
  coverage: ucdb                  # → tools/adapters/ucdb.py

paths:
  spec_dir: "../docs/spec"
  tb_root:  "../tb"
  test_dir: "../tests"
  sim_work: "../sim_work"

budget:
  max_sim_runs:       10
  max_compile_retry:   3
  max_fix_iterations:  5
  sim_timeout_sec:  3600

guardrails:
  rtl_bug_require_review:    true
  code_change_require_review: true  # diff > 50 lines
  classifier_confidence_min:  0.75
```

## Subagent Discovery Mechanism

```
Canonical prompts live in dv-agentic-system: src/dv_agentic/prompts/*.tmpl.md

install-agents / python -m dv_agentic.cli.install_agents generates two outputs per agent:

  PromptLoader enrichment (team + IP rules; session omitted)
          │
          ├──────────────► .claude/agents/{agent}.md     (Claude Code front matter + body)
          │
          └──────────────► .opencode/agents/{agent}.md   (OpenCode front matter unchanged + body)

Run once:
  bash dv-agentic-system/scripts/install-agents.sh
```

Structure of `.claude/agents/*.md` (Claude Code) — simplified example:

```markdown
---
name: code_generator
description: Generates and fixes SV / pyuvm code, commits on ai-task/task branch
tools: Read, Write, Bash
---

{enriched body — OpenCode YAML from the template was stripped}
```

Structure of `.opencode/agents/*.md` mirrors **`*.tmpl.md`**: OpenCode YAML (`description`, `mode`, `model`, nested `tools` flags, etc.) followed by the same enriched narrative body. Example shape:

```markdown
---
description: …
mode: subagent
model: …
temperature: …
tools:
  write: false
  …
---

{base prompt from prompts/code_generator.tmpl.md}

{team prompt_patch from composition.team}

{ip_type protocol_rules from composition.ip_types}

## VCS Rules
- All modifications are performed on the `ai-task/{task_id}` branch
- Commit message format: `[agent] {reason} · task:{task_id}`
- Direct pushes to main/trunk are prohibited
```

## Generated Code VCS Workflow

```
  Agent starts task
      │
      ▼
  git checkout -b ai-task/{task_id}   (or svn branch)
      │
  Agent modifies files under tb/, tests/
  Commits after each fix (including task_id, iteration number)
      │
  Sim Controller runs simulation, Log Analyzer provides feedback
      │
  Loop until pass or budget limit reached
      │
      ▼
  Human review: PR / MR
      │
  Merge → main / trunk
```

Agents do not maintain a separate `generated/` directory. All code is directly on the VCS branch.
Audit trails and rollbacks are entirely handed over to git / svn.

## External Environment Differences (Only project.yaml differs)

```yaml
environment: external
composition:
  team: external_default
  ip_types: [axi]
  simulator: cocotb
  coverage: lcov

memory:
  backend: sqlite     # local, or switch to vector_db to enable semantic search
```

`team_external_default`'s vip_index points to pyuvm base classes,
prompt_patch targets Python syntax and pyuvm class hierarchy,
remaining agent logic is completely unchanged.
