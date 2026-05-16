#!/usr/bin/env bash

# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

# .opencode/tools/_run_agent.sh
#
# Wrapper invoked by all TypeScript tool definitions.
# Activates the project venv (if present) and delegates to the
# appropriate dv_agentic CLI module.
#
# Usage:
#   bash _run_agent.sh <agent_name> [args…]
#
# Example:
#   bash _run_agent.sh log_analyzer --input-file sim.log

set -euo pipefail

AGENT="${1:?agent name required}"
shift

KNOWN_AGENTS="orchestrator spec_analyst code_generator sim_controller log_analyzer wave_analyzer coverage_analyst bug_classifier reporter"

if ! echo "$KNOWN_AGENTS" | grep -qw "$AGENT"; then
    echo "ERROR: Unknown agent: $AGENT" >&2
    exit 1
fi

# ── Activate virtualenv when present ──────────────────────────────────────
PROJECT_ROOT="${PROJECT_ROOT:-.}"
VENV_ACTIVATE=""

for candidate in \
  "${PROJECT_ROOT}/.venv/bin/activate" \
  "${PROJECT_ROOT}/venv/bin/activate" \
  "${HOME}/.venv/dv_agentic/bin/activate"
do
  if [ -f "$candidate" ]; then
    VENV_ACTIVATE="$candidate"
    break
  fi
done

if [ -n "$VENV_ACTIVATE" ]; then
  # shellcheck disable=SC1090
  source "$VENV_ACTIVATE"
fi

# ── Run ───────────────────────────────────────────────────────────────────
exec python3 -m "dv_agentic.cli.${AGENT}" "$@"
