#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-}"
if [[ -z "${PROJECT_ROOT}" ]]; then
  echo "usage: scripts/smoke_m5_governance_end_to_end.sh <project_root>"
  exit 2
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "${PROJECT_ROOT}"
${PYTHON_BIN} -m pytest -q tests/integration/test_m5_governance_end_to_end_smoke.py

