#!/usr/bin/env bash
# run_repo_architect_slices.sh
# Dispatches a sequence of repo-architect workflow slices via GitHub Actions,
# waits for each to complete, downloads artifacts, and validates the results.
#
# Slice sequence
#   1. report              — full current-state architecture report
#   2. parse_errors        — mutate: fix parse/syntax errors
#   3. import_cycles       — mutate: break local import cycles
#   4. entrypoint_consol.  — mutate: consolidate excess entrypoints
#   5. hygiene             — mutate: remove marked debug prints
#   6. campaign            — all lanes sequentially (campaign mode)

set -euo pipefail

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
for cmd in gh jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: required command '$cmd' not found." >&2
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# Repo / branch detection
# ---------------------------------------------------------------------------
REPO="${GITHUB_REPO:-}"
if [ -z "$REPO" ]; then
  REPO="$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null || true)"
fi
if [ -z "$REPO" ]; then
  echo "ERROR: could not detect repository. Set GITHUB_REPO or run inside a git repo with 'gh auth login'." >&2
  exit 1
fi
echo "Repository: $REPO"

WORKFLOW_FILE="repo-architect.yml"
BRANCH="${GITHUB_REF_NAME:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)}"
echo "Branch:     $BRANCH"

# Delay (seconds) after workflow dispatch before polling for the new run ID.
# Configurable to account for high-load GitHub API conditions.
GH_API_DELAY="${GH_API_DELAY:-5}"

# ---------------------------------------------------------------------------
# Optional: merge a baseline PR before dispatching slices.
# Performs an explicit synchronous squash-merge — fails immediately on error
# and polls until the PR reports MERGED before continuing.
# ---------------------------------------------------------------------------
if [ -n "${MERGE_BASELINE_PR:-}" ]; then
  echo "Merging baseline PR #$MERGE_BASELINE_PR …"
  gh pr merge "$MERGE_BASELINE_PR" --repo "$REPO" --squash

  # Poll until the PR reaches MERGED state so subsequent slices always run
  # against a clean, merged baseline and not against a merge-in-progress state.
  echo "Waiting for PR #$MERGE_BASELINE_PR to reach MERGED state …"
  MAX_MERGE_POLLS=60
  MERGE_POLL_INTERVAL=5
  for i in $(seq 1 "$MAX_MERGE_POLLS"); do
    PR_STATE="$(gh pr view "$MERGE_BASELINE_PR" --repo "$REPO" \
      --json state -q '.state' 2>/dev/null || echo '')"
    if [ "$PR_STATE" = "MERGED" ]; then
      echo "PR #$MERGE_BASELINE_PR is merged."
      break
    fi
    if [ "$i" -eq "$MAX_MERGE_POLLS" ]; then
      echo "ERROR: PR #$MERGE_BASELINE_PR did not reach MERGED state within $((MAX_MERGE_POLLS * MERGE_POLL_INTERVAL))s (last state: $PR_STATE)." >&2
      exit 1
    fi
    sleep "$MERGE_POLL_INTERVAL"
  done
fi

# ---------------------------------------------------------------------------
# Artifact download directory
# ---------------------------------------------------------------------------
ARTIFACT_DIR="${ARTIFACT_DIR:-/tmp/repo_architect_artifacts}"
mkdir -p "$ARTIFACT_DIR"

# ---------------------------------------------------------------------------
# Helper: wait for a new run ID to appear after dispatch.
#
# Strategy (race-condition safe, correctly scoped):
#   - Records DISPATCH_TIME (UTC ISO-8601) immediately before gh workflow run.
#   - Filters gh run list by --branch, --event workflow_dispatch so scheduled
#     or push-triggered runs on other branches cannot be picked up.
#   - Only considers runs whose createdAt >= DISPATCH_TIME (further eliminates
#     any workflow_dispatch run that was already in flight before our dispatch).
#   - Compares against BEFORE_RUN_ID to skip any pre-existing run with the
#     same creation second (extremely unlikely but defensive).
# ---------------------------------------------------------------------------
wait_for_new_run_id() {
  local dispatch_time="$1"   # ISO-8601 timestamp captured just before dispatch
  local before_id="$2"
  local max_attempts=30
  local poll_interval=3
  local run_id=""

  for attempt in $(seq 1 "$max_attempts"); do
    # Query only workflow_dispatch runs on our branch created at/after dispatch.
    # Pipe to jq separately so --arg is passed to jq (gh -q does not forward --arg).
    run_id="$(gh run list \
      --repo "$REPO" \
      --workflow "$WORKFLOW_FILE" \
      --branch "$BRANCH" \
      --event workflow_dispatch \
      --limit 5 \
      --json databaseId,createdAt \
      2>/dev/null | \
      jq -r --arg ts "$dispatch_time" \
        '[.[] | select(.createdAt >= $ts)] | .[0].databaseId // empty' \
      2>/dev/null || true)"
    if [ -n "$run_id" ] && [ "$run_id" != "$before_id" ]; then
      echo "$run_id"
      return 0
    fi
    sleep "$poll_interval"
  done

  echo "ERROR: timed out waiting for new workflow run after $((max_attempts * poll_interval))s (dispatch_time=$dispatch_time, before_id=$before_id)." >&2
  return 1
}

# ---------------------------------------------------------------------------
# Helper: dispatch one slice, wait for completion, download and validate.
# Arguments:
#   $1  slice_name      — human label (used for artifact directory)
#   $2  mode            — report | mutate | campaign
#   $3  lanes           — comma-separated lane order (empty = workflow default)
#   $4  mutation_budget — integer (default 1)
# ---------------------------------------------------------------------------
run_slice() {
  local slice_name="$1"
  local mode="$2"
  local lanes="${3:-}"
  local mutation_budget="${4:-1}"

  echo ""
  echo "============================================================"
  echo "SLICE: $slice_name  [mode=$mode  lanes=${lanes:-<default>}]"
  echo "============================================================"

  # Capture timestamp and last-known run ID before dispatch so we can
  # isolate the exact run we are about to create.
  DISPATCH_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  BEFORE_RUN_ID="$(gh run list \
    --repo "$REPO" \
    --workflow "$WORKFLOW_FILE" \
    --branch "$BRANCH" \
    --event workflow_dispatch \
    --limit 1 \
    --json databaseId \
    -q '.[0].databaseId // empty' 2>/dev/null || echo '')"

  # Build dispatch field arguments.
  DISPATCH_ARGS=(
    --repo "$REPO"
    --ref "$BRANCH"
    --field "mode=$mode"
    --field "mutation_budget=$mutation_budget"
  )
  if [ -n "$lanes" ]; then
    DISPATCH_ARGS+=(--field "lanes=$lanes")
  fi

  # Dispatch the workflow run.
  gh workflow run "$WORKFLOW_FILE" "${DISPATCH_ARGS[@]}"

  # Brief pause to let the GitHub API register the new run.
  sleep "$GH_API_DELAY"

  # Poll until the new run appears; bound to our branch, event, and dispatch time.
  RUN_ID="$(wait_for_new_run_id "$DISPATCH_TIME" "$BEFORE_RUN_ID")"

  if [ -z "$RUN_ID" ]; then
    echo "ERROR: could not resolve run ID for slice '$slice_name'." >&2
    return 1
  fi
  echo "Run ID: $RUN_ID — waiting for completion …"

  # Block until the run finishes; non-zero exit if the run fails.
  gh run watch "$RUN_ID" --repo "$REPO" --exit-status

  # Download artifacts — fail hard on download failure.
  SLICE_DIR="$ARTIFACT_DIR/$slice_name"
  mkdir -p "$SLICE_DIR"
  if ! gh run download "$RUN_ID" \
    --repo "$REPO" \
    --dir "$SLICE_DIR" \
    --pattern "repo-architect-$RUN_ID" 2>/dev/null; then
    gh run download "$RUN_ID" \
      --repo "$REPO" \
      --dir "$SLICE_DIR"
  fi

  # Locate the analysis JSON — fail hard if absent.
  ANALYSIS_FILE="$(find "$SLICE_DIR" -name "latest_analysis.json" -type f 2>/dev/null | head -1)"

  echo ""
  echo "--- Validation for slice: $slice_name ---"

  if [ -z "$ANALYSIS_FILE" ]; then
    echo "ERROR: latest_analysis.json not found in artifacts for slice '$slice_name'." >&2
    return 1
  fi

  ACTUAL_MODE="$(jq -r '.mode // .analysis.mode // "unknown"' "$ANALYSIS_FILE" 2>/dev/null || echo unknown)"
  ACTUAL_STATUS="$(jq -r '.status // .analysis.status // "unknown"' "$ANALYSIS_FILE" 2>/dev/null || echo unknown)"
  ARCH_SCORE="$(jq -r '.architecture_score // .analysis.architecture_score // "n/a"' "$ANALYSIS_FILE" 2>/dev/null || echo n/a)"
  CHANGED_FILES="$(jq -r '(.changed_files // .analysis.changed_files // []) | length' "$ANALYSIS_FILE" 2>/dev/null || echo 0)"
  PR_URL="$(jq -r '.pr_url // .analysis.pr_url // ""' "$ANALYSIS_FILE" 2>/dev/null || echo "")"

  echo "  mode:               $ACTUAL_MODE"
  echo "  status:             $ACTUAL_STATUS"
  echo "  architecture score: $ARCH_SCORE"
  echo "  changed files:      $CHANGED_FILES"
  if [ -n "$PR_URL" ] && [ "$PR_URL" != "null" ]; then
    echo "  PR URL:             $PR_URL"
  fi

  # Hard-fail on unexpected mode (field may be absent for some run types — allow unknown).
  if [ "$ACTUAL_MODE" != "unknown" ] && [ "$ACTUAL_MODE" != "$mode" ]; then
    echo "ERROR: expected mode '$mode' but analysis reports '$ACTUAL_MODE' for slice '$slice_name'." >&2
    return 1
  fi

  echo "--- Run $RUN_ID complete for slice '$slice_name' ---"
}

# ---------------------------------------------------------------------------
# Slice sequence
# ---------------------------------------------------------------------------

# 1. Full architecture report
run_slice "report"                   "report"    ""

# 2. Parse errors — fix syntax/parse issues
run_slice "parse_errors"             "mutate"    "parse_errors"

# 3. Import cycles — break local circular dependencies
run_slice "import_cycles"            "mutate"    "import_cycles"

# 4. Entrypoint consolidation — reduce duplicate entrypoints
run_slice "entrypoint_consolidation" "mutate"    "entrypoint_consolidation"

# 5. Hygiene — remove marked debug prints
run_slice "hygiene"                  "mutate"    "hygiene"

# 6. Campaign — all lanes sequentially
run_slice "campaign"                 "campaign"  ""  "1"

echo ""
echo "============================================================"
echo "All slices completed. Artifacts in: $ARTIFACT_DIR"
echo "============================================================"
