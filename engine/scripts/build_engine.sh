#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build_engine.sh — Build the QuantNexus C++ execution engine.
#
# Usage:
#   ./scripts/build_engine.sh          # Release build
#   ./scripts/build_engine.sh debug    # Debug build (AddressSanitizer enabled)
#   ./scripts/build_engine.sh test     # Build + run C++ unit tests
#
# Prerequisites (install once):
#   macOS:  brew install cmake pybind11 googletest
#   Ubuntu: sudo apt install cmake pybind11-dev libgtest-dev python3-dev
#
# After a successful build the Python extension is at:
#   engine/build/quantnexus_engine*.so
#
# Add the build directory to your PYTHONPATH so `import quantnexus_engine`
# works without installing:
#   export ENGINE_BUILD_DIR="$(pwd)/engine/build"
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE_DIR="${REPO_ROOT}/engine"
BUILD_TYPE="${1:-Release}"

echo "▶ Building QuantNexus C++ engine (${BUILD_TYPE})..."
echo "  Engine dir:  ${ENGINE_DIR}"

cmake -S "${ENGINE_DIR}" \
      -B "${ENGINE_DIR}/build" \
      -DCMAKE_BUILD_TYPE="${BUILD_TYPE}" \
      -DBUILD_TESTS=ON

cmake --build "${ENGINE_DIR}/build" --parallel "$(nproc 2>/dev/null || sysctl -n hw.logicalcpu)"

if [[ "${1:-}" == "test" ]]; then
    echo "▶ Running C++ unit tests..."
    cd "${ENGINE_DIR}/build"
    ctest --output-on-failure
fi

echo "✅ Build complete. Extension: ${ENGINE_DIR}/build/quantnexus_engine*.so"
echo ""
echo "   To use from Python:"
echo "   export ENGINE_BUILD_DIR='${ENGINE_DIR}/build'"
echo "   python -c 'import quantnexus_engine; print(quantnexus_engine.__doc__)'"
