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
# them to .claude/ and/or .opencode/ directories.
#
# Usage:
#   bash scripts/install-agents.sh [TARGET] [options]
#
# Target selection (default: --opencode):
#   -o, --opencode   Install OpenCode paths only  [default]
#   -c, --claude     Install Claude paths only
#   -a, --all        Install both Claude and OpenCode
#
# With profile injection (recommended):
#   bash scripts/install-agents.sh \
#       --project-config .agent/project.yaml \
#       --profiles-dir ../my-org-dv-profiles
#
# Override the project root (default: directory containing this script's parent):
#   PROJECT_ROOT=/path/to/project bash scripts/install-agents.sh
#
# Remaining flags are forwarded to:
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
# Parse target selection flags
# ---------------------------------------------------------------------------

INSTALL_TARGET="opencode"   # default: opencode only
PASSTHROUGH_ARGS=()

_usage() {
    cat <<EOF
Usage: $(basename "$0") [TARGET] [OPTIONS]

Target selection (default: --opencode):
  -o, --opencode   Install OpenCode paths only  [default]
  -c, --claude     Install Claude paths only
  -a, --all        Install both Claude and OpenCode

Options forwarded to the Python installer:
  --project-root PATH    Root of the verification project (default: auto-detected)
  --project-config PATH  Path to .agent/project.yaml for profile injection
  --profiles-dir PATH    Org profile repository root
  --force                Overwrite existing files in target directories
  -v, --verbose          Show debug-level log messages

Environment:
  PROJECT_ROOT    Override the auto-detected project root

Examples:
  $(basename "$0")                        # install OpenCode only (default)
  $(basename "$0") --claude               # install Claude only
  $(basename "$0") --all --force          # install both, overwriting existing files
  $(basename "$0") -o --project-config .agent/project.yaml
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--opencode)
            INSTALL_TARGET="opencode"
            shift
            ;;
        -c|--claude)
            INSTALL_TARGET="claude"
            shift
            ;;
        -a|--all)
            INSTALL_TARGET="all"
            shift
            ;;
        -h|--help)
            _usage
            exit 0
            ;;
        *)
            PASSTHROUGH_ARGS+=("$1")
            shift
            ;;
    esac
done

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
echo "[install-agents] Command:      $CMD"
echo "[install-agents] Target:       $INSTALL_TARGET"

# Check if dv_agentic is available
if ! $CMD -c "import dv_agentic" &>/dev/null; then
    echo "[install-agents] ERROR: dv_agentic package not found." >&2
    echo "  Please ensure dependencies are installed (e.g., pip install -e . or uv sync)" >&2
    exit 1
fi

# shellcheck disable=SC2086
exec $CMD -m dv_agentic.cli.install_agents \
    --project-root "$PROJECT_ROOT" \
    --target "$INSTALL_TARGET" \
    "${PASSTHROUGH_ARGS[@]}"
