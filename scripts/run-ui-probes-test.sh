#!/usr/bin/env bash
set -euo pipefail

# Run the UI health probes Playwright test end-to-end with background backend + frontend preview.
# Requires: nvm (Node >= 18.19.0), npm, playwright (downloaded automatically).

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

# Use Node via nvm if available
if command -v nvm >/dev/null 2>&1; then
  # shellcheck disable=SC1090
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" || true
  nvm use || nvm install
fi

echo "Node: $(node -v 2>/dev/null || echo 'not found')"

# Start backend (detached) and wait for readiness
WAIT_SECS=120 ./scripts/start-backend-bg.sh

pushd svelte-frontend >/dev/null

# Install deps (prefer npm ci if lockfile is present)
if [ -f package-lock.json ]; then
  npm ci --silent
else
  npm install --silent
fi

# Ensure playwright browser is available
npx playwright install chromium --with-deps || npx playwright install chromium || true

# Build and run preview (detached)
npm run -s build
nohup npm run -s preview >/dev/null 2>&1 & echo $! > ../.frontend-preview.pid

# Wait for preview readiness
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:3001 >/dev/null; then break; fi
  sleep 1
done

# Run the probes test headless
npx playwright test tests/health-probes.spec.js --project=chromium --reporter=line

popd >/dev/null

# Cleanup preview and backend
if [ -f .frontend-preview.pid ]; then
  kill $(cat .frontend-preview.pid) 2>/dev/null || true
  rm -f .frontend-preview.pid
fi

./scripts/stop-backend-bg.sh || true

echo "✅ UI probes test completed"

