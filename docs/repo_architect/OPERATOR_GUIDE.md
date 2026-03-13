# repo-architect Operator Guide

## Overview

`repo_architect.py` is a single-file autonomous agent that:
- Analyses the Python codebase for parse errors, import cycles, entrypoints, and hygiene issues.
- Generates or refreshes architecture documentation under `docs/repo_architect/`.
- Creates mutation branches and pull-requests that fix real code issues.
- Can run repeatedly without branch collisions or stale-branch failures.

---

## Model Selection (preferred / fallback)

The agent tries a **preferred** model first and automatically retries with a **fallback** model when the preferred one is unavailable or returns an unknown-model error.

| Priority | Source |
|---|---|
| 1 | `--preferred-model` CLI flag |
| 2 | `REPO_ARCHITECT_PREFERRED_MODEL` env var |
| 3 | Hard-coded default (`openai/gpt-5.4`) |

| Fallback priority | Source |
|---|---|
| 1 | `--fallback-model` CLI flag |
| 2 | `REPO_ARCHITECT_FALLBACK_MODEL` env var |
| 3 | Hard-coded default (`openai/gpt-4.1`) |

**Failure tolerance:** if both model calls fail (network, quota, unavailability), the run continues without model-generated output instead of aborting. The JSON result records `fallback_reason` and `fallback_occurred`.

The workflow exports:
```yaml
REPO_ARCHITECT_PREFERRED_MODEL: openai/gpt-5.4
REPO_ARCHITECT_FALLBACK_MODEL: openai/gpt-4.1
```

---

## Unique Branch Strategy

Every mutation branch is suffixed with a per-run unique token to prevent branch-push collisions.

**Suffix precedence:**
1. `REPO_ARCHITECT_BRANCH_SUFFIX` env var (if set and non-empty)
2. `GITHUB_RUN_ID-GITHUB_RUN_ATTEMPT` (when both are present)
3. UTC timestamp fallback (`YYYYmmddHHMMSS`)

The suffix is sanitised to `[A-Za-z0-9._-]` only.

**Push collision recovery:** Before pushing, the agent checks whether the remote branch already exists. If it does, a fresh unique branch name is generated. A single retry is also performed if the push is rejected due to a non-fast-forward error.

The workflow exports:
```yaml
REPO_ARCHITECT_BRANCH_SUFFIX: ${{ github.run_id }}-${{ github.run_attempt }}
```

---

## Lane Priority Rules

In `mutate` and `campaign` modes the agent selects exactly one lane per slice, in this priority order:

| Priority | Lane | Behaviour |
|---|---|---|
| 1 | `parse_errors` | Model-assisted syntax fix for one or more files with parse errors. Skipped if no parse errors exist or model is unavailable. |
| 2 | `import_cycles` | Model-assisted import cycle break (TYPE_CHECKING guard / lazy import). Skipped if no cycles or model unavailable. |
| 3 | `entrypoint_consolidation` | Annotates one redundant backend server entrypoint with a `# DEPRECATED` comment when ≥ 4 backend entrypoints exist. Model-assisted. |
| 4 | `hygiene` | Remove explicitly `# DEBUG`-marked `print()` statements. No model required. |
| 5 | `report` | Refresh the architecture documentation packet. Only selected when no higher-priority code mutation is possible. |

A **report-only mutation is never produced when parse errors exist** unless all code-lane attempts fail (in which case `no_safe_code_mutation_reason` is populated in the JSON output).

---

## Campaign Mode

Campaign mode executes up to `--max-slices` mutation slices across the lane priority order, re-analysing between each slice so later lanes see the updated repository state.

```bash
python repo_architect.py \
  --mode campaign \
  --allow-dirty \
  --max-slices 3 \
  --lanes parse_errors,import_cycles,entrypoint_consolidation,hygiene,report \
  --stop-on-failure
```

**CLI flags:**

| Flag | Default | Description |
|---|---|---|
| `--max-slices` | `3` | Maximum slices to attempt |
| `--lanes` | `parse_errors,import_cycles,hygiene,report` | Comma-separated lane order |
| `--stop-on-failure` | `false` | Abort remaining slices on first failure |
| `--preferred-model` | (env / default) | Override preferred model for this run |
| `--fallback-model` | (env / default) | Override fallback model for this run |

Campaign results are emitted as `status: campaign_complete` JSON and also saved to `.agent/campaign_summary.json`.

---

## Output Contract (machine-readable JSON)

Every run emits a JSON object on stdout. Key fields:

| Field | Description |
|---|---|
| `status` | `analyzed`, `analysis_only`, `mutated`, `no_meaningful_delta`, `no_safe_mutation_available`, `campaign_complete` |
| `mode` | Active mode |
| `lane` | Selected mutation lane (`none` if no mutation) |
| `architecture_score` | 1–100 composite health score |
| `requested_model` | Model that was requested |
| `actual_model` | Model that actually responded (may differ if fallback occurred) |
| `fallback_reason` | Reason fallback was triggered (or `null`) |
| `fallback_occurred` | `true` if the fallback model was used |
| `no_safe_code_mutation_reason` | Explanation when no code-level mutation was safe |
| `branch` | Git branch name pushed (or `null`) |
| `changed_files` | List of files modified |
| `validation` | Output from `py_compile` or equivalent validation |
| `artifact_files` | All artifact paths generated in this run |
| `pull_request_url` | PR URL if created |

---

## Workflow Dispatch Modes

| Mode | Effect |
|---|---|
| `analyze` | Builds analysis, writes `.agent/` artifacts, no branch or PR |
| `report` | Refreshes `docs/repo_architect/` documentation |
| `mutate` | Attempts one code or report mutation in lane-priority order |
| `campaign` | Runs up to `max_slices` slices serially across lanes |

---

## Validation Policy

Each mutation lane runs the following validation before pushing:

| Lane | Validation |
|---|---|
| `parse_errors` | `ast.parse` on model-generated content; file must parse cleanly or it is rejected |
| `import_cycles` | `ast.parse` on model-generated content; unchanged files are not validated |
| `entrypoint_consolidation` | `ast.parse` on model-generated content |
| `hygiene` | `python -m py_compile` on all touched Python files |
| `report` | Verify report files were written; hash included in output |

Validation failures abort the mutation and **never push a broken branch**.

---

## Running Tests

```bash
python -m unittest tests.test_repo_architect -v
```

The test suite covers: branch suffix generation, model fallback, `ast.parse` gate, campaign aggregation, output schema stability, lane priority selection, and `entrypoint_consolidation` threshold/validation logic.
