## Architecture Design Analysis: UVM/pyuvm Agentic System

## 1. Core Architectural Principles

Key design constraint: **Agent logic must be shared across both environments, but tool execution must be separated**. This dictates a layered architecture of "portable agent core + environment adapter layer".

```
┌─────────────────────────────────────────────────────────┐
│                    AGENT CORE LAYER                     │
│      (Logic, prompts, and orchestration shared)         │
├─────────────────────────────────────────────────────────┤
│                  TOOL INTERFACE LAYER                   │
│      (Abstract interface, unified agent call style)     │
├────────────────────┬────────────────────────────────────┤
│  INTERNAL ADAPTER  │        EXTERNAL ADAPTER            │
│  VCS/Questa CLI    │    cocotb/pyuvm runner             │
│  Internal VIP API  │    OSS simulators                  │
│  OpenCode tools    │    GitHub / open network           │
│  Intranet file sys │    Cloud storage / APIs            │
└────────────────────┴────────────────────────────────────┘
```

This layering ensures your agent prompts, orchestration logic, and memory schema are identical; only the underlying tool implementations differ.

## 2. Multi-Agent Responsibility Breakdown

Based on cognitive tasks analyzed from three workflows, they are split into 8 agents:

```
┌─────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR AGENT                          │
│  • Receives tasks, determines which workflow to start           │
│  • Manages handoffs and budgets (max run count) between agents  │
│  • Determines when Human-in-the-loop is needed                  │
│  • Maintains cross-session task states                          │
└────────────────────────┬────────────────────────────────────────┘
                         │ Dispatches by workflow
         ┌───────────────┼───────────────────┐
         ▼               ▼                   ▼
    [Workflow 1]    [Workflow 2]         [Workflow 3]
```

### Agent Overview

| Agent | Responsibility | Input | Output |
|---|---|---|---|
| **Orchestrator** | Task routing, budget control, handoff | Task description | Subtask instructions |
| **SPEC Analyst** | Parse spec, generate vplan | PDF/Text spec | structured vplan |
| **Code Generator** | Write SV/pyuvm code | vplan + constraints | code diff |
| **Sim Controller** | Call simulator, manage jobs | compile/run cmds | job status + paths |
| **Log Analyzer** | Parse log, find failure point | log file | failure summary |
| **Wave Analyzer** | Interpret waveform patterns | Signal list + time | signal analysis |
| **Coverage Analyst** | Analyze coverage DB, find holes | ucdb/coverage report | hole list + priority |
| **Bug Classifier** | Differentiate TB bug vs RTL bug | spec + log + code | classification + evidence |
| **Reporter** | Output bug report / summary | analysis results | structured report |

## 3. Three Workflow Agent Collaboration Diagrams

### Workflow 1: SPEC → Code → Simulate → Fix

```
USER: "Develop verification for XXX feature based on this spec"
         │
         ▼
  [Orchestrator]
         │
         ▼
  [SPEC Analyst] ──── tools: parse_pdf(), extract_feature_list(),
         │                   identify_corner_cases()
         │ vplan (structured)
         ▼
  [Code Generator] ── tools: get_vip_api(), get_base_class(),
         │                   generate_sequence(), validate_sv_syntax()
         │ SV code
         ▼
  [Sim Controller] ── tools: compile_check(), run_simulation()
         │
    ┌────┴────┐
  PASS      FAIL
    │          │
    ▼          ▼
[Coverage   [Log Analyzer] ── tools: parse_log(), extract_error_context()
 Analyst]        │
(→ WF3)        ▼
           [Bug Classifier]
                 │
         ┌───────┴──────┐
      TB Bug          RTL Bug
         │                │
         ▼                ▼
  [Code Generator]   [Reporter]
   (Auto fix)        (Open RTL bug ticket)
         │
         ▼
  [Sim Controller]  ← loop (max N times)
         │
  ── Budget exceeded ──▶ Human-in-the-loop checkpoint
```

### Workflow 2: Regression Fail → Debug → Classify → Fix

```
USER: "Regression has 5 fails, please analyze"
         │
         ▼
  [Orchestrator]
  Batch process first, sort by severity
         │
         ▼ (For each fail case)
  [Log Analyzer]
  ├── Quick analysis: Can the cause be determined from existing logs?
  │     YES → Go straight to [Bug Classifier]
  │     NO  ↓
  │
  ▼ Trigger debug decision
  [Orchestrator] Determines:
  ├── Is this fail worth spending time to run in debug mode?
  │   (Based on: fail severity, past patterns, budget)
  │
  ├── YES → [Sim Controller]
  │           run_simulation(debug_mode=True, full_log=True)
  │                 │
  │           [Wave Analyzer] + [Log Analyzer]
  │
  └── NO  → [Bug Classifier] Make best guess using existing info
                               Mark confidence level
         │
         ▼
  [Bug Classifier]
  ├── tools: cross_ref_spec(), check_protocol_state_machine()
  ├── Output: {type: TB|RTL, evidence: [...], confidence: 0-1}
  │
  ├── confidence < 0.7 → Human-in-the-loop
  │
  └── TB Bug → [Code Generator] Fix
               [Sim Controller] Rerun verification
               loop (max N times)
```

### Workflow 3: Coverage Analysis → Fill Patterns

```
USER: "Coverage is only 73%, find what needs to be filled"
         │
         ▼
  [Coverage Analyst]
  ├── tools: parse_ucdb(), query_vplan(),
  │          classify_holes_by_priority()
  │
  ├── Output: hole list, sorted by priority
  │         {bin_name, hit:0, requires:[State A + State B + timing]}
  │
  ▼
  [Orchestrator] Decision:
  ├── Which holes are worth filling? (Exclude impossible bins caused by design limits)
  ├── Estimate effort vs coverage gain
  │
  ▼ (For each worth-filling hole)
  [Code Generator]
  ├── Generate targeted sequence based on hole's protocol dependency
  ├── tools: generate_targeted_sequence(), constrain_by_protocol_rules()
  │
  ▼
  [Sim Controller] compile + run
         │
  [Log Analyzer] + [Coverage Analyst]
  ├── Did this pattern hit the target bin?
  ├── Were any new fails introduced?
  │
  ├── Success → Continue to next hole
  └── Failure → loop fix or mark "requires human intervention"
         │
  All completed → [Reporter] Output coverage delta report
```

## 4. Shared Tool Interface Design

This is the key to allowing agents to be shared across both environments. Each tool defines a unified interface, while the underlying implementation is handled by adapters:

```python
# Unified interface (agents only see this layer)
class SimulatorTool:
    def compile(self, file_list: list, top: str) -> CompileResult
    def run(self, test: str, seed: int, debug: bool) -> SimResult
    def get_log(self, job_id: str) -> str
    def get_coverage(self, job_id: str) -> CoverageDB

# Company Adapter (Internal VCS)
class VCSAdapter(SimulatorTool):
    def compile(self, ...):
        # Call vcs -sverilog ... internal scripts

# External Adapter (cocotb/pyuvm)
class CocotbAdapter(SimulatorTool):
    def compile(self, ...):
        # Call make SIM=icarus / verilator
```

**All tools must unify their return formats** so agents can work cross-environment:

```python
@dataclass
class SimResult:
    status: Literal["pass", "fail", "compile_error", "timeout"]
    job_id: str
    log_path: str
    coverage_db_path: Optional[str]
    error_summary: Optional[str]   # Pre-extracted to prevent agents from reading full logs
    wall_time_sec: int
```

## 5. Memory and State Design

Agents need to remember several categories of information across sessions:

```
Memory Schema
├── Project Context (Long-term)
│   ├── vplan (feature → bins mapping)
│   ├── VIP API index (class → methods → constraints)
│   ├── known RTL bugs (already reported, avoid duplicate analysis)
│   └── protocol state machine summary
│
├── Session State (Mid-term)
│   ├── Current task goal and budget usage
│   ├── simulation job history (avoid rerunning same seed)
│   └── coverage baseline (snapshot at start, calculate delta)
│
└── Iteration Context (Short-term)
    ├── Current code diff
    ├── Error patterns of the last N fails
    └── Current debug hypothesis
```

Internal: Stored in local file system / SQLite
External: Can use vector DB (knowledge base) + cloud storage

## 6. Human-in-the-Loop Trigger Points

Not everything is automatically completed by agents. Force pause at these points:

```
1. Bug Classifier confidence < 0.7
   → "I judged this as an RTL bug, but am 70% uncertain. Please confirm."

2. Code Generator fixed 3 times but still fails
   → "Auto-fix loop reached limit. Attached debug context, please intervene manually."

3. Coverage hole analysis indicates a possible impossible bin
   → "This bin may be a design limitation. Please confirm if it should be removed from the vplan."

4. Before submitting an RTL bug report
   → Provide evidence for engineer review to prevent false alarms.

5. Before migration / large-scale code modifications
   → Show diff, execute only after confirmation.
```

## 7. Key Differences Between Two Environments

| Aspect | Internal | External |
|---|---|---|
| LLM Access | OpenCode (Local/Internal) | External APIs (Claude/GPT) |
| SPEC Retrieval | Internal file system | PDF upload / URL |
| Simulator | VCS / Questa (CLI) | Icarus / Verilator / GHDL |
| Coverage DB | UCDB (Questa) / VDB (VCS) | cocotb coverage XML / LCOV |
| VIP | Commercial VIP (Private API) | pyuvm base classes (Open source) |
| Agent memory | Local file / SQLite | Vector DB + cloud |
| Debug artifacts | Internal waveform viewer | Local GTKWave / Cloud |
