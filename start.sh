#!/usr/bin/env bash
set -Eeuo pipefail

# MVP starter: run from MVP directory, isolate venv inside MVP, exclude venv from reloader
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# If script is at repo root, cd into MVP; if it already lives in MVP/, stay there
if [[ -d "${SCRIPT_DIR}/MVP" ]]; then
  cd "${SCRIPT_DIR}/MVP"
else
  cd "${SCRIPT_DIR}"
fi

log() { printf "[%s] %s\n" "$(date +'%H:%M:%S')" "$*"; }
die() { printf "ERROR: %s\n" "$*" 1>&2; exit 1; }

# Load env without echoing secrets.
# NOTE: We intentionally DO NOT source ../backend/.env because it may contain non-shell-safe values (e.g., CSV lists with spaces).
try_source_env() {
  local f="$1"
  if [[ -f "$f" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$f"
    set +a
    log "Loaded env from $f"
  fi
}
try_source_env ".env"
try_source_env "../.env"

# OpenRouter defaults (do not hardcode secrets)
: "${LLM_PROVIDER_BASE_URL:=https://openrouter.ai/api/v1}"
: "${OPENROUTER_MODEL:=openrouter/sonoma-sky-alpha}"

if [[ -z "${LLM_PROVIDER_API_KEY:-}" ]]; then
  die "LLM_PROVIDER_API_KEY is not set. Export it or add to MVP/.env (LLM_PROVIDER_API_KEY=...)"
fi

# Python and venv setup (inside MVP)
PYTHON="${PYTHON:-python3}"
"$PYTHON" -V >/dev/null 2>&1 || die "python3 not found in PATH"

VENV_DIR="${VENV_DIR:-.venv}"
if [[ ! -d "$VENV_DIR" ]]; then
  log "Creating virtual environment at $(pwd)/$VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip wheel >/dev/null

# Dependencies (prefer MVP/requirements.txt; fallback to backend)
if [[ -f "requirements.txt" ]]; then
  REQ_FILE="requirements.txt"
elif [[ -f "../backend/requirements.txt" ]]; then
  REQ_FILE="../backend/requirements.txt"
else
  REQ_FILE=""
fi

if [[ -n "${REQ_FILE}" ]]; then
  log "Installing dependencies from ${REQ_FILE}"
  pip install -r "${REQ_FILE}"
else
  log "No requirements.txt found; skipping dependency installation"
fi

# Host/Port defaults (honor existing env)
: "${HOST:=${GODELOS_HOST:-127.0.0.1}}"
: "${PORT:=${GODELOS_PORT:-8000}}"

export LLM_PROVIDER_API_KEY LLM_PROVIDER_BASE_URL OPENROUTER_MODEL
export GODELOS_HOST="$HOST" GODELOS_PORT="$PORT"

# Uvicorn args: run app:app from MVP dir; exclude venv/node_modules from reload watcher
APP_MODULE="app:app"
RELOAD_ARGS=(--reload --reload-exclude "$VENV_DIR" --reload-exclude ".venv*" --reload-exclude "node_modules")
if [[ "${NO_RELOAD:-0}" == "1" ]]; then
  RELOAD_ARGS=()
fi

log "Starting MVP backend at http://${HOST}:${PORT} (model=${OPENROUTER_MODEL}) in $(pwd)"
exec uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT" "${RELOAD_ARGS[@]}"
