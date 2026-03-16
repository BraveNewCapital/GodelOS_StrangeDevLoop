# repo-architect Operator Guide

## Operating Model

`repo_architect.py` is an **architectural governance** tool that inspects the repository, diagnoses structural and operational gaps, and runs a continuous closed-loop system for issue tracking, Copilot delegation, and PR reconciliation.

### Four operating lanes

```
Planning lane:   analyze → diagnose → dedupe → create/update issue
Execution lane:  select ready issue → delegate to Copilot → track PR
Memory lane:     ingest issue/PR state → update work state → feed next planning cycle
Scheduler lane:  run automatically on a schedule with safe gating and no duplicate execution
```

### Default safe mode: issue-first governance

```
inspect repo → identify architectural gap → deduplicate against existing issues
    → open/update GitHub Issue → attach Copilot prompt → report outcome
```

The GitHub Issue becomes the mutation surface. Copilot or a human becomes the code author. CI validates the resulting implementation PRs.

### Execution lane

```
load work state → reconcile open PRs → select one ready issue
    → delegate to Copilot (label + assign + comment) → save work state
```

The execution lane selects at most one issue per run. Delegation is either dry-run (report only) or live (calls GitHub API). Live delegation requires `--enable-live-delegation` or `ENABLE_LIVE_DELEGATION=true`.

### Reconciliation lane

```
load work state → list recent PRs → match PRs to tracked issues
    → update pr_state/merged/closed → update lifecycle labels → save work state
```

Reconciliation feeds the memory lane. After reconciliation, the planning lane can see which issues have open PRs, which have merged, and which are stale.

### Charter-validated secondary modes: lane-based mutation

```
inspect repo → generate code diff → create branch → open PR → repeat
```

Modes `mutate` and `campaign` implement the narrow, validated self-modification lanes defined in the **GODELOS_REPO_IMPLEMENTATION_CHARTER §9–§10**. They are retained as charter-sanctioned secondary modes that require explicit opt-in (`--mode mutate` or `--mode campaign`). They are not the default execution path.

---

## Architectural Reconciliation

This section documents how the repo-architect operating model aligns with the project's canonical architectural specifications.

> **Authoritative sources:**
> - `docs/architecture/GODELOS_ARCHITECTURAL_CHARTER.md`
> - `docs/architecture/GODELOS_REPO_IMPLEMENTATION_CHARTER.md`
>
> These documents are the source of truth. If implementation and documentation conflict, the charters govern.

### Core principles from the charters

The architectural charters establish that:

1. **Issue-first governance is the default execution model** — the repo-architect loop diagnoses gaps, prioritises them by charter lane, and synthesizes structured GitHub Issues for human or Copilot implementation.
2. **Mutation lanes defined in the implementation charter remain part of the architecture** — Lanes 0–9 are charter-defined categories of narrow, validated self-modification work.
3. **Automated mutation is currently gated for safety** — direct code mutation via `--mode mutate`/`--mode campaign` requires explicit opt-in and remains bounded by validation floors (§9.3), mutation budget policy (§11), and the PR contract (§12).
4. **The repo-architect loop still diagnoses and prioritises all lanes** — even lanes where automated mutation is not yet safe are represented in gap detection, issue synthesis, and diagnostics.

### Full charter lane reference (§10 GODELOS_REPO_IMPLEMENTATION_CHARTER)

| Lane | Name | Purpose | Automated? | Gap detection |
|---|---|---|---|---|
| **0** | Report generation | Generate architecture packets, refresh inventories, update risk docs | ✅ (`report` lane) | Architecture score degradation |
| **1** | Hygiene | Remove debug prints, dead code, simplify internal clutter | ✅ (`hygiene` lane) | — |
| **2** | Parse repair | Repair syntax errors, restore parsability | ✅ (`parse_errors` lane) | Parse error detection |
| **3** | Circular dependency elimination | Break import cycles structurally | ✅ (`import_cycles` lane) | Import cycle detection |
| **4** | Entrypoint consolidation | Reduce runtime duplication, delegate launchers to canonical root | ✅ (`entrypoint_consolidation` lane) | Entrypoint fragmentation detection |
| **5** | Contract repair | Normalise interfaces, repair adapter mismatches | 🔒 Issue-only | Dependency direction violation detection |
| **6** | Runtime extraction | Move orchestration logic from scripts into runtime modules | 🔒 Issue-only | — (future) |
| **7** | Agent boundary enforcement | Isolate agent state, replace cross-module reach-through | 🔒 Issue-only | Agent boundary violation detection |
| **8** | Knowledge substrate normalisation | Centralise persistent knowledge access | 🔒 Issue-only | — (future) |
| **9** | Consciousness instrumentation | Add metrics, traces, introspection paths for self-awareness research | 🔒 Issue-only | — (future) |

**Legend:** ✅ = available in `mutate`/`campaign` modes; 🔒 = addressed via issue synthesis with Copilot-ready prompts.

### Alignment with GODELOS_ARCHITECTURAL_CHARTER

| Charter principle | How this system honours it |
|---|---|
| **§14 Effective Gödel-Machine Program** — "modelling its own architecture, detecting defects, proposing candidate modifications, validating them" | Issue mode inspects, diagnoses, and synthesizes structured proposals across all 10 charter lanes. Lane-based mutation validates changes before adoption. |
| **§15.1 Explicitness** — "every modification must be explainable in terms of a defect, an invariant, a capability target, or a charter objective" | Every issue body includes Summary, Problem, Why it matters, Scope, and Machine metadata tying it to a specific gap and charter lane. |
| **§15.2 Boundedness** — "no change may introduce unbounded recursion" | Issue mode produces no code at all. Mutation modes are scoped to one lane per slice with mutation budget limits (§11). |
| **§15.3 Reversibility** — "mutations should be small, inspectable, and reversible" | Mutation lanes produce thin, single-purpose PRs. Issue mode delegates implementation to Copilot/humans under review. |
| **§15.4 Validation** — "a change is not admissible unless it passes the relevant validation regime" | Lane-based mutations run `ast.parse`, `py_compile`, and lane-specific validation before pushing (§9.3). |
| **§15.5 Convergence** — "purpose of self-modification is convergence" | Both modes share the same analysis engine and prioritize gaps by architectural convergence impact per §14 priority order. |
| **§20 Repository Automation Policy** — "automation should prioritize parse correctness, dependency/import-cycle reduction, convergence toward canonical runtime structure" | Gap detection follows the same ordered concerns: parse errors → import cycles → entrypoint fragmentation → dependency violations → agent boundaries → score degradation → workflow drift. |

### Alignment with GODELOS_REPO_IMPLEMENTATION_CHARTER

| Charter section | How this system honours it |
|---|---|
| **§9 Self-Modification Contract** — allows code generation proposals, small structural refactors, contract extraction, etc. with a validation floor | Lane-based mutation modes (mutate/campaign) implement exactly these allowed forms with `ast.parse`/`py_compile` validation. Issue mode synthesizes proposals that instruct Copilot to follow the same contract. |
| **§10 Repo-Architect Mutation Lanes** — defines Lanes 0–9 for narrow, explicit work | All 10 lanes are represented: Lanes 0–4 in `MUTATION_LANE_ORDER` for automated mutation; Lanes 0–9 in `CHARTER_LANE_MAP` for gap detection and issue synthesis. |
| **§11 Mutation Budget Policy** — "thin and rapid, but never indiscriminate" | `--mutation-budget` (default 1) and `--max-slices` (default 3) enforce thinness for mutation modes. Issue mode respects `--max-issues` (default 1). |
| **§12 Pull Request Contract for Agents** — every PR must state lane, files, invariant, validation, next lane | Lane-based mutations produce structured PR bodies with all required fields. Issue-generated Copilot prompts instruct the same contract. |
| **§14 Current Priority Order** — parse correctness → import cycles → entrypoint reduction → knowledge substrate → agent boundaries → consciousness instrumentation | `diagnose_gaps()` and `MUTATION_LANE_ORDER` follow this priority stack. Higher lanes (5–9) are surfaced as issues when their signals are detected. |

### Why issue-first is the default

The charters support both diagnosis/governance and narrow validated mutation. Making issue-first the default:

1. **Reduces risk** — no autonomous code changes without human or Copilot review.
2. **Scales to higher lanes** — contract repair (Lane 5), runtime extraction (Lane 6), agent boundary enforcement (Lane 7), knowledge substrate normalisation (Lane 8), and consciousness instrumentation (Lane 9) require judgment that exceeds what the current analysis engine can safely validate. Issue synthesis expresses these as structured Copilot prompts.
3. **Preserves the lane model** — every detected gap maps to a charter lane. The issue body references the affected subsystem and lane-appropriate scope.
4. **Satisfies §15.2 boundedness** — the safest mutation budget is zero autonomous code changes by default, with explicit opt-in for narrow validated lanes.

Operators who need autonomous lane-based mutation can use `--mode mutate` or `--mode campaign` at any time.

---

## Modes

| Mode | Description | Charter basis | Default? |
|---|---|---|---|
| `issue` | **Default safe governance mode.** Detects gaps and opens/updates GitHub Issues with Copilot-ready prompts. | §14 Effective Gödel-Machine, §15 Self-Modification Doctrine, §20 Automation Policy | ✅ Yes |
| `execution` | Selects one ready issue and delegates it to Copilot (dry-run or live). | Execution lane — closed-loop extension | Scheduled |
| `reconcile` | Ingests PR outcomes back into durable work state. | Reconciliation lane — memory loop | Scheduled |
| `analyze` | Build analysis and write `.agent/` artifacts. No GitHub API calls. | §20 Automation Policy | Read-only |
| `report` | Refresh `docs/repo_architect/` documentation reports. | Lane 0 (Report generation) | Read-only |
| `mutate` | Attempt one direct code mutation via charter-validated lanes. | §9–§10 Self-Modification Contract, Lanes 0–4 | Opt-in |
| `campaign` | Run multiple mutation slices across lanes. | §9–§11 Self-Modification Contract, Mutation Budget | Opt-in |

The default mode (both CLI and scheduled workflow) is `issue`.

---

## Issue Mode

### What it does

1. Loads durable work state (memory lane) to avoid re-raising issues already actively in-progress.
2. Builds repository analysis (parse errors, import cycles, entrypoints, architecture score).
3. Calls GitHub Models for an architectural risk summary (if credentials are available).
4. Diagnoses concrete architectural gaps from the analysis.
5. Filters gaps already covered by active delegations in work state.
6. Deduplicates: searches existing open issues for each gap using a deterministic fingerprint.
7. Creates a new GitHub Issue (or updates an existing one with a comment).
8. Records newly created issues in durable work state for future planning passes.
9. Emits a structured JSON result and workflow step summary.

### Running it

```bash
# Live mode: create/update real GitHub Issues
python repo_architect.py --mode issue --allow-dirty

# Dry-run: write issue bodies to disk without API calls
python repo_architect.py --mode issue --allow-dirty --dry-run

# Target a specific subsystem
python repo_architect.py --mode issue --allow-dirty --issue-subsystem runtime

# Open up to 3 issues per run
python repo_architect.py --mode issue --allow-dirty --max-issues 3
```

### Environment variables

| Variable | Description |
|---|---|
| `GITHUB_TOKEN` | Required for live issue creation. Must have `issues: write` permission. |
| `GITHUB_REPO` | Repository in `owner/repo` format. |
| `REPO_ARCHITECT_PREFERRED_MODEL` | Preferred GitHub Models model ID. |
| `REPO_ARCHITECT_FALLBACK_MODEL` | Fallback model if preferred is unavailable. |
| `REPO_ARCHITECT_SUBSYSTEM` | Target subsystem for gap detection. |

### CLI flags

| Flag | Default | Description |
|---|---|---|
| `--mode issue` | `issue` | Operating mode |
| `--dry-run` | `false` | Write issue bodies to disk only |
| `--max-issues N` | `1` | Maximum issues to open/update per run |
| `--issue-subsystem X` | all | Restrict to one subsystem |
| `--allow-dirty` | `false` | Skip dirty-worktree check |

---

## Execution Lane

### What it does

1. Loads durable work state.
2. Runs lightweight PR reconciliation to refresh issue states.
3. Selects at most one issue that is ready for delegation (eligible labels + not blocked/in-progress).
4. Delegates to Copilot: applies `in-progress` label, assigns to `@copilot`, posts delegation comment.
5. Records the delegation in work state.

### Selection rules

- Issue must have all of: `arch-gap`, `copilot-task`, `needs-implementation`
- Issue must NOT have: `blocked`, `superseded`, `in-progress`, `pr-open`, `merged`
- Fingerprint must not already be delegated
- At most one issue per charter lane at a time
- Respects `MAX_CONCURRENT_DELEGATED` limit (default: 1)
- Prefers highest priority first (critical > high > medium > low)

### Running it

```bash
# Dry-run: report what would be delegated (default)
python repo_architect.py --mode execution --allow-dirty

# Live delegation to Copilot via GitHub API
python repo_architect.py --mode execution --allow-dirty --enable-live-delegation

# Restrict to a specific objective
python repo_architect.py --mode execution --allow-dirty --active-objective eliminate-import-cycles

# Restrict to a specific lane
python repo_architect.py --mode execution --allow-dirty --lane-filter import_cycles
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `ENABLE_LIVE_DELEGATION` | `false` | Enable live GitHub API delegation |
| `MAX_CONCURRENT_DELEGATED` | `1` | Max simultaneous in-flight delegations |
| `ACTIVE_OBJECTIVE` | (any) | Restrict selection to a specific objective key |
| `LANE_FILTER` | (any) | Restrict selection to a specific charter lane |
| `STALE_TIMEOUT_DAYS` | `14` | Days before a delegated-but-PR-less item is marked stale |

### Valid objective keys

| Key | Description |
|---|---|
| `restore-parse-correctness` | Restore or preserve parse correctness (Lane 2) |
| `eliminate-import-cycles` | Eliminate import cycles (Lane 3) |
| `converge-runtime-structure` | Converge runtime entrypoint structure (Lane 4) |
| `normalise-knowledge-substrate` | Normalise knowledge substrate boundaries (Lane 8) |
| `isolate-agent-boundaries` | Isolate agent boundaries (Lane 7) |
| `reduce-architecture-score-risk` | Reduce architecture score risk (Lanes 0–9) |
| `add-consciousness-instrumentation` | Add consciousness instrumentation (Lane 9) |

### How Copilot execution is triggered

In live mode, the execution lane:

1. Applies `in-progress` label and removes `ready-for-delegation`.
2. Assigns the issue to `@copilot` (GitHub Copilot coding agent username).
3. Posts a delegation comment with the active objective, lane, and fingerprint.

GitHub Copilot coding agent is automatically triggered when an issue is assigned to `@copilot`. It reads the issue body (including the Copilot implementation prompt) and opens a PR. The reconciliation lane then detects this PR and updates the work state.

---

## Reconciliation Lane

### What it does

1. Loads durable work state.
2. Fetches all recent PRs from the repository.
3. For each tracked issue, detects linked PRs (by `#issue_number` reference in PR body/title).
4. Updates item state: `merged`, `closed_unmerged`, `open`, `draft`, `stale`.
5. Updates lifecycle labels on the GitHub Issue.
6. Saves updated work state.

### PR state classifications

| Classification | Condition |
|---|---|
| `merged` | PR has `merged_at` timestamp |
| `closed_unmerged` | PR state is `closed` and no `merged_at` |
| `draft` | PR is open and marked as draft |
| `open` | PR is open and not draft |
| `stale` | No PR found and item has been delegated for > `STALE_TIMEOUT_DAYS` days |

### Running it

```bash
# Ingest PR outcomes
python repo_architect.py --mode reconcile --allow-dirty

# With custom thresholds
python repo_architect.py --mode reconcile --allow-dirty --stale-timeout-days 7 --reconciliation-window-days 60
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `STALE_TIMEOUT_DAYS` | `14` | Days before a delegated-but-PR-less item is marked stale |
| `RECONCILIATION_WINDOW_DAYS` | `30` | Days of PRs to consider during reconciliation |

### How issues and PRs feed the next planning cycle

After reconciliation:
- Issues with `merged` PRs are marked `done` in work state → planner can generate follow-on work.
- Issues with `open` PRs are blocked from re-delegation → planner skips them.
- Issues with `stale` status are flagged → operator can review or unblock.
- Issues with `closed_unmerged` PRs are marked done (superseded) → planner can re-raise if still needed.

---

## Durable Work State (Memory Lane)

The work state is stored in `.agent/work_state.json` (gitignored, refreshed each run).

### Schema

```json
{
  "version": "2.1.0",
  "updated_at": "2026-01-01T00:00:00+00:00",
  "items": [
    {
      "fingerprint": "a1b2c3d4e5f6",
      "objective": "eliminate-import-cycles",
      "lane": "import_cycles",
      "issue_number": 42,
      "issue_state": "open",
      "delegation_state": "delegated",
      "assignee": "copilot",
      "pr_number": 101,
      "pr_url": "https://github.com/org/repo/pull/101",
      "pr_state": "merged",
      "merged": true,
      "closed_unmerged": false,
      "blocked": false,
      "superseded": false,
      "created_at": "2026-01-01T00:00:00+00:00",
      "updated_at": "2026-01-02T00:00:00+00:00",
      "run_id": "12345678-1",
      "gap_title": "Eliminate import cycles in backend.core",
      "gap_subsystem": "runtime"
    }
  ]
}
```

### Field reference

| Field | Type | Description |
|---|---|---|
| `fingerprint` | string | 12-hex deterministic fingerprint from `issue_fingerprint()` |
| `objective` | string | Active objective at time of creation |
| `lane` | string | Charter lane name |
| `issue_number` | int\|null | GitHub Issue number |
| `issue_state` | string | `open` or `closed` |
| `delegation_state` | string | `pending`, `delegated`, `done`, `blocked`, or `superseded` |
| `assignee` | string\|null | GitHub username delegated to |
| `pr_number` | int\|null | Linked PR number |
| `pr_url` | string\|null | Linked PR URL |
| `pr_state` | string\|null | `open`, `draft`, `merged`, `closed_unmerged`, `stale`, or null |
| `merged` | bool | Whether the linked PR merged |
| `closed_unmerged` | bool | Whether the linked PR was closed without merging |
| `blocked` | bool | Whether the item is manually blocked |
| `superseded` | bool | Whether the item has been superseded |
| `created_at` | ISO-8601 | Creation timestamp |
| `updated_at` | ISO-8601 | Last update timestamp |
| `run_id` | string | Workflow run provenance |
| `gap_title` | string | Issue title |
| `gap_subsystem` | string | Detected subsystem |

---

## Label Lifecycle

Labels transition deterministically through the following states:

```
[created]
    └─ arch-gap + copilot-task + needs-implementation
    └─ [optional] ready-for-delegation   (added by planner on first synthesis)

[selected for execution]
    └─ in-progress                       (removes ready-for-delegation)

[PR opened]
    └─ pr-open                           (removes in-progress)

[PR merged]
    └─ merged                            (removes pr-open)

[PR closed unmerged]
    └─ superseded                        (removes pr-open)

[stale: delegated > STALE_TIMEOUT_DAYS with no PR]
    └─ blocked                           (flags for operator review)
```

### All labels used by repo-architect

| Label | Category | Description |
|---|---|---|
| `arch-gap` | Base | Architecture governance issue |
| `copilot-task` | Base | Ready for Copilot to implement |
| `needs-implementation` | Base | Awaiting a code PR |
| `ready-for-delegation` | Lifecycle | Ready for execution selection |
| `in-progress` | Lifecycle | Currently delegated to Copilot |
| `pr-open` | Lifecycle | PR exists and is open |
| `merged` | Lifecycle | PR has merged |
| `blocked` | Lifecycle | Stale or manually blocked |
| `superseded` | Lifecycle | PR closed unmerged or issue replaced |
| `priority:critical` | Priority | Critical priority (applied automatically) |
| `priority:high` | Priority | High priority (applied automatically) |
| Subsystem labels | Subsystem | `runtime`, `core`, `agents`, etc. |

---

## Dry-Run Mode

In dry-run mode (`--dry-run` flag, or `ENABLE_LIVE_DELEGATION=false` for execution mode), the system operates without GitHub API side-effects:

- **Issue mode dry-run**: writes issue bodies to `docs/repo_architect/issues/<fingerprint>.md` instead of calling the Issues API.
- **Execution mode dry-run** (default): reports which issue would be delegated but does not assign labels, assignees, or post comments. Work state is still updated with `delegation_state: pending`.
- **Reconcile mode dry-run**: reads PR state but does not update lifecycle labels on issues.

---

## Scheduled Automation

The workflow runs on three separate schedules:

| Schedule | Cron | Job | Purpose |
|---|---|---|---|
| Planning | `17 * * * *` | `repo-architect-issue` | Hourly gap detection + issue synthesis |
| Execution | `37 */2 * * *` | `repo-architect-execution` | Every 2h: select + delegate one ready issue |
| Reconciliation | `57 */4 * * *` | `repo-architect-reconcile` | Every 4h: ingest PR outcomes into work state |

### Concurrency guards

- The issue job uses `group: repo-architect-${{ github.ref }}` with `cancel-in-progress: true` to prevent concurrent planning runs.
- The execution job uses `group: repo-architect-execution-${{ github.repository }}` with `cancel-in-progress: false` to avoid cancelling an in-flight delegation.
- The reconciliation job uses `group: repo-architect-reconcile-${{ github.repository }}` similarly.

These groups ensure that:
- Two planning runs don't produce duplicate issues.
- An execution run doesn't fire twice and create duplicate delegations.
- A reconciliation run doesn't overlap and corrupt work state.

---

## How Copilot Consumes the Generated Prompt

### Manual (current capability)

1. Maintainer opens the GitHub Issue created by this workflow.
2. In the issue body, find the **Copilot implementation prompt** section.
3. Copy the entire code block.
4. Paste into **GitHub Copilot Chat** (agent mode) or the Copilot Workspace.
5. Copilot reads the referenced files, implements the fix, and opens a PR.
6. CI validates the PR against the **Validation** commands in the issue.
7. Maintainer reviews and merges.

### Automated (via execution lane)

1. Execution lane selects the issue and assigns it to `@copilot`.
2. GitHub Copilot coding agent is triggered automatically on assignment.
3. Copilot reads the issue body and opens a PR.
4. Reconciliation lane detects the PR and updates work state + lifecycle labels.
5. Next planning run sees the in-progress state and skips re-raising the issue.

---

## Workflow Dispatch Inputs

| Input | Default | Description |
|---|---|---|
| `mode` | `issue` | Operating mode (`issue`, `execution`, `reconcile`, `analyze`, `report`, `mutate`, `campaign`) |
| `dry_run` | `false` | Issue mode dry-run without API calls |
| `enable_live_delegation` | `false` | Execution mode: actually delegate via GitHub API |
| `active_objective` | (any) | Execution mode: restrict to a specific objective |
| `lane_filter` | (any) | Execution mode: restrict to a specific charter lane |
| `max_concurrent_delegated` | `1` | Execution mode: max in-flight delegations |
| `stale_timeout_days` | `14` | Reconciliation: days before stale marking |
| `reconciliation_window_days` | `30` | Reconciliation: days of PRs to consider |
| `max_issues` | `1` | Issue mode: max issues per run |
| `issue_subsystem` | (all) | Issue mode: target subsystem |
| `github_model` | (catalog) | Override preferred model |
| `github_fallback_model` | (catalog) | Override fallback model |
| `report_path` | `docs/repo_architect/runtime_inventory.md` | Report output path (analyze/report modes) |
| `mutation_budget` | `1` | Mutation budget per run (mutate mode, charter §11) |
| `max_slices` | `3` | Campaign slices (campaign mode, charter §11) |
| `lanes` | all lanes | Lane order (mutate/campaign modes, charter §10) |

---

## Output Contract (machine-readable JSON)

### Issue mode output

| Field | Description |
|---|---|
| `status` | `issue_cycle_complete` |
| `mode` | `issue` |
| `dry_run` | Whether dry-run mode was active |
| `gaps_detected` | Total gaps found |
| `gaps_selected` | Gaps processed (up to `max_issues`) |
| `issue_actions` | Array of `IssueAction` objects |
| `summary` | Human-readable summary lines |
| `architecture_score` | 1-100 composite health score |
| `artifact_files` | All artifact paths generated |
| `charter` | Charter metadata |

### Execution mode output

| Field | Description |
|---|---|
| `status` | `execution_cycle_complete` |
| `mode` | `execution` |
| `dry_run` | Whether dry-run mode was active |
| `selected_issue` | Dict with `number`, `title`, `url` (or null if nothing selected) |
| `delegation` | Delegation result dict |
| `reconcile` | Embedded reconciliation result |
| `summary` | Human-readable summary lines |

### Reconciliation mode output

| Field | Description |
|---|---|
| `status` | `reconcile_cycle_complete` |
| `mode` | `reconcile` |
| `updated` | Number of work items updated |
| `prs_found` | Number of PRs matched to tracked issues |
| `details` | Array of per-issue reconciliation detail objects |
| `summary` | Human-readable summary lines |

### IssueAction fields

| Field | Description |
|---|---|
| `action` | `created`, `updated`, `dry_run`, or `error` |
| `issue_number` | GitHub Issue number (null for dry-run) |
| `issue_url` | GitHub Issue URL |
| `labels_applied` | Labels *requested* by the orchestration layer (deterministic set sent to the GitHub API) |
| `labels_confirmed` | Labels actually *confirmed* by the GitHub API response after create/update (null for dry-run/error — use this as the source of truth for what labels are on the issue) |
| `dedupe_result` | `new`, `existing_open`, `lookup_failed`, `create_failed`, or `n/a` |
| `fingerprint` | 12-char deterministic fingerprint |
| `dry_run_path` | Relative path to dry-run artifact (dry-run only) |
| `gap_title` | Issue title |
| `gap_subsystem` | Subsystem of the detected gap |
| `error` | Error message (error action only) |

---

## Lane-Based Mutation Modes (Charter §9–§10)

Modes `mutate` and `campaign` implement the narrow, validated self-modification lanes defined in the charter. They are retained as charter-sanctioned secondary modes.

### Lane Priority Order

| Priority | Lane | Charter ref | Behaviour |
|---|---|---|---|
| 1 | `parse_errors` | Lane 2 (Parse repair) | Model-assisted syntax fix. Skipped if no parse errors exist or model is unavailable. |
| 2 | `import_cycles` | Lane 3 (Circular dependency elimination) | Model-assisted import cycle break. Skipped if no cycles or model unavailable. |
| 3 | `entrypoint_consolidation` | Lane 4 (Entrypoint consolidation) | Annotates redundant entrypoints when ≥ 4 exist. Model-assisted. |
| 4 | `hygiene` | Lane 1 (Hygiene) | Remove explicitly `# DEBUG`-marked `print()` statements. No model required. |
| 5 | `report` | Lane 0 (Report generation) | Refresh architecture documentation. Fallback when no code mutation is possible. |

### Running mutation modes

```bash
# Single mutation in lane-priority order
python repo_architect.py --mode mutate --allow-dirty

# Restrict to specific lanes
python repo_architect.py --mode mutate --lane hygiene --allow-dirty

# Multi-slice campaign
python repo_architect.py --mode campaign --allow-dirty --max-slices 3 --lanes parse_errors,import_cycles,hygiene,report
```

### Validation policy (charter §9.3)

Each lane runs validation before pushing:

| Lane | Validation |
|---|---|
| `parse_errors` | `ast.parse` on model-generated content |
| `import_cycles` | `ast.parse` + import smoke test (warn-only) |
| `entrypoint_consolidation` | `ast.parse` on model-generated content |
| `hygiene` | `python -m py_compile` on all touched Python files |
| `report` | Verify report files were written |

Validation failures abort the mutation and **never push a broken branch**.

---

## Issue Structure

Each generated issue follows this template:

| Section | Description |
|---|---|
| **Summary** | 1-2 sentence description of the gap |
| **Problem** | Detailed problem statement with evidence |
| **Why it matters** | Impact and urgency justification |
| **Scope** | Bounded implementation scope |
| **Suggested files** | Repo-relative file paths relevant to the fix |
| **Implementation notes** | Guidance for the implementer |
| **Copilot implementation prompt** | Ready-to-paste prompt for Copilot Chat / agent mode |
| **Acceptance criteria** | Checklist items to verify the fix |
| **Validation** | Shell commands to validate the implementation |
| **Out of scope** | Explicit exclusions |
| **Machine metadata** | Structured JSON: subsystem, priority, confidence, fingerprint, run_id, etc. |

### Machine metadata fields

```json
{
  "subsystem": "runtime",
  "priority": "high",
  "confidence": 0.95,
  "mode": "issue",
  "generated_at": "2026-01-01T00:00:00Z",
  "run_id": "12345678-1",
  "repo": "org/repo",
  "issue_key": "import-cycles",
  "fingerprint": "a1b2c3d4e5f6"
}
```

---

## Detected Gap Types

| Gap | Subsystem | Priority | Charter lane equivalent |
|---|---|---|---|
| Python parse errors | `runtime` | `critical` | Lane 2 (Parse repair) |
| Import cycles | `runtime` | `high` | Lane 3 (Circular dependency elimination) |
| Entrypoint fragmentation (≥4 backend entrypoints) | `runtime` | `medium` | Lane 4 (Entrypoint consolidation) |
| Dependency direction violations | `core` | `medium` | Lane 5 (Contract repair) |
| Agent boundary violations | `agents` | `medium` | Lane 7 (Agent boundary enforcement) |
| Architecture score < 70/100 | `reporting` | `high` / `medium` | Cross-lane |
| Workflow / documentation drift (model-assisted) | `workflow` | `medium` | Lane 0 (Report generation) |

Lanes 6 (Runtime extraction), 8 (Knowledge substrate normalisation), and 9 (Consciousness instrumentation) are represented in `CHARTER_LANE_MAP` and will be detected as gap signals become available in the analysis engine.

---

## Deduplication

Each gap has a deterministic 12-hex-character fingerprint derived from `subsystem:issue_key`. The fingerprint is embedded in the issue body as:

```html
<!-- arch-gap-fingerprint: a1b2c3d4e5f6 -->
```

On each run:
- If a matching **open** issue exists → add a re-scan comment (no new issue).
- If no matching issue exists → create a new one.
- If the fingerprint is already tracked as `delegated` in work state → the planner skips it (no duplicate issue).

---

## Model Selection (preferred / fallback)

The system tries a **preferred** model first and automatically retries with a **fallback** model when unavailable.

| Priority | Source |
|---|---|
| 1 | `--preferred-model` CLI flag |
| 2 | `REPO_ARCHITECT_PREFERRED_MODEL` env var |
| 3 | Hard-coded default (`openai/gpt-5`) |

| Fallback priority | Source |
|---|---|
| 1 | `--fallback-model` CLI flag |
| 2 | `REPO_ARCHITECT_FALLBACK_MODEL` env var |
| 3 | Hard-coded default (`openai/o3`) |

---

## Running Tests

```bash
python -m unittest tests.test_repo_architect -v
```

The test suite covers: branch suffix generation, model fallback, `ast.parse` gate, campaign aggregation, output schema stability, lane priority, `entrypoint_consolidation`, lane scoping, `validate_change`, charter context, issue fingerprint generation, issue body rendering, deduplication behavior, label assignment, gap diagnosis, `run_issue_cycle` output schema, charter-validated mode notices, module-name normalization, companion file existence, **work state ingestion, issue execution selection, delegation dry-run behavior, PR reconciliation, lifecycle label transitions, planner skip-in-progress logic, and new operator control validation**.

---

## Machine-Readable Companion Files (Charter §15)

The implementation charter (§15) requires machine-readable policy files that encode mutation lanes, dependency contracts, and architectural invariants. These files live alongside the OPERATOR_GUIDE:

| File | Charter ref | Contents |
|---|---|---|
| [`policy.json`](policy.json) | §15 | Operating modes, canonical entrypoint, protected paths, priority order (§14), agent instruction contract (§16), architectural invariants |
| [`mutation_lanes.json`](mutation_lanes.json) | §10, §11 | All 10 charter-defined lanes with purpose, constraints, automation status, preferred methods, validation floor, and mutation budget policy |
| [`dependency_contract.json`](dependency_contract.json) | §6 | Layer order, allowed dependency direction, hard prohibitions, circular import policy, ownership hints |

Agents should consume these files before proposing code changes. The constants `CHARTER_COMPANION_FILES`, `CHARTER_PRIORITY_ORDER`, and `AGENT_INSTRUCTION_CONTRACT` in `repo_architect.py` encode the same data as Python tuples for runtime use.

