# repo-architect Operator Guide

## Operating Model

`repo_architect.py` is an **architectural governance** tool that inspects the repository, diagnoses structural and operational gaps, and opens structured GitHub Issues containing Copilot-ready implementation prompts.

### Default safe mode: issue-first governance

```
inspect repo → identify architectural gap → deduplicate against existing issues
    → open/update GitHub Issue → attach Copilot prompt → report outcome
```

The GitHub Issue becomes the mutation surface. Copilot or a human becomes the code author. CI validates the resulting implementation PRs.

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
| `analyze` | Build analysis and write `.agent/` artifacts. No GitHub API calls. | §20 Automation Policy | Read-only |
| `report` | Refresh `docs/repo_architect/` documentation reports. | Lane 0 (Report generation) | Read-only |
| `mutate` | Attempt one direct code mutation via charter-validated lanes. | §9–§10 Self-Modification Contract, Lanes 0–4 | Opt-in |
| `campaign` | Run multiple mutation slices across lanes. | §9–§11 Self-Modification Contract, Mutation Budget | Opt-in |

The default mode (both CLI and scheduled workflow) is `issue`.

---

## Issue Mode

### What it does

1. Builds repository analysis (parse errors, import cycles, entrypoints, architecture score).
2. Calls GitHub Models for an architectural risk summary (if credentials are available).
3. Diagnoses concrete architectural gaps from the analysis.
4. Deduplicates: searches existing open issues for each gap using a deterministic fingerprint.
5. Creates a new GitHub Issue (or updates an existing one with a comment).
6. Emits a structured JSON result and workflow step summary.

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
| `--mode issue` | `issue` | Operating mode (issue/mutate/campaign/report/analyze) |
| `--dry-run` | `false` | Write issue bodies to disk only |
| `--max-issues N` | `1` | Maximum issues to open/update per run |
| `--issue-subsystem X` | all | Restrict to one subsystem |
| `--allow-dirty` | `false` | Skip dirty-worktree check |

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

---

## Labels and Lifecycle

### Base labels (always applied)

- `arch-gap` — identifies this as an architecture governance issue
- `copilot-task` — ready for Copilot to implement
- `needs-implementation` — awaiting a code PR

### Subsystem labels (where applicable)

`workflow`, `runtime`, `reporting`, `docs`, `model-routing`, `issue-orchestration`, `core`, `knowledge`, `agents`, `consciousness`

### Priority labels (critical and high only)

`priority:critical`, `priority:high`

### Lifecycle labels (manually applied by maintainers)

- `ready-for-validation` — implementation PR exists, needs CI review
- `blocked` — blocked by a dependency or decision
- `superseded` — replaced by a more comprehensive issue

---

## Dry-Run Mode

In dry-run mode (`--dry-run` flag or `dry_run: 'true'` workflow input), the system writes issue bodies to `docs/repo_architect/issues/<fingerprint>.md` instead of calling the GitHub Issues API. This is useful for:
- Local testing and preview
- CI pipelines without `issues: write` permission
- Auditing generated prompts before publishing

---

## How Copilot Consumes the Generated Prompt

1. Maintainer opens the GitHub Issue created by this workflow.
2. In the issue body, find the **Copilot implementation prompt** section.
3. Copy the entire code block.
4. Paste into **GitHub Copilot Chat** (agent mode) or the Copilot Workspace.
5. Copilot reads the referenced files, implements the fix, and opens a PR.
6. CI validates the PR against the **Validation** commands in the issue.
7. Maintainer reviews and merges.

---

## Workflow Dispatch Inputs

| Input | Default | Description |
|---|---|---|
| `mode` | `issue` | Operating mode |
| `dry_run` | `false` | Dry-run without API calls |
| `max_issues` | `1` | Max issues per run |
| `issue_subsystem` | (all) | Target subsystem |
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

### IssueAction fields

| Field | Description |
|---|---|
| `action` | `created`, `updated`, `dry_run`, or `error` |
| `issue_number` | GitHub Issue number (null for dry-run) |
| `issue_url` | GitHub Issue URL |
| `labels_applied` | Labels attached to the issue |
| `dedupe_result` | `new`, `existing_open`, or `n/a` |
| `fingerprint` | 12-char deterministic fingerprint |
| `dry_run_path` | Relative path to dry-run artifact (dry-run only) |
| `gap_title` | Issue title |
| `gap_subsystem` | Subsystem of the detected gap |

### Example output

```
created issue #12 for workflow architectural drift
updated existing issue #9 for reporting schema inconsistency
skipped creation because matching open issue exists
dry-run generated issue body at docs/repo_architect/issues/a1b2c3d4e5f6.md
```

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

The test suite covers: branch suffix generation, model fallback, `ast.parse` gate, campaign aggregation, output schema stability, lane priority, `entrypoint_consolidation`, lane scoping, `validate_change`, charter context, issue fingerprint generation, issue body rendering, deduplication behavior, label assignment, gap diagnosis, `run_issue_cycle` output schema, and charter-validated mode notices.
