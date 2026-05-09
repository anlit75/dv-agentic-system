# dv-agentic-system

[![CI Status](https://github.com/anlit75/dv-agentic-system/actions/workflows/ci.yml/badge.svg?style=flat-square)](https://github.com/anlit75/dv-agentic-system/actions/workflows/ci.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/anlit75/dv-agentic-system)
![Version](https://img.shields.io/badge/version-v0.2.0-blue?style=flat-square)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

> AI Agentic System for UVM/pyuvm Verification

`dv-agentic-system` is a multi-agent collaboration framework designed specifically for Digital IC Verification. This system aims to automate tedious tasks in the verification workflow, including SPEC analysis, test environment setup, code generation, simulation control, log debugging, and coverage analysis.

## Architecture

This system adopts an "**Environment-Agnostic**" design philosophy and is divided into three independent layers:

1. **Shared Package (`dv-agentic-system`)**
   - Contains the system core, agent logic, Simulator/Coverage Adapters, and Base Prompts.
   - **Completely generic**; it does not contain any company secrets or specific IP knowledge.
2. **Team Profile Repo (`{org}-dv-profiles`)**
   - Responsible for storing configuration for each DV Team, specific IP protocol rules (e.g., AXI, PCIe), VIP API manuals, and custom Prompt Patches.
3. **Verification Project Implant Point (`{project}/.agent`)**
   - Attached to existing UVM/pyuvm projects.
   - Loads specific profiles via `project.yaml` and combines them with a dedicated team of Agents to perform automated development and debugging locally.

For detailed system architecture design, please refer to [`docs/agentic-system-structure.md`](docs/agentic-system-structure.md) and [`docs/agentic-system.md`](docs/agentic-system.md).

## Toolchain Support

This system supports seamless switching between internal enterprise tools and external open-source tools:

| Environment | Simulator | Coverage | OS |
|-------------|-----------|----------|----|
| **Internal** | Cadence Xcelium 25.03 | Cadence IMC 24.06 + Verisium 25.12 | RHEL 8.4 |
| **External** | GHDL (LLVM) + cocotb | pyuvm functional coverage | Cross-platform |

## Quick Start

### 1. Environment Setup
This project strictly uses [`uv`](https://github.com/astral-sh/uv) for package management.

```bash
# Install dependencies (including development tools)
uv sync

# Activate the virtual environment
source .venv/bin/activate
# On Windows, use: .venv\Scripts\activate
```

### 2. Config Loading and Profiles
The system uses a **Three-Layer Configuration Loader** (`project.yaml` -> team profile -> IP protocol rules) to dynamically inject context (Level 1: team parameters and IP protocol rules; Level 2: custom prompt patches and VIP catalog indexes) into the agentic system.

- Local project settings: `.agent/project.yaml`
- Profile Repository contains custom rules under `teams/` and `ip-types/` directories.

### 3. Sub-agent Installation
You can easily generate and install the canonical prompt templates for your sub-agents (enriched with your organizational profile and IP rules) into your project.

```bash
# Generate agent prompts and install symlinks to .claude/agents/ and .cursor/rules/
uv run python -m dv_agentic.cli.install_agents

# Alternatively, on macOS/Linux, run the shell wrapper script:
./scripts/install-agents.sh
```

> [!NOTE]
> On Windows, creating symbolic links requires **Administrator Privileges** or enabling **Developer Mode** in Windows Settings (otherwise a warning will be displayed, but the prompt files will still be successfully written to `.agent/subagents/`).

### 4. Development and Static Analysis
The project uses `ruff` and `mypy` to ensure Python code quality, and automatically intercepts formatting issues before commits via `pre-commit`.

```bash
# Install pre-commit hook (required only once)
uv run pre-commit install

# Manually execute a full project scan
uv run pre-commit run --all-files
```

## Roadmap
For the implementation progress of each phase, supported Adapters, and upcoming core development goals, please refer to [`ROADMAP.md`](ROADMAP.md).
