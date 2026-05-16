# Command Line Interface (CLI) Reference 💻

This section documents the subcommands and command-line execution helper modules in `dv-agentic-system`.

---

## Agent Invocation Commands

These CLI handlers map command-line arguments to agent runs.

### Orchestrator Command
::: dv_agentic.cli.orchestrator
    options:
      heading_level: 4

### Code Generator Command
::: dv_agentic.cli.code_generator
    options:
      heading_level: 4

### Sim Controller Command
::: dv_agentic.cli.sim_controller
    options:
      heading_level: 4

### Log Analyzer Command
::: dv_agentic.cli.log_analyzer
    options:
      heading_level: 4

---

## Specialty Commands

### Spec Analyst Command
::: dv_agentic.cli.spec_analyst
    options:
      heading_level: 4

### Bug Classifier Command
::: dv_agentic.cli.bug_classifier
    options:
      heading_level: 4

### Coverage Analyst Command
::: dv_agentic.cli.coverage_analyst
    options:
      heading_level: 4

### Reporter Command
::: dv_agentic.cli.reporter
    options:
      heading_level: 4

### Environment Setup & Installer Command
::: dv_agentic.cli.install_agents
    options:
      heading_level: 4

---

## Wiki Knowledge Base Commands

These commands manage the persistent LLM Wiki knowledge base introduced in v0.7.0.
Wiki integration must be enabled via `wiki.enabled: true` in `.agent/project.yaml`.

### Wiki Ingest Service
Ingest runs inside agents (`LogAnalyzerAgent`, `BugClassifierAgent`, `ReporterAgent`); there is no separate `wiki_ingest` CLI entry point.

::: dv_agentic.wiki.ingest
    options:
      heading_level: 4

### Wiki Lint Command
::: dv_agentic.cli.wiki_lint
    options:
      heading_level: 4

### Wiki Search Index
::: dv_agentic.wiki.search
    options:
      heading_level: 4

### Wiki Build Command
::: dv_agentic.cli.wiki_build
    options:
      heading_level: 4
