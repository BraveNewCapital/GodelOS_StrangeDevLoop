#!/usr/bin/env bash
set -euo pipefail

# Start the unified backend in the background and return immediately.
# - Kills any existing process bound to the target port
# - Uses the project venv if present
# - Detaches via nohup and redirects logs

PORT="${GODELOS_BACKEND_PORT:-8000}"
HOST="${GODELOS_BACKEND_HOST:-127.0.0.1}"
LOGS_DIR="logs"

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
if [[ -d godelos_venv ]]; then
  # shellcheck disable=SC1091
  source godelos_venv/bin/activate
fi

# Launch detached with nohup so the shell can exit cleanly
nohup python -m uvicorn backend.unified_server:app \
  --host "${HOST}" --port "${PORT}" --log-level warning \
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
