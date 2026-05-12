#!/bin/bash
# scripts/offline-download.sh
# Run this on an internet-connected machine to fetch all necessary dependencies.
set -e

echo "================================================================="
echo "🤖 dv-agentic-system: Offline Dependency Downloader"
echo "================================================================="

WHEELS_DIR="dv_wheels"
TAR_FILE="dv-agentic-system.tar.gz"

# Parse optional arguments
WITH_DEV=false
WITH_COCOTB=false

for arg in "$@"; do
    case $arg in
        --with-dev)
            WITH_DEV=true
            ;;
        --with-cocotb)
            WITH_COCOTB=true
            ;;
    esac
done

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

# Check if uv is installed to optimize downloading
if command -v uv >/dev/null 2>&1; then
    echo "⚡ Detected 'uv' packaging tool! Using 'uv pip compile' for optimized, lean dependency resolution..."

    COMPILE_FLAGS=""
    if [ "$WITH_COCOTB" = true ]; then
        COMPILE_FLAGS="$COMPILE_FLAGS --extra cocotb"
    fi
    if [ "$WITH_DEV" = true ]; then
        COMPILE_FLAGS="$COMPILE_FLAGS --all-groups"
    fi

    TEMP_REQ="temp-requirements.txt"
    echo "Generating locked dependency tree into $TEMP_REQ..."
    uv pip compile pyproject.toml $COMPILE_FLAGS -o "$TEMP_REQ"

    echo "Downloading locked dependencies..."
    $PIP_CMD download \
        --only-binary=:all: \
        -d "$WHEELS_DIR" \
        -r "$TEMP_REQ"

    # Always download hatchling, pip, setuptools, and wheel for packaging/install needs
    $PIP_CMD download \
        --only-binary=:all: \
        -d "$WHEELS_DIR" \
        hatchling \
        pip \
        setuptools \
        wheel

    rm -f "$TEMP_REQ"
else
    echo "ℹ️ 'uv' not found. Falling back to standard pip download..."

    # Download build backend, core dependencies, and packaging tools
    echo "1. Downloading core dependencies and packaging tools..."
    $PIP_CMD download \
        --only-binary=:all: \
        -d "$WHEELS_DIR" \
        pydantic \
        pyyaml \
        hatchling \
        pip \
        setuptools \
        wheel

    # Download open-source verification dependencies only if explicitly requested
    if [ "$WITH_COCOTB" = true ]; then
        echo "1b. Downloading open-source cocotb & pyuvm dependencies..."
        $PIP_CMD download \
            --only-binary=:all: \
            -d "$WHEELS_DIR" \
            cocotb \
            pyuvm
    fi

    # Download documentation and static analysis dependencies only if explicitly requested
    if [ "$WITH_DEV" = true ]; then
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
    fi
fi

# Bundle source code and downloaded wheels together under a parent folder to avoid tarbombs
echo "3. Creating offline bundle archive ($TAR_FILE)..."
if command -v tar >/dev/null 2>&1; then
    # Create temporary directory layout to ensure all files extract into a parent folder
    TEMP_BUNDLE_DIR="dv-agentic-system"
    mkdir -p "$TEMP_BUNDLE_DIR"

    # Copy files/folders to the temporary directory
    cp -r "$WHEELS_DIR" "$TEMP_BUNDLE_DIR/"
    cp pyproject.toml "$TEMP_BUNDLE_DIR/"
    cp README.md "$TEMP_BUNDLE_DIR/"
    if [ -f "LICENSE" ]; then
        cp LICENSE "$TEMP_BUNDLE_DIR/"
    fi
    cp -r src "$TEMP_BUNDLE_DIR/"
    cp -r scripts "$TEMP_BUNDLE_DIR/"

    # Clean up any potential local virtualenvs or caches in the copied folders
    find "$TEMP_BUNDLE_DIR" -type d -name ".venv" -exec rm -rf {} + 2>/dev/null || true
    find "$TEMP_BUNDLE_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

    tar -czf "$TAR_FILE" "$TEMP_BUNDLE_DIR"
    rm -rf "$TEMP_BUNDLE_DIR"

    echo "✅ Success! Pinned tarball created at: $TAR_FILE"
else
    echo "❌ Error: 'tar' utility not found. Please compress the files manually."
    exit 1
fi

echo "================================================================="
echo "🎉 Done! Copy the archive to your secure, air-gapped machine."
echo "================================================================="
