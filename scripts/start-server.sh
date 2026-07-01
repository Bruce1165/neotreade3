#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR=""
HOST="127.0.0.1"
PORT="0"
FOREGROUND="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      PROJECT_DIR="${2:-}"
      shift 2
      ;;
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --foreground)
      FOREGROUND="1"
      shift 1
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${PROJECT_DIR}" ]]; then
  echo "--project-dir is required" >&2
  exit 2
fi

PROJECT_DIR="$(cd "${PROJECT_DIR}" && pwd)"

DEFAULT_PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
PYTHON_BIN="${PYTHON_BIN:-${DEFAULT_PYTHON_BIN}}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python interpreter not found or not executable: ${PYTHON_BIN}" >&2
  echo "Use PROJECT_ROOT/.venv/bin/python (Python 3.10.x)." >&2
  exit 2
fi

if [[ "${FOREGROUND}" == "1" ]]; then
  exec "${PYTHON_BIN}" "${PROJECT_DIR}/scripts/brainstorm_server.py" \
    --project-dir "${PROJECT_DIR}" \
    --host "${HOST}" \
    --port "${PORT}"
fi

STATE_ROOT="${PROJECT_DIR}/.superpowers/brainstorm"
mkdir -p "${STATE_ROOT}"

before=""
if ls -1 "${STATE_ROOT}" >/dev/null 2>&1; then
  before="$(ls -1 "${STATE_ROOT}" | sort | tail -n 1 || true)"
fi

nohup "${PYTHON_BIN}" "${PROJECT_DIR}/scripts/brainstorm_server.py" \
  --project-dir "${PROJECT_DIR}" \
  --host "${HOST}" \
  --port "${PORT}" \
  >/dev/null 2>&1 &

session_dir=""
for _ in $(seq 1 50); do
  after="$(ls -1 "${STATE_ROOT}" | sort | tail -n 1 || true)"
  if [[ -n "${after}" && "${after}" != "${before}" ]]; then
    candidate="${STATE_ROOT}/${after}/state/server-info"
    if [[ -f "${candidate}" ]]; then
      session_dir="${STATE_ROOT}/${after}"
      break
    fi
  fi
  sleep 0.1
done

if [[ -z "${session_dir}" ]]; then
  echo "{\"type\":\"server-started\",\"error\":\"server-info not found\"}"
  exit 1
fi

cat "${session_dir}/state/server-info"
