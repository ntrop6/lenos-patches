#!/usr/bin/env bash
# Run the lenOS patch test suite.
#   ./run-tests.sh              all tests
#   ./run-tests.sh test_ssaid   one module
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export LENOS_WORKSPACE="${LENOS_WORKSPACE:-$(cd "$HERE/../.." && pwd)}"
PY="${LENOS_PYTHON:-$(command -v python3)}"
cd "$HERE"
exec "$PY" -m unittest "${@:-discover -s . -p test_*.py}" -v
