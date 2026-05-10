#!/bin/bash
# scripts/offline-download.sh
# Run this on an internet-connected machine to fetch all necessary dependencies.
set -e

echo "================================================================="
echo "🤖 dv-agentic-system: Offline Dependency Downloader"
echo "================================================================="

WHEELS_DIR="dv_wheels"
TAR_FILE="dv-agentic-system.tar.gz"

# Dynamically detect available pip tool on the host machine
if [ -f ".venv/Scripts/pip.exe" ]; then
    PIP_CMD=".venv/Scripts/pip.exe"
elif [ -f ".venv/bin/pip" ]; then
    PIP_CMD=".venv/bin/pip"
elif [ -f "venv/Scripts/pip.exe" ]; then
    PIP_CMD="venv/Scripts/pip.exe"
elif [ -f "venv/bin/pip" ]; then
    PIP_CMD="venv/bin/pip"
elif command -v pip3 >/dev/null 2>&1; then
    PIP_CMD="pip3"
elif command -v pip >/dev/null 2>&1; then
    PIP_CMD="pip"
elif command -v python3 >/dev/null 2>&1 && python3 -m pip --version >/dev/null 2>&1; then
    PIP_CMD="python3 -m pip"
elif command -v python >/dev/null 2>&1 && python -m pip --version >/dev/null 2>&1; then
    PIP_CMD="python -m pip"
else
    echo "❌ Error: Neither 'pip', 'pip3', nor 'python -m pip' was found."
    echo "   Please make sure Python and pip are installed and available in your PATH."
    exit 1
fi

echo "Using pip command: $PIP_CMD"

# Create wheels directory
echo "Creating output directory: $WHEELS_DIR..."
mkdir -p "$WHEELS_DIR"

# Download build backend and core dependencies (lightweight enterprise setup)
echo "1. Downloading core dependencies and packaging tools..."
$PIP_CMD download \
    --only-binary=:all: \
    -d "$WHEELS_DIR" \
    pydantic \
    pyyaml \
    hatchling

# Download open-source verification dependencies only if explicitly requested
if [[ "$*" == *"--with-cocotb"* ]]; then
    echo "1b. Downloading open-source cocotb & pyuvm dependencies..."
    $PIP_CMD download \
        --only-binary=:all: \
        -d "$WHEELS_DIR" \
        cocotb \
        pyuvm
fi

# Download documentation and static analysis dependencies
echo "2. Downloading development & doc dependencies..."
$PIP_CMD download \
    -d "$WHEELS_DIR" \
    pytest \
    pytest-cov \
    ruff \
    mypy \
    mkdocs \
    mkdocs-material \
    mkdocstrings \
    mkdocstrings-python

# Bundle source code and downloaded wheels together
echo "3. Creating offline bundle archive ($TAR_FILE)..."
if command -v tar >/dev/null 2>&1; then
    tar --exclude="*.venv*" \
        --exclude="*__pycache__*" \
        --exclude="*.git*" \
        --exclude="*.ruff_cache*" \
        --exclude="*.mypy_cache*" \
        --exclude="*.pytest_cache*" \
        -czf "$TAR_FILE" \
        "$WHEELS_DIR" \
        pyproject.toml \
        README.md \
        ROADMAP.md \
        CHANGELOG.md \
        src/ \
        tests/ \
        scripts/
    echo "✅ Success! Pinned tarball created at: $TAR_FILE"
else
    echo "❌ Error: 'tar' utility not found. Please compress the files manually."
    exit 1
fi

echo "================================================================="
echo "🎉 Done! Copy the archive to your secure, air-gapped machine."
echo "================================================================="
