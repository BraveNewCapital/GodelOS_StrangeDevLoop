#!/usr/bin/env bash
# bootstrap_repo_architect_slices.sh
# Bootstrap convenience script for local development.
# Copies the tracked workflow and runner script to their canonical repo paths
# and ensures the runner is executable.
#
# This script is the single source of truth reference — it uses cp from the
# already-tracked files so the bootstrap can never drift from the committed
# versions.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$REPO_ROOT/scripts"
WORKFLOW_DIR="$REPO_ROOT/.github/workflows"

echo "Repository root: $REPO_ROOT"

# ---------------------------------------------------------------------------
# 1. Ensure .github/workflows/repo-architect.yml is present
# ---------------------------------------------------------------------------
WORKFLOW_SRC="$WORKFLOW_DIR/repo-architect.yml"
if [ ! -f "$WORKFLOW_SRC" ]; then
  echo "ERROR: $WORKFLOW_SRC not found. Has it been committed to the repo?" >&2
  exit 1
fi
echo "Workflow file present: $WORKFLOW_SRC"

# ---------------------------------------------------------------------------
# 2. Ensure scripts/run_repo_architect_slices.sh is present and executable
# ---------------------------------------------------------------------------
RUNNER_SRC="$SCRIPTS_DIR/run_repo_architect_slices.sh"
if [ ! -f "$RUNNER_SRC" ]; then
  echo "ERROR: $RUNNER_SRC not found. Has it been committed to the repo?" >&2
  exit 1
fi
chmod +x "$RUNNER_SRC"
echo "Runner script present and executable: $RUNNER_SRC"

echo ""
echo "Bootstrap complete. Both files are sourced from their committed versions."
echo "  Workflow:      $WORKFLOW_SRC"
echo "  Runner script: $RUNNER_SRC"
echo ""
echo "To run the full slice sequence:"
echo "  $RUNNER_SRC"
