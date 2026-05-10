# Agents API Reference 🧠

This section provides complete technical documentation of the `dv-agentic-system` multi-agent ecosystem. These specialized agents collaborate to perform specification analysis, code generation, simulation execution, log triage, and final coverage analysis.

---

## Base Class & Configuration

All specialized sub-agents inherit from `BaseAgent` and are configured via `AgentConfig`.

::: dv_agentic.agents.base
    options:
      heading_level: 3

---

## Orchestrator Agent

The `OrchestratorAgent` coordinates all task routing, schedules sub-agents, and manages loop safety guardrails.

::: dv_agentic.agents.orchestrator
    options:
      heading_level: 3

---

## Code Generator Agent

The `CodeGeneratorAgent` generates stimulus sequences, testbenches, and checkers utilizing UVM/pyuvm constructs.

::: dv_agentic.agents.code_generator
    options:
      heading_level: 3

---

## Simulation Controller Agent

The `SimControllerAgent` drives simulator execution, configures test variables, and triggers builds.

::: dv_agentic.agents.sim_controller
    options:
      heading_level: 3

---

## Log Analyzer Agent

The `LogAnalyzerAgent` parses simulation logs, identifies failures, and returns structured failure classifications.

::: dv_agentic.agents.log_analyzer
    options:
      heading_level: 3

---

## Other Sub-Agents

Below are additional specialized components:

### Spec Analyst Agent
::: dv_agentic.agents.spec_analyst
    options:
      heading_level: 4

### Bug Classifier Agent
::: dv_agentic.agents.bug_classifier
    options:
      heading_level: 4

### Coverage Analyst Agent
::: dv_agentic.agents.coverage_analyst
    options:
      heading_level: 4

### Reporter Agent
::: dv_agentic.agents.reporter
    options:
      heading_level: 4
