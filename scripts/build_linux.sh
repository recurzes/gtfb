#!/usr/bin/env bash
# ========================================================
#   GTFB - Building Linux Standalone Executable (PyInstaller)
# ========================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "========================================================"
echo "  GTFB - Building Linux Standalone Executable"
echo "========================================================"
echo ""

# Locate Python 3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python 3 was not found in your PATH." >&2
    echo "Please install Python 3.11+ using your Linux package manager (e.g. sudo apt install python3 python3-pip)." >&2
    exit 1
fi

echo "Using Python: $(${PYTHON_CMD} --version)"
echo "Running Linux build orchestrator..."
echo ""

${PYTHON_CMD} "${SCRIPT_DIR}/build_linux.py" "$@"

echo ""
echo "[SUCCESS] Build complete! Linux executable is in the dist/ directory."
echo ""
