# Prompt System Architecture

## Design Principle

Prompts are the primary artifact.
The agentic system is a context supplier, not a prompt generator.

```
prompts/{agent}.md          ← canonical, version-controlled, standalone-ready
        │
        │   dv-agentic PromptLoader reads this file
        │   and fills {{PLACEHOLDER}} blocks with real context
        │
        ▼
enriched system prompt      ← sent to LLM by the agent runtime
```

A prompt must be useful at all three levels of enrichment:

  Level 0 — Raw file, used directly in any AI tool. No injection.
             Agent asks user for missing context.

  Level 1 — Base file + team profile patch injected.
             Agent knows VIP API, coding rules, simulator.

  Level 2 — Level 1 + project vplan + session state injected.
             Agent operates fully autonomously within budget.

---

## Placeholder Convention

Placeholders use `{{UPPER_SNAKE_CASE}}` and are always in the
**Project Context** section at the bottom of each prompt.

The Project Context section is always separated by a horizontal rule
and a clear comment explaining it is injected content. This makes it
visually obvious in standalone use that the section is absent/empty.

### Placeholder Registry

| Placeholder | Source | Used by |
|---|---|---|
| `{{TEAM_RULES}}` | `profiles/teams/{team}/prompt_patch.md` | code_generator, spec_analyst |
| `{{IP_TYPE_RULES}}` | `profiles/ip-types/{ip}/protocol_rules.yaml` | code_generator, bug_classifier, coverage_analyst |
| `{{VIP_INDEX}}` | `profiles/teams/{team}/vip_index.yaml` | code_generator |
| `{{PROJECT_VPLAN_SUMMARY}}` | `.agent/vplan.yaml` (summarised) | coverage_analyst, spec_analyst |
| `{{KNOWN_ERROR_PATTERNS}}` | wiki `patterns/` (wiki-first) → `profiles/` error DB (fallback) | log_analyzer, bug_classifier |
| `{{KNOWN_RTL_BUGS}}` | wiki `bugs/` (wiki-first) → `.agent/tasks/` (fallback) | log_analyzer, bug_classifier |
| `{{COVERAGE_HOLE_HISTORY}}` | wiki `coverage/` (requires `wiki.enabled: true`) | coverage_analyst |
| `{{WIKI_PATTERN_SUMMARY}}` | wiki `patterns/` statistics (requires `wiki.enabled: true`) | code_generator |
| `{{SESSION_STATE}}` | `.agent/tasks/{task_id}.yaml` current session | all agents |

If a placeholder has no data to inject (e.g. no team profile configured),
the PromptLoader removes the placeholder line entirely rather than leaving
`{{PLACEHOLDER}}` visible. The prompt must still be coherent after removal.

---

## PromptLoader Contract

```python
class PromptLoader:
    """Loads and enriches agent prompt templates.

    Standalone use:
        loader = PromptLoader()
        prompt = loader.load("code_generator")
        # Returns raw prompt with all {{}} removed (Level 0)

    Augmented use:
        loader = PromptLoader(project_config=config, session=session)
        prompt = loader.load("code_generator")
        # Returns fully enriched prompt (Level 1 or 2)
    """

    def load(self, agent_name: str) -> str:
        """Return the final system prompt string for the given agent."""

    def _inject(self, template: str, context: dict[str, str]) -> str:
        """Replace {{KEY}} with context[KEY], remove unmatched placeholders."""
```

No template language beyond `{{KEY}}` substitution. No Jinja2, no
conditional blocks inside the prompt file itself. Complexity lives in the
Python loader, not in the prompt syntax.

---

## prompt_patch.md Format

Team profiles supply a `prompt_patch.md` that is injected as-is into
`{{TEAM_RULES}}`. It must be written in natural language that reads
coherently inside the parent prompt, not as a config file.

```markdown
<!-- profiles/teams/team_io/prompt_patch.md -->
<!-- Injected into {{TEAM_RULES}} — write as natural prose/rules, not YAML -->

## Team IO Coding Rules

Naming: all sequences must follow `io_{feature}_{scenario}_seq` format.

VIP usage: never call `pcie_vip_driver::send_raw()` directly.
Always use the sequence-level API (`pcie_tlp_seq`, `pcie_cfg_seq`).

Simulator: Xcelium 25.03 with IMC 24.06. Coverage DB at `cov_work/`.

Forbidden patterns:
- Hardcoded transaction sizes (use `cfg.max_payload_size`)
- `fork/join` inside sequences (use UVM phasing instead)
```

---

## Subagent .md Files (Claude Code / OpenCode)

Prompts are authored once as templates and materialized by the installer (`install-agents.sh` or `python -m dv_agentic.cli.install_agents`) at **Level 1**: team and IP rules from `project.yaml` composition are injected; session state is omitted.

```
install-agents / install_agents CLI
        │
        ├──► {project}/.claude/agents/{agent}.md
        │       Claude Code YAML (`name`, `description`, `tools`, …) + enriched body
        │
        └──► {project}/.opencode/agents/{agent}.md
                OpenCode YAML (same fields as `*.tmpl.md`) + enriched body
```

Do not hand-edit generated files for long-term changes — update the template under `src/dv_agentic/prompts/` and re-run the installer.

The canonical template files use the `*.tmpl.md` naming convention (for example `code_generator.tmpl.md`). They include **OpenCode-oriented** YAML at the top of the file.

For **Claude Code**, the installer **strips** that OpenCode front matter and prepends a Claude-compatible block (see `dv_agentic.cli.install_agents`).

Example shape for `.claude/agents/*.md`:

```yaml
---
name: code_generator
description: Generate and modify SV/UVM code targeting specific coverage bins or bug fixes
tools: Read, Write, Bash
---
{enriched prompt body}
```

OpenCode outputs under `.opencode/agents/` keep the template’s original YAML keys (`mode`, `model`, `temperature`, nested `tools` permissions, etc.).

---

## File Locations

```
src/dv_agentic/prompts/          ← canonical templates (part of package)
    orchestrator.tmpl.md
    code_generator.tmpl.md
    ...

{project}/tools/               ← TypeScript tool adapters + `_run_agent.sh`; mirrored into `.opencode/tools/` and `.claude/tools/`
{project}/skills/              ← optional; mirrored into both tool ecosystems

{project}/.claude/agents/      ← generated (Claude format)
{project}/.opencode/agents/    ← generated (OpenCode format, matches tmpl front matter)
```
