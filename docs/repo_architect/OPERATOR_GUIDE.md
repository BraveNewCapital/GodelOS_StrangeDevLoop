# repo-architect Operator Guide

## Operating Model

`repo_architect.py` is an **architectural governance** tool that inspects the repository, diagnoses structural and operational gaps, and opens structured GitHub Issues containing Copilot-ready implementation prompts.

**The system is now an architectural governor. It must not write code, create branches, or open code PRs.**

### New operating model

```
inspect repo → identify architectural gap → deduplicate against existing issues
    → open/update GitHub Issue → attach Copilot prompt → report outcome
```

The GitHub Issue becomes the mutation surface. Copilot or a human becomes the code author. CI validates the resulting implementation PRs.

### Deprecated model (disabled by default)

```
inspect repo → generate code diff → create branch → open PR → repeat
```

This model is deprecated. Modes `mutate` and `campaign` still function for backward compatibility but emit a runtime deprecation warning and are no longer the default or primary path.

---

## Modes

| Mode | Description | Recommended |
|---|---|---|
| `issue` | **Primary mode.** Detects architectural gaps and opens/updates GitHub Issues with Copilot-ready prompts. | ✅ Yes |
| `analyze` | Build analysis and write `.agent/` artifacts. No GitHub API calls. | ✅ Yes (read-only) |
| `report` | Refresh `docs/repo_architect/` documentation reports. | ✅ Yes (read-only) |
| `mutate` | **DEPRECATED.** Attempt one direct code mutation. Emits runtime warning. | ⚠️ Deprecated |
| `campaign` | **DEPRECATED.** Run multiple mutation slices. Emits runtime warning. | ⚠️ Deprecated |

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
| `--mode issue` | required | Enable issue-first mode |
| `--dry-run` | `false` | Write issue bodies to disk only |
| `--max-issues N` | `1` | Maximum issues to open/update per run |
| `--issue-subsystem X` | all | Restrict to one subsystem |
| `--allow-dirty` | `false` | Skip dirty-worktree check |

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

| Gap | Subsystem | Priority |
|---|---|---|
| Python parse errors | `runtime` | `critical` |
| Import cycles | `runtime` | `high` |
| Entrypoint fragmentation (≥4 backend entrypoints) | `runtime` | `medium` |
| Architecture score < 70/100 | `reporting` | `high` / `medium` |
| Workflow / documentation drift (model-assisted) | `workflow` | `medium` |

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

`workflow`, `runtime`, `reporting`, `docs`, `model-routing`, `issue-orchestration`

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
| `mutation_budget` | `1` | [DEPRECATED] mutation budget |
| `max_slices` | `3` | [DEPRECATED] campaign slices |
| `lanes` | all lanes | [DEPRECATED] lane order |

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

The test suite covers: branch suffix generation, model fallback, `ast.parse` gate, campaign aggregation, output schema stability, lane priority, `entrypoint_consolidation`, lane scoping, `validate_change`, charter context, issue fingerprint generation, issue body rendering, deduplication behavior, label assignment, gap diagnosis, `run_issue_cycle` output schema, and deprecated mode warnings.

---

## Deprecated: Mutation Modes

The `mutate` and `campaign` modes are preserved for backward compatibility but emit a runtime warning:

```
⚠️  DEPRECATED: mode 'mutate' performs direct code mutation which is no longer
the primary operating model.  Use --mode issue to open structured GitHub Issues
with Copilot-ready implementation prompts instead.
```

If you need to continue using mutation modes temporarily, pass `--mode mutate` or `--mode campaign` explicitly. These modes will not be removed immediately, but will be gated behind an explicit opt-in in a future release.
