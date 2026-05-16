#!/usr/bin/env bash

# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

# scripts/install-agents.sh
#
# Standardized Agent/Tool/Skill installer.
#
# Discovers agents/, tools/, and skills/ in the project root and installs
# them to .claude/ and .opencode/ directories.
#
# Usage:
#   bash scripts/install-agents.sh [--force] [options]
#
# With profile injection (recommended):
#   bash scripts/install-agents.sh \
#       --project-config .agent/project.yaml \
#       --profiles-dir ../my-org-dv-profiles
#
# Override the project root (default: directory containing this script's parent):
#   PROJECT_ROOT=/path/to/project bash scripts/install-agents.sh
#
# All flags are forwarded verbatim to:
#   uv run python -m dv_agentic.cli.install_agents
#
# See --help for the full flag list:
#   bash scripts/install-agents.sh --help

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default project_root: one directory above scripts/
PROJECT_ROOT="${PROJECT_ROOT:-$(dirname "$SCRIPT_DIR")}"

# ---------------------------------------------------------------------------
# Tiered Execution Strategy (uv -> venv -> system python)
# ---------------------------------------------------------------------------

# 1. Try uv (Preferred)
CMD=""
if command -v uv &>/dev/null; then
    CMD="uv run python"
elif command -v uv.exe &>/dev/null; then
    CMD="uv.exe run python"
fi

# 2. If no uv, try to find and activate a virtualenv
if [ -z "$CMD" ]; then
    VENV_ACTIVATE=""
    for candidate in \
        "${PROJECT_ROOT}/.venv/bin/activate" \
        "${PROJECT_ROOT}/.venv/Scripts/activate" \
        "${PROJECT_ROOT}/venv/bin/activate" \
        "${PROJECT_ROOT}/venv/Scripts/activate"
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

    # 3. Fallback to system python
    CMD="python3"
    if ! command -v python3 &>/dev/null; then
        CMD="python"
    fi
fi

echo "[install-agents] Project Root: $PROJECT_ROOT"
echo "[install-agents] Command: $CMD"

# Check if dv_agentic is available
if ! $CMD -c "import dv_agentic" &>/dev/null; then
    echo "[install-agents] ERROR: dv_agentic package not found." >&2
    echo "  Please ensure dependencies are installed (e.g., pip install -e . or uv sync)" >&2
    exit 1
fi

# shellcheck disable=SC2086
exec $CMD -m dv_agentic.cli.install_agents \
    --project-root "$PROJECT_ROOT" \
    "$@"
