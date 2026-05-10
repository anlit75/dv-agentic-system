#!/bin/bash
# scripts/offline-install.sh
# Run this on the target air-gapped machine.
set -e

echo "================================================================="
echo "🤖 dv-agentic-system: Air-Gapped Offline Installer"
echo "================================================================="

WHEELS_DIR="dv_wheels"

# Verify wheels directory exists
if [ ! -d "$WHEELS_DIR" ]; then
    echo "❌ Error: Dependency folder '$WHEELS_DIR' not found."
    echo "   Please make sure you have extracted the offline bundle correctly."
    exit 1
fi

# Detect available Python command (prefer python3, fallback to python)
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "❌ Error: Neither python3 nor python was found in your PATH."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Detected Python: $PYTHON_CMD (v$PYTHON_VERSION)"

# 1. Create Python virtual environment
echo "1. Creating Python virtual environment (.venv)..."
$PYTHON_CMD -m venv .venv

# 2. Activate virtual environment (cross-platform fallback)
echo "2. Activating virtual environment..."
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "❌ Error: Virtual environment activation script not found."
    exit 1
fi

# 3. Upgrade pip & packaging tools offline first
echo "3. Upgrading pip and packaging utilities..."
pip install --no-index --find-links="$WHEELS_DIR" --upgrade pip setuptools wheel || true

# 4. Perform offline installation of dv-agentic-system in editable mode
echo "4. Installing dv-agentic-system and dependencies..."
pip install --no-index --find-links="$WHEELS_DIR" -e .

# 5. Compile and install sub-agent prompt templates (use standard python within venv)
echo "5. Compiling and installing sub-agent prompt configurations..."
if python -c 'import dv_agentic' >/dev/null 2>&1; then
    python -m dv_agentic.cli.install_agents
    echo "✅ Sub-agents installed successfully!"
else
    echo "⚠️ Warning: Failed to import dv_agentic package to install sub-agents."
fi

# Determine the correct activation command to output to user
if [ -f ".venv/Scripts/activate" ]; then
    ACTIVATE_CMD="source .venv/Scripts/activate"
else
    ACTIVATE_CMD="source .venv/bin/activate"
fi

echo "================================================================="
echo "🎉 Installation complete!"
echo "================================================================="
echo "To start using the system, activate your environment with:"
echo "   $ACTIVATE_CMD"
echo ""
echo "To verify the CLI installation, run:"
echo "   dv-agentic --help"
echo "================================================================="
