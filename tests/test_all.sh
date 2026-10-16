#!/usr/bin/env bash
# Run every suite and aggregate. Exit 0 only if all pass.
# Run: bash tests/test_all.sh

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTS_DIR="$REPO_ROOT/tests"

SUITES=(
    "test_structure.sh"
    "test_skill.sh"
    "test_install.sh"
)

PASSED=()
FAILED=()

for suite in "${SUITES[@]}"; do
    path="$TESTS_DIR/$suite"
    if [ ! -f "$path" ]; then
        echo "  FAIL: $suite missing"
        FAILED+=("$suite")
        continue
    fi
    echo ""
    echo "########## $suite ##########"
    if bash "$path"; then PASSED+=("$suite"); else FAILED+=("$suite"); fi
done

echo ""
echo "########## python unit tier ##########"
if python3 -m unittest discover -s "$TESTS_DIR/python" -t "$TESTS_DIR/python"; then
    PASSED+=("python")
else
    FAILED+=("python")
fi

# The live tier reads a real Sentl project through the MCP server; opt in with RUN_LIVE=1.
if [ "${RUN_LIVE:-0}" = "1" ] && [ -d "$TESTS_DIR/live" ]; then
    echo ""
    echo "########## live tier ##########"
    if python3 -m unittest discover -s "$TESTS_DIR/live" -t "$TESTS_DIR/live"; then
        PASSED+=("live")
    else
        FAILED+=("live")
    fi
elif [ "${RUN_LIVE:-0}" = "1" ]; then
    echo ""
    echo "(live tier: RUN_LIVE=1 is set but tests/live/ does not exist)"
else
    echo ""
    echo "(live tier skipped: set RUN_LIVE=1 and SENTL_LIVE_STUDY to a study folder outside the repository)"
fi

echo ""
echo "============================================="
echo "Aggregate: ${#PASSED[@]} suite(s) passed, ${#FAILED[@]} failed"

if [ ${#FAILED[@]} -gt 0 ]; then
    echo "Failed suites:"
    for s in "${FAILED[@]}"; do echo "  - $s"; done
    exit 1
fi
