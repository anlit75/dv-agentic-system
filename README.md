# 🤖 DV Agentic System

[![CI Status](https://github.com/anlit75/dv-agentic-system/actions/workflows/ci.yml/badge.svg?style=flat-square)](https://github.com/anlit75/dv-agentic-system/actions/workflows/ci.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/anlit75/dv-agentic-system)
![Version](https://img.shields.io/badge/version-v0.5.1-blue?style=flat-square)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

## ⚡ The DV Engineer's Productivity Problem

You're debugging a test failure at 2 AM. The simulator log is 80,000 lines long. The coverage hole is buried three layers deep in a scoreboard you didn't write. And your release tape-out deadline doesn't move.

**This is not a tooling problem. It's a cognitive load problem.**

State-of-the-art LLMs can reason about SystemVerilog. But raw API access doesn't solve anything — you need an agent that understands your IP protocol rules, your team's VIP catalog, your simulator's error taxonomy, and knows the difference between a DUT bug and a testbench bug. Building that from scratch for every project is exactly the kind of tedious work that kills verification velocity.

`dv-agentic-system` is the foundation that handles that scaffolding so you don't have to.

## 🎯 What It Does

`dv-agentic-system` is a **multi-agent AI framework purpose-built for UVM / pyuvm verification**. It automates the highest-friction tasks in the verification workflow:

| Task | What the Agent Does |
|------|---------------------|
| **SPEC Analysis** | Parses specification documents → generates `vplan.yaml` with coverage intent |
| **Environment Setup** | Injects your team's protocol rules and VIP API references into every prompt |
| **Code Generation** | Writes / modifies sequences, scoreboards, coverage groups, and monitors |
| **Simulation Control** | Compiles, runs, and branches — with timeout and retry logic |
| **Log Debugging** | Classifies 80K-line simulator logs into actionable error categories |
| **Coverage Analysis** | Reads IMC / pyuvm coverage DBs and proposes targeted test scenarios |
| **Bug Classification** | Distinguishes DUT bugs from TB bugs before escalating to the engineer |

All agents operate under a strict **TB-only** policy — RTL source files are completely off-limits for reading or writing. The sole sources of hardware architectural truth are the SPEC and `vplan.yaml`.

## 🏗️ Architecture: Three Layers, Zero Secrets

The system is designed around a hard separation between generic intelligence and organization-specific knowledge:

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1 · Shared Package  (this repo)                  │
│  Agent logic, Simulator/Coverage Adapters, Base Prompts │
│  Contains NO company IP, NO proprietary protocol rules  │
├─────────────────────────────────────────────────────────┤
│  Layer 2 · Team Profile Repo  ({org}-dv-profiles)       │
│  AXI / PCIe / custom protocol rules, VIP API index,     │
│  Prompt Patches — lives in your private org repo        │
├─────────────────────────────────────────────────────────┤
│  Layer 3 · Project Implant  ({project}/.agent/)         │
│  project.yaml wires Layers 1 + 2 to a specific project  │
│  Attaches to existing UVM / pyuvm projects in-place     │
└─────────────────────────────────────────────────────────┘
```

This **Environment-Agnostic** design means:
- The shared package can be open-sourced with zero IP risk
- Each DV team customizes behavior through their private profile repo
- Adding a new project requires only a `project.yaml` — no core changes

For the full architecture specification, see [`docs/agentic-system-structure.md`](docs/agentic-system-structure.md) and [`docs/agentic-system.md`](docs/agentic-system.md).

## 🛠️ Toolchain Support

Seamless switching between enterprise commercial tools and open-source CI tools:

| Environment | Simulator | Coverage | OS |
|-------------|-----------|----------|----|
| **Internal** | Cadence Xcelium 25.03 | Cadence IMC 24.06 + Verisium 25.12 | RHEL 8.4 |
| **External** | GHDL (LLVM) + cocotb | pyuvm functional coverage | Cross-platform |
| **Lightweight CI** | Icarus Verilog / Verilator | lcov line coverage | Cross-platform |

One codebase. Three environments. The same agent logic runs in all of them.

## 🔬 Research-Guided Optimization

The optimizations are grounded in empirical findings from:

> Pinckney, N., Deng, C., Ho, C. T., Tsai, Y. D., Liu, M., Zhou, W., ... & Ren, H. (2025). Comprehensive Verilog design problems: A next-generation benchmark dataset for evaluating large language models and agents on RTL design and verification. *arXiv preprint* [arXiv:2506.14074](https://arxiv.org/abs/2506.14074v1).

The CVDP benchmark reveals that even frontier models (Claude 3.7, GPT-4.1) achieve only **22.77% pass rates on Checker Generation** (`cid13`) — the exact task our `CodeGeneratorAgent` handles. The root causes are not reasoning failures; they are mechanical failures: missing `timescale` declarations, unmatched `begin/end` blocks, mixed blocking/non-blocking assignments.

## 🚀 Quick Start

### ✨ Option A — Let Your AI Agent Install It (Recommended)

Open your AI coding tool (Claude Code, Cursor, Copilot Chat, etc.), paste the prompt below, and let it handle the setup end-to-end.

```
Please set up dv-agentic-system in this repository by following these steps:

1. Install dependencies using uv:
   uv sync

2. Activate the virtual environment (source .venv/bin/activate on macOS/Linux, or .venv\Scripts\activate on Windows).

3. Install the pre-commit hooks:
   uv run pre-commit install

4. Generate and install the sub-agent prompt files:
   uv run python -m dv_agentic.cli.install_agents

5. Verify the installation by running the full static analysis:
   uv run pre-commit run --all-files

Report any errors and fix them before proceeding. On Windows, if symlink creation fails, confirm that Developer Mode is enabled in Windows Settings or the terminal is running as Administrator.
```

> [!TIP]\
> If you already have a team profile repo (`{org}-dv-profiles`), also tell the agent the path to your `project.yaml` so it can validate the three-layer configuration at the same time.

---

### 🔧 Option B — Manual Setup

#### 📦 1. Environment Setup

This project uses [`uv`](https://github.com/astral-sh/uv) for reproducible dependency management.

```bash
# Install dependencies
uv sync

# Activate the virtual environment
source .venv/bin/activate
# Windows: .venv\Scripts\activate
```

#### ⚙️ 2. Configure Your Project

The system uses a **three-layer configuration loader** (`project.yaml` → team profile → IP protocol rules) to inject context into every agent prompt.

```
{project}/.agent/project.yaml    ← points to your org's profile repo
{org}-dv-profiles/teams/         ← team parameters, VIP index
{org}-dv-profiles/ip-types/      ← AXI, PCIe, and other protocol rules
```

See [`sample/`](sample/) for complete working examples of all three layers.

#### 🤖 3. Install Sub-agents

Generate prompt files enriched with your org's profile and install them to your AI coding tool's expected path:

```bash
# Generate and install to .claude/agents/ and .cursor/rules/
uv run python -m dv_agentic.cli.install_agents

# macOS/Linux shell wrapper
./scripts/install-agents.sh
```

> [!NOTE]\
> On Windows, symlink creation requires **Administrator Privileges** or **Developer Mode** enabled in Windows Settings. Without either, prompt files are still written to `.agent/subagents/` — only the symlinks are skipped.

#### 🛡️ 4. Static Analysis and Code Quality

```bash
# Install pre-commit hooks (once)
uv run pre-commit install

# Run ruff + mypy across the full project
uv run pre-commit run --all-files
```

## 📍 Roadmap

For per-phase implementation progress, adapter status, and upcoming work, see [`ROADMAP.md`](ROADMAP.md).

## 📄 License

This project is licensed under the terms of the [MIT](LICENSE).
