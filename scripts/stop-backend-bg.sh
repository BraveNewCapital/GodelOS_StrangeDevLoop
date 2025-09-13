#!/usr/bin/env bash
set -euo pipefail

# Stop the background unified backend started via start-backend-bg.sh

PORT="${GODELOS_BACKEND_PORT:-8000}"

if [[ -f .server.pid ]]; then
  PID=$(cat .server.pid)
  if kill -0 "$PID" 2>/dev/null; then
    echo "Stopping backend (PID $PID)..."
    kill "$PID" 2>/dev/null || true
    sleep 1
  fi
  rm -f .server.pid
fi

# Best-effort port cleanup
if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -ti tcp:"$PORT" || true)
  if [[ -n "${PIDS}" ]]; then
    echo "Cleaning up processes bound to port ${PORT}: ${PIDS}"
    kill ${PIDS} 2>/dev/null || true
  fi
fi

echo "✅ Backend stopped"

