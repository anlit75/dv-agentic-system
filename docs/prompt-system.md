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
| `{{KNOWN_ERROR_PATTERNS}}` | `profiles/` error DB | log_analyzer |
| `{{KNOWN_RTL_BUGS}}` | `.agent/memory.db` | log_analyzer, bug_classifier |
| `{{SESSION_STATE}}` | `.agent/memory.db` current session | all agents |

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

## Subagent .md Files (Claude Code / Cursor / OpenCode)

The `.agent/subagents/{agent}.md` files used by AI coding tools are
generated from the same base prompt, not separately authored:

```
install-agents.sh runs PromptLoader at Level 1
(team + IP rules injected, session state omitted)
        │
        ▼
.agent/subagents/code_generator.md   ← written to disk
        │
        ├── symlink → .claude/agents/code_generator.md
        └── symlink → .cursor/rules/code_generator.md
```

These files are generated, not edited by hand. The canonical source is
always `src/dv_agentic/prompts/code_generator.md`.

The YAML front matter required by Claude Code / Cursor is prepended
by the installer, not present in the source prompt:

```yaml
---
name: code_generator
description: Generate and modify SV/UVM code targeting specific coverage bins or bug fixes
tools: [read_file, write_file, run_bash]
---
{enriched prompt body}
```

---

## File Locations

```
src/dv_agentic/prompts/          ← canonical source (part of package)
    code_generator.md
    log_analyzer.md
    coverage_analyst.md
    bug_classifier.md
    spec_analyst.md
    sim_controller.md
    wave_analyzer.md
    orchestrator.md
    reporter.md

{project}/.agent/subagents/      ← generated by install-agents.sh (gitignore or commit)
    code_generator.md            ← Level 1 enriched + YAML front matter
    log_analyzer.md
    ...

{project}/.claude/agents/        ← symlinks to .agent/subagents/
{project}/.cursor/rules/         ← symlinks to .agent/subagents/
```
