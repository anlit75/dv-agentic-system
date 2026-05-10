## Sample Team Coding Rules

The sample team uses Xcelium 25.03 with IMC 24.06 for all verification.
Replace this file with rules specific to your team.

### Naming Conventions

- Sequences: `{feature}_{scenario}_seq` — example: `axi_write_back_pressure_seq`
- Tests: `{feature}_{scenario}_test`
- Covergroups: `{feature}_cov`
- Config objects: `{block}_cfg` — example: `axi_agent_cfg`

### VIP Usage Rules

Always extend `axi_master_seq` or `axi_slave_seq` as the base class.
Never instantiate `axi_vip_driver` directly — use the sequence-level API only.
All VIP configuration must go through `uvm_config_db` in `build_phase`.

### Simulator and Coverage

Simulator: Xcelium 25.03. Coverage DB root: `cov_work/`.
Coverage collected on every run. The adapter adds `-coverage all` automatically.

### Commit and Branch Rules

All agent-generated code lives on `ai-task/{task_id}` branches.
Commit message format: `[agent] {reason} · task:{task_id} · iter:{n}`
Never commit directly to `main`. Always wait for human PR review.

### Forbidden Patterns

- Hardcoded transaction sizes: always use `cfg.max_payload_bytes`.
- `fork/join` inside sequences: use UVM phasing or guarded `fork/join_none`.
- `$display` in production code: use the uvm_info macro with correct verbosity.
- Direct DUT signal forcing from sequences: route through the driver only.
