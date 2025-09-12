#!/usr/bin/env bash
set -euo pipefail

# Start the unified backend in the background and return immediately.
# - Kills any existing process bound to the target port
# - Uses the project venv if present
# - Detaches via nohup and redirects logs

PORT="${GODELOS_BACKEND_PORT:-8000}"
HOST="${GODELOS_BACKEND_HOST:-127.0.0.1}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOGS_DIR="${ROOT_DIR}/logs"
# Option parsing / defaults
WAIT="${WAIT:-1}"   # env WAIT=0 disables readiness probe
for arg in "$@"; do
  case "$arg" in
    --no-wait|-n) WAIT=0 ;;
    --wait)       WAIT=1 ;;
    --help|-h)
      echo "Usage: $0 [--no-wait|--wait]"
      echo "Env vars: GODELOS_BACKEND_PORT, GODELOS_BACKEND_HOST, WAIT(1|0), WAIT_SECS"
      exit 0
      ;;
  esac
done

# Defer the success message until after readiness (so it only prints when up)
# We intercept only the specific success echo later in the script.
if [[ "${WAIT}" != "0" ]]; then
  BACKEND_STARTED_MSG=""
  echo() {
    if [[ "$*" == "✅ Backend started"* ]]; then
      BACKEND_STARTED_MSG="$*"
      return 0
    fi
    command echo "$@"
  }
  # Print the stored success line at script exit (after readiness loop completes)
  trap 'if [[ -n "${BACKEND_STARTED_MSG}" ]]; then command echo "${BACKEND_STARTED_MSG}"; fi' EXIT
fi
mkdir -p "$LOGS_DIR"

# Kill an existing server by PID file if present
if [[ -f .server.pid ]]; then
  if kill -0 "$(cat .server.pid)" 2>/dev/null; then
    echo "Stopping existing backend (PID $(cat .server.pid))..."
    kill "$(cat .server.pid)" 2>/dev/null || true
    sleep 1
  fi
  rm -f .server.pid
fi

# Also kill anything bound to the port (best-effort)
if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -ti tcp:"$PORT" || true)
  if [[ -n "${PIDS}" ]]; then
    echo "Releasing port ${PORT} (PIDs: ${PIDS})..."
    kill ${PIDS} 2>/dev/null || true
    sleep 1
  fi
fi

# Activate venv if present
if [[ -d "${ROOT_DIR}/godelos_venv" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/godelos_venv/bin/activate"
fi

# Ensure repo root is on PYTHONPATH so 'backend' package resolves
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

# Launch detached with nohup; point uvicorn at repo root to resolve package
cd "${ROOT_DIR}" || exit 1
nohup python -m uvicorn backend.unified_server:app \
  --host "${HOST}" --port "${PORT}" --log-level warning --app-dir "${ROOT_DIR}" \
  >"${LOGS_DIR}/backend.bg.log" 2>&1 < /dev/null &

echo $! > .server.pid
echo "✅ Backend started (PID $(cat .server.pid)) on http://${HOST}:${PORT}"

# Optional readiness wait (fast exit if you don't need it):
if [[ "${WAIT:-1}" != "0" ]]; then
  SECS=${WAIT_SECS:-90}
  for _ in $(seq 1 "$SECS"); do
    if command -v curl >/dev/null 2>&1; then
      if curl -sf "http://${HOST}:${PORT}/api/health" >/dev/null; then break; fi
    else
      python - <<PY >/dev/null 2>&1 || true
import sys, urllib.request
try:
    urllib.request.urlopen('http://${HOST}:${PORT}/api/health', timeout=2)
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
      if [[ $? -eq 0 ]]; then break; fi
    fi
    sleep 1
  done
fi

exit 0
