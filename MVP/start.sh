#!/usr/bin/env bash
set -Eeuo pipefail

# MVP starter: boots FastAPI MVP backend with OpenRouter config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log() { printf "[%s] %s\n" "$(date +'%H:%M:%S')" "$*"; }
die() { printf "ERROR: %s\n" "$*" >&2; exit 1; }

# Load env from common locations if present (do not echo secrets)
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
# Intentionally NOT sourcing ../backend/.env because it may contain non-shell-safe values (e.g., comma-separated URLs)

# Defaults for OpenRouter
: "${LLM_PROVIDER_BASE_URL:=https://openrouter.ai/api/v1}"
: "${OPENROUTER_MODEL:=openrouter/sonoma-sky-alpha}"

if [[ -z "${LLM_PROVIDER_API_KEY:-}" ]]; then
  die "LLM_PROVIDER_API_KEY is not set. Export it or add to .env or backend/.env"
fi

# Python and venv setup
PYTHON="${PYTHON:-python3}"
"$PYTHON" -V >/dev/null 2>&1 || die "python3 not found in PATH"

VENV_DIR="${VENV_DIR:-.venv_mvp}"
if [[ ! -d "$VENV_DIR" ]]; then
  log "Creating virtual environment at $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip wheel >/dev/null

# Dependencies
if [[ -f "MVP/requirements.txt" ]]; then
  REQ_FILE="MVP/requirements.txt"
elif [[ -f "backend/requirements.txt" ]]; then
  REQ_FILE="backend/requirements.txt"
else
  REQ_FILE=""
fi

if [[ -n "${REQ_FILE}" ]]; then
  log "Installing dependencies from ${REQ_FILE}"
  pip install -r "${REQ_FILE}"
else
  log "No requirements.txt found; skipping dependency installation"
fi

# Host/Port defaults
: "${HOST:=127.0.0.1}"
: "${PORT:=8000}"

export LLM_PROVIDER_API_KEY LLM_PROVIDER_BASE_URL OPENROUTER_MODEL
export GODELOS_HOST="${GODELOS_HOST:-$HOST}"
export GODELOS_PORT="${GODELOS_PORT:-$PORT}"

# Run MVP backend
log "Starting MVP backend at http://${HOST}:${PORT} (model=${OPENROUTER_MODEL})"
exec uvicorn app:app --host "$HOST" --port "$PORT" --reload --reload-exclude ".venv*" --reload-exclude "node_modules"