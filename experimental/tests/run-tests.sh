#!/usr/bin/env bash
# Run the lenOS patch test suite.
#   ./run-tests.sh              all tests
#   ./run-tests.sh test_ssaid   one module
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -n "${LENOS_WORKSPACE+x}" && ! -d "$LENOS_WORKSPACE" ]]; then
  echo "error: LENOS_WORKSPACE is not a directory: $LENOS_WORKSPACE" >&2
  exit 1
fi
export LENOS_WORKSPACE="${LENOS_WORKSPACE:-$HOME/lineage}"
if [[ ! -d "$LENOS_WORKSPACE" ]]; then
  echo "warning: no LineageOS tree at $LENOS_WORKSPACE; patch-application tests will be skipped" >&2
fi
PY="${LENOS_PYTHON:-$(command -v python3)}"
cd "$HERE"
if [[ $# -eq 0 ]]; then
  set -- discover -s . -p 'test_*.py'
fi
exec "$PY" -m unittest "$@" -v
