#!/usr/bin/env bash

# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

# scripts/install-agents.sh
#
# Generates enriched .agent/subagents/*.md files and creates symlinks
# for Claude Code (.claude/agents/), Cursor (.cursor/rules/), and OpenCode.
#
# Usage:
#   bash scripts/install-agents.sh [--force] [options]
#
# With profile injection (recommended):
#   bash scripts/install-agents.sh \
#       --project-config .agent/project.yaml \
#       --profiles-dir ../my-org-dv-profiles
#
# Override the worktree root (default: directory containing this script's parent):
#   WORKTREE=/path/to/project bash scripts/install-agents.sh
#
# All flags are forwarded verbatim to:
#   python3 -m dv_agentic.cli.install_agents
#
# See --help for the full flag list:
#   bash scripts/install-agents.sh --help

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default worktree: one directory above scripts/
WORKTREE="${WORKTREE:-$(dirname "$SCRIPT_DIR")}"

# ---------------------------------------------------------------------------
# Activate virtualenv if present
# ---------------------------------------------------------------------------

VENV_ACTIVATE=""
for candidate in \
    "${WORKTREE}/.venv/bin/activate" \
    "${WORKTREE}/.venv/Scripts/activate" \
    "${WORKTREE}/venv/bin/activate" \
    "${WORKTREE}/venv/Scripts/activate" \
    "${HOME}/.venv/dv_agentic/bin/activate" \
    "${HOME}/.venv/dv_agentic/Scripts/activate"
do
    if [ -f "$candidate" ]; then
        VENV_ACTIVATE="$candidate"
        break
    fi
done

if [ -n "$VENV_ACTIVATE" ]; then
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE"
    echo "[install-agents] Using virtualenv: $VENV_ACTIVATE"
fi

# ---------------------------------------------------------------------------
# Check that dv_agentic is importable
# ---------------------------------------------------------------------------

PYTHON="python3"
if ! command -v python3 &>/dev/null; then
    PYTHON="python"
fi

if ! "$PYTHON" -c "import dv_agentic" 2>/dev/null; then
    echo "[install-agents] ERROR: dv_agentic is not importable." >&2
    echo "  Run: pip install -e . (or activate the correct virtualenv)" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Run the installer
# ---------------------------------------------------------------------------

echo "[install-agents] Worktree: $WORKTREE"
exec "$PYTHON" -m dv_agentic.cli.install_agents \
    --worktree "$WORKTREE" \
    "$@"
