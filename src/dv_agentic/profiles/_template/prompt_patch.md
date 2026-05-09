<!-- profiles/_template/prompt_patch.md -->
<!--
  This file is injected verbatim into {{TEAM_RULES}} in agent prompts.
  Write it as natural prose and rules — NOT as YAML or config syntax.
  It must read coherently as a section of an agent system prompt.

  Guidelines
  ----------
  - Use markdown headings (## and ###) to organise sections.
  - Keep it under 800 words; LLMs have limited context budgets.
  - Focus on what makes your team's environment DIFFERENT from defaults.
  - Do NOT duplicate rules already in protocol_rules.yaml (ip_type profile).
  - Forbidden patterns belong here if they are team-wide. Protocol-specific
    forbidden patterns belong in protocol_rules.yaml.

  Sections to include (use only what applies to your team)
  --------------------------------------------------------
  ## Team {name} Coding Rules
  ## Naming Conventions
  ## VIP Usage Rules
  ## Simulator & Tool Notes
  ## Forbidden Patterns
-->

## Team <name> Coding Rules

Replace this file with your team's actual rules. Below are examples
of the kind of content that belongs here.

### Naming Conventions

Sequences must follow the `{feature}_{scenario}_seq` format.
Example: `axi_write_back_pressure_seq`, not `bp_seq` or `axi_bp`.

Tests must follow `{feature}_{scenario}_test`.

### VIP Usage Rules

Never call `<vip_driver>::send_raw()` directly.
Always use the sequence-level API (`<vip>_tlp_seq`, `<vip>_cfg_seq`).

All VIP configuration must go through `uvm_config_db` in the test's
`build_phase`, not in the sequence body.

### Simulator Notes

Simulator: <simulator_name> with coverage DB at `cov_work/`.

Coverage must be collected on every regression run. Pass
`-coverage all -covworkdir cov_work/{test}_{seed}` to xrun.

### Forbidden Patterns

- Hardcoded transaction sizes: always use `cfg.max_payload_size`.
- `fork/join` inside sequences: use UVM phasing instead.
- Direct DUT signal forcing from sequences: route through the driver.
- `$display` in production sequences: use `uvm_info` with correct verbosity.
