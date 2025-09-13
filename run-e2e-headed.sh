#!/usr/bin/env bash
set -euo pipefail

# Root convenience script to run headed Chromium E2E tests for the Svelte frontend
# It relies on svelte-frontend/playwright.config.js to start the backend and frontend.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔧 Ensuring Playwright browsers..."
cd "$SCRIPT_DIR/svelte-frontend"
npx playwright install chromium >/dev/null 2>&1 || true

echo "🚀 Starting full stack via start-godelos.sh and running headed tests..."
PLAYWRIGHT_HEADLESS=false npm run test:headed

echo "✅ E2E headed run complete"

