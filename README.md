# 🤖 DV Agentic System

[![CI Status](https://github.com/anlit75/dv-agentic-system/actions/workflows/ci.yml/badge.svg?style=flat-square)](https://github.com/anlit75/dv-agentic-system/actions/workflows/ci.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/anlit75/dv-agentic-system)
[![Release](https://img.shields.io/github/v/release/anlit75/dv-agentic-system?style=flat-square)](https://github.com/anlit75/dv-agentic-system/releases)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

## ⚡ Why this exists

Hardware verification produces huge logs, deep coverage questions, and repeated reasoning across sessions. Raw LLM access is not enough: you need **structured prompts**, **team and IP context**, and **guardrails** that match how DV teams actually work.

This repository is the **shared Python package** that provides that scaffolding: agent orchestration, prompt loading, configuration wiring, and integration points for simulators and coverage tools. Organization-specific rules and VIP catalogs live **outside** this repo (see Architecture).

## 🎯 What you get here

- A **multi-agent** workflow oriented to **UVM** verification (orchestrator plus specialized agents).
- A **three-layer** split between generic code (this repo), org profiles, and per-project `.agent/` configuration.
- **Documentation** for architecture, prompts, APIs, and CLI — see the [documentation home](https://anlit75.github.io/dv-agentic-system/).

**Design constraint (policy):** agents follow a **testbench-only** stance toward RTL: they do not treat RTL sources as a writable surface; hardware intent is driven by your verification artifacts (e.g. specification inputs and plans you configure), not by editing DUT RTL through this framework.

For **current capabilities, agent list, and roadmap**, use the docs and changelog rather than this file:

- [Documentation home](https://anlit75.github.io/dv-agentic-system/)
- [Agents](https://anlit75.github.io/dv-agentic-system/api/agents/)
- [CLI](https://anlit75.github.io/dv-agentic-system/api/cli/)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│  Layer 1 · Shared package (this repository)         │
│  Agent logic, adapters, base prompts — no org IP    │
├─────────────────────────────────────────────────────┤
│  Layer 2 · Team profile repository (yours, private) │
│  Protocol rules, VIP index, prompt patches          │
├─────────────────────────────────────────────────────┤
│  Layer 3 · Project implant ({project}/.agent/)      │
│  project.yaml connects Layer 1 and Layer 2          │
└─────────────────────────────────────────────────────┘
```

Details: [Structure & design](https://anlit75.github.io/dv-agentic-system/agentic-system-structure/), [System overview](https://anlit75.github.io/dv-agentic-system/agentic-system/).

## 🧠 LLM Wiki (optional knowledge layer)

Some workflows persist verification notes and summaries in a **Git-versioned Markdown wiki** under the project’s `.agent/` tree so context can carry across sessions. \
The **pattern** (persistent markdown between you and raw sources, maintained by an agent rather than re-derived on every question like chunk-RAG alone) follows the public **“LLM Wiki”** idea file by [**Andrej Karpathy** (GitHub Gist, April 2026)](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). \
This repository’s layout, tooling, and agent hooks are **our** instantiation; use the gist for the original motivation and the docs below for what is implemented here.

- [LLM Wiki](https://anlit75.github.io/dv-agentic-system/llm-wiki/) — architecture and usage

## 📦 Requirements

- **Python**: see `requires-python` in [`pyproject.toml`](pyproject.toml) (source of truth).
- **Package manager**: this repo is set up for [`uv`](https://github.com/astral-sh/uv).

## 🚀 Quick start (contributors & local development)

```bash
git clone https://github.com/anlit75/dv-agentic-system.git
cd dv-agentic-system
uv sync
```

Optional: activate the virtual environment (`source .venv/bin/activate` on Unix, `.venv\Scripts\activate` on Windows).

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

### ✨ Option — setup via an AI assistant (copy-paste prompt)

Use the block below as a single message to your AI assistant.

<details>
<summary><strong>📋 Copy prompt for Cursor / Claude Code / Copilot Chat (etc.)</strong></summary>

```
You are helping me set up the local dev environment for the dv-agentic-system repo (Python, uv).

Goals:
1) Install dependencies: run `uv sync` from the repo root.
2) (Optional) Install git hooks: `uv run pre-commit install`, then `uv run pre-commit run --all-files`.
3) Agent installer: run `uv run python -m dv_agentic.cli.install_agents --help`, then run the installer with the `--target` value that matches my tools (choices are printed by --help). If `./scripts/install-agents.sh` exists, you may use it instead after reading `./scripts/install-agents.sh --help`.
4) Report any failures with the exact command and stderr.

Constraints:
- Do not invent CLI flags; only use what --help lists.
- On Windows, if symlink creation fails for mirrored assets, note Developer Mode / admin requirements and continue if the installer falls back to copies.

When done, summarize what ran and what I should run next manually if anything needs human approval.
```

</details>

### 🤖 Install agent prompt bundles into a project

The installer writes agent markdown and mirrored assets into paths expected by supported AI coding tools. **Which paths are populated** depends on the flags you pass; do not assume defaults without reading help output once:

```bash
uv run python -m dv_agentic.cli.install_agents --help
```

On Unix you can also use `./scripts/install-agents.sh --help` if present.

### 📚 Documentation site (local)

```bash
uv sync --all-groups
uv run mkdocs serve
```

### 🔒 Air-gapped install

Use the **[offline install guide](https://anlit75.github.io/dv-agentic-system/air-gapped-install/)**: bundle layout, release assets vs. `offline-download.sh`, and `offline-install.sh` behavior.

## 🔬 Research note

Design choices are informed by public benchmarks in the verification / LLM literature. One widely cited dataset is CVDP (Pinckney et al., 2025) — [arXiv:2506.14074](https://arxiv.org/abs/2506.14074v1).

## 📄 License

[MIT](LICENSE).
