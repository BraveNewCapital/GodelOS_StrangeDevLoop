#!/usr/bin/env bash
# bootstrap_repo_architect_slices.sh
# Bootstrap convenience script: writes the workflow and runner scripts from
# their canonical source into the repository paths for local development.
# Run this once to (re)initialise the fat-slices execution path.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Repository root: $REPO_ROOT"

# ---------------------------------------------------------------------------
# 1. Write .github/workflows/repo-architect.yml
# ---------------------------------------------------------------------------
WORKFLOW_DIR="$REPO_ROOT/.github/workflows"
mkdir -p "$WORKFLOW_DIR"

cat > "$WORKFLOW_DIR/repo-architect.yml" << 'WORKFLOW_EOF'
name: repo-architect

on:
  workflow_dispatch:
    inputs:
      mode:
        description: 'Execution mode'
        required: true
        default: 'report'
        type: choice
        options:
          - analyze
          - report
          - mutate
      lane:
        description: 'Slice lane name (e.g. report_packet, parse_repair:test_pipeline)'
        required: false
        default: ''
        type: string
      targets:
        description: 'Comma-separated list of files/modules for this slice'
        required: false
        default: ''
        type: string
      github_model:
        description: 'GitHub Models model id'
        required: true
        default: 'openai/gpt-4.1'
        type: string
      report_path:
        description: 'Primary report path'
        required: true
        default: 'docs/repo_architect/runtime_inventory.md'
        type: string
      mutation_budget:
        description: 'Maximum automatic mutations in a single run'
        required: true
        default: '1'
        type: choice
        options:
          - '1'
          - '2'
          - '3'
      allow_dirty:
        description: 'Allow dirty working tree'
        required: false
        default: 'true'
        type: choice
        options:
          - 'true'
          - 'false'
  schedule:
    - cron: '17 * * * *'

concurrency:
  group: repo-architect-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: write
  pull-requests: write
  models: read

jobs:
  repo-architect:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.x'

      - name: Configure git identity
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

      - name: Run repo architect
        env:
          GITHUB_TOKEN: ${{ github.token }}
          GITHUB_REPO: ${{ github.repository }}
          GITHUB_BASE_BRANCH: ${{ github.event.repository.default_branch }}
          GITHUB_MODEL: ${{ github.event.inputs.github_model || 'openai/gpt-4.1' }}
          REPO_ARCHITECT_LANE: ${{ github.event.inputs.lane || '' }}
          REPO_ARCHITECT_TARGETS: ${{ github.event.inputs.targets || '' }}
        run: |
          MODE="${{ github.event.inputs.mode }}"
          REPORT_PATH="${{ github.event.inputs.report_path }}"
          MUTATION_BUDGET="${{ github.event.inputs.mutation_budget }}"
          ALLOW_DIRTY="${{ github.event.inputs.allow_dirty }}"
          if [ -z "$MODE" ]; then MODE="report"; fi
          if [ -z "$REPORT_PATH" ]; then REPORT_PATH="docs/repo_architect/runtime_inventory.md"; fi
          if [ -z "$MUTATION_BUDGET" ]; then MUTATION_BUDGET="1"; fi
          if [ -z "$ALLOW_DIRTY" ]; then ALLOW_DIRTY="true"; fi

          # Detect optional --lane / --targets CLI support; fall back to env vars if absent
          HELP_TEXT="$(python repo_architect.py --help 2>&1)"
          EXTRA_ARGS=()
          if echo "$HELP_TEXT" | grep -q -- '--lane'; then
            if [ -n "$REPO_ARCHITECT_LANE" ]; then
              EXTRA_ARGS+=(--lane "$REPO_ARCHITECT_LANE")
            fi
          fi
          if echo "$HELP_TEXT" | grep -q -- '--targets'; then
            if [ -n "$REPO_ARCHITECT_TARGETS" ]; then
              EXTRA_ARGS+=(--targets "$REPO_ARCHITECT_TARGETS")
            fi
          fi

          if [ "$ALLOW_DIRTY" = "true" ]; then
            EXTRA_ARGS+=(--allow-dirty)
          fi

          python repo_architect.py \
            --mode "$MODE" \
            --report-path "$REPORT_PATH" \
            --mutation-budget "$MUTATION_BUDGET" \
            "${EXTRA_ARGS[@]}"

      - name: Upload repo architect artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: repo-architect-${{ github.run_id }}
          path: |
            .agent
            docs/repo_architect
          include-hidden-files: true
          if-no-files-found: warn
          retention-days: 7
WORKFLOW_EOF

echo "Written: $WORKFLOW_DIR/repo-architect.yml"

# ---------------------------------------------------------------------------
# 2. Write scripts/run_repo_architect_slices.sh
# ---------------------------------------------------------------------------
SCRIPTS_DIR="$REPO_ROOT/scripts"
mkdir -p "$SCRIPTS_DIR"

cat > "$SCRIPTS_DIR/run_repo_architect_slices.sh" << 'RUNNER_EOF'
#!/usr/bin/env bash
# run_repo_architect_slices.sh
# Dispatches a sequence of repo-architect workflow slices via GitHub Actions,
# waits for each to complete, downloads artifacts, and validates the results.

set -euo pipefail

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
for cmd in gh python3 jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: required command '$cmd' not found." >&2
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# Repo detection
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

# Delay (seconds) after workflow dispatch before polling for the new run ID.
# Configurable to account for high-load GitHub API conditions.
GH_API_DELAY="${GH_API_DELAY:-5}"

# ---------------------------------------------------------------------------
# Optional: merge a baseline PR before dispatching slices
# ---------------------------------------------------------------------------
if [ -n "${MERGE_BASELINE_PR:-}" ]; then
  echo "Merging baseline PR #$MERGE_BASELINE_PR …"
  gh pr merge "$MERGE_BASELINE_PR" --repo "$REPO" --squash --auto || true
fi

# ---------------------------------------------------------------------------
# Artifact download directory
# ---------------------------------------------------------------------------
ARTIFACT_DIR="${ARTIFACT_DIR:-/tmp/repo_architect_artifacts}"
mkdir -p "$ARTIFACT_DIR"

# ---------------------------------------------------------------------------
# Helper: wait for a new run ID to appear after dispatch.
# Records the most-recent run ID *before* dispatch, then polls until a
# different (newer) run appears — avoiding the race where gh run list
# returns a concurrent unrelated run.
# ---------------------------------------------------------------------------
wait_for_new_run_id() {
  local before_id="$1"
  local max_attempts=20
  local poll_interval=3
  local run_id=""

  for attempt in $(seq 1 "$max_attempts"); do
    run_id="$(gh run list \
      --repo "$REPO" \
      --workflow "$WORKFLOW_FILE" \
      --limit 1 \
      --json databaseId \
      -q '.[0].databaseId' 2>/dev/null || true)"
    if [ -n "$run_id" ] && [ "$run_id" != "$before_id" ]; then
      echo "$run_id"
      return 0
    fi
    sleep "$poll_interval"
  done

  echo "ERROR: timed out waiting for new workflow run to appear (attempt $attempt/$max_attempts)." >&2
  return 1
}

# ---------------------------------------------------------------------------
# Helper: dispatch one slice, wait, download, validate
# ---------------------------------------------------------------------------
run_slice() {
  local slice_name="$1"
  local mode="$2"
  local lane="$3"
  local targets="$4"
  local mutation_budget="${5:-1}"

  echo ""
  echo "============================================================"
  echo "SLICE: $slice_name  [mode=$mode  lane=$lane]"
  echo "============================================================"

  # Record current latest run ID before dispatch to detect the new one reliably
  BEFORE_RUN_ID="$(gh run list \
    --repo "$REPO" \
    --workflow "$WORKFLOW_FILE" \
    --limit 1 \
    --json databaseId \
    -q '.[0].databaseId' 2>/dev/null || echo '')"

  # Dispatch the workflow
  gh workflow run "$WORKFLOW_FILE" \
    --repo "$REPO" \
    --ref "$BRANCH" \
    --field "mode=$mode" \
    --field "lane=$lane" \
    --field "targets=$targets" \
    --field "mutation_budget=$mutation_budget" \
    --field "allow_dirty=true"

  # Brief pause to let the GitHub API register the new run
  sleep "$GH_API_DELAY"

  # Poll until the new run appears (avoids race with concurrent runs)
  RUN_ID="$(wait_for_new_run_id "$BEFORE_RUN_ID")"

  if [ -z "$RUN_ID" ]; then
    echo "ERROR: could not retrieve run ID for slice '$slice_name'." >&2
    return 1
  fi
  echo "Waiting for run $RUN_ID …"

  # Wait for completion; exits non-zero if the run fails
  gh run watch "$RUN_ID" --repo "$REPO" --exit-status

  # Download artifacts
  SLICE_DIR="$ARTIFACT_DIR/$slice_name"
  mkdir -p "$SLICE_DIR"
  gh run download "$RUN_ID" \
    --repo "$REPO" \
    --dir "$SLICE_DIR" \
    --pattern "repo-architect-$RUN_ID" 2>/dev/null || \
  gh run download "$RUN_ID" \
    --repo "$REPO" \
    --dir "$SLICE_DIR" || true

  # Locate the analysis JSON (may be nested under artifact folder)
  ANALYSIS_FILE="$(find "$SLICE_DIR" -name "latest_analysis.json" -type f | head -1 || true)"

  echo ""
  echo "--- Validation for slice: $slice_name ---"

  if [ -z "$ANALYSIS_FILE" ]; then
    echo "WARNING: latest_analysis.json not found in downloaded artifacts."
  else
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

    # Best-effort mode assertion (field may be absent for some modes)
    if [ "$ACTUAL_MODE" != "unknown" ] && [ "$ACTUAL_MODE" != "$mode" ]; then
      echo "WARNING: expected mode '$mode' but analysis reports '$ACTUAL_MODE'."
    fi
  fi

  echo "--- Run $RUN_ID complete for slice '$slice_name' ---"
}

# ---------------------------------------------------------------------------
# Slice sequence
# ---------------------------------------------------------------------------

# 1. Report packet — gather the full current-state report
run_slice \
  "report_packet" \
  "report" \
  "report_packet" \
  "" \
  "1"

# 2. Parse repair — tests/nlu_nlg/nlu/test_pipeline.py
run_slice \
  "parse_repair_test_pipeline" \
  "mutate" \
  "parse_repair:test_pipeline" \
  "tests/nlu_nlg/nlu/test_pipeline.py" \
  "1"

# 3. Parse repair — tests/nlu_nlg/nlu/test_lexical_analyzer_parser.py
run_slice \
  "parse_repair_test_lexical_analyzer_parser" \
  "mutate" \
  "parse_repair:test_lexical_analyzer_parser" \
  "tests/nlu_nlg/nlu/test_lexical_analyzer_parser.py" \
  "1"

# 4. Import cycle — agentic_daemon_system + grounding_coherence_daemon
run_slice \
  "import_cycle_agentic_grounding" \
  "mutate" \
  "import_cycle:agentic_grounding" \
  "backend/core/agentic_daemon_system.py,backend/core/grounding_coherence_daemon.py" \
  "1"

# 5. Import cycle — chroma_store + interface
run_slice \
  "import_cycle_chroma_interface" \
  "mutate" \
  "import_cycle:chroma_interface" \
  "godelOS/core_kr/knowledge_store/chroma_store.py,godelOS/core_kr/knowledge_store/interface.py" \
  "1"

# 6. Import cycle — type_system manager + visitor
run_slice \
  "import_cycle_type_system" \
  "mutate" \
  "import_cycle:type_system" \
  "godelOS/core_kr/type_system/manager.py,godelOS/core_kr/type_system/visitor.py" \
  "1"

echo ""
echo "============================================================"
echo "All slices completed. Artifacts in: $ARTIFACT_DIR"
echo "============================================================"
RUNNER_EOF

chmod +x "$SCRIPTS_DIR/run_repo_architect_slices.sh"
echo "Written + chmod +x: $SCRIPTS_DIR/run_repo_architect_slices.sh"

echo ""
echo "Bootstrap complete."
echo "  Workflow:      $WORKFLOW_DIR/repo-architect.yml"
echo "  Runner script: $SCRIPTS_DIR/run_repo_architect_slices.sh"
