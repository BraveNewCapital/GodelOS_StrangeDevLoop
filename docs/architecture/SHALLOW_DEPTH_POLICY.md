# Shallow Depth Policy for Recursive Introspection Runs

## Purpose
Ensure consistency, interpretability, and statistical comparability across recursive introspection experiment runs by defining thresholds and remediation actions for *shallow* runs (those that terminate before reaching an expected recursion depth).

## Key Definitions
- Observed Depths: Unique `depth` values found in a run's records JSONL.
- Max Observed Depth: Highest numeric depth value in the run.
- Configured Max Depth: The theoretical upper limit passed to the experiment runner (currently 6).
- Minimum Required Depth (`--min-depth`): Policy threshold for acceptable recursion completeness.
- Critical Depth Threshold (`--critical-depth-threshold`): Depth below which a run is considered *structurally invalid* (likely aborted or failed early).

## Severity Mapping
| Condition | Criteria | Severity |
|-----------|----------|----------|
| Missing manifest / records | File absent or unreadable | critical |
| Condition mismatch | Manifest condition != folder | critical |
| Max depth observed < critical threshold | `max_observed < critical_depth_threshold` | critical |
| Insufficient coverage ( <2 depths ) | Recursive mode but only one (or zero) depth | warning |
| Shallow run | `critical_depth_threshold <= max_observed < min_depth` | warning |
| Did not reach configured max depth | Missing only the top depth but otherwise progressing | info |

## Recommended Default Thresholds
- `--max-depth 6`
- `--min-depth 5` (require at least depth 5 observed)
- `--critical-depth-threshold 3` (depth 1–2 indicates probable early termination)

## Rationale
- Depths 1–2 often reflect initialization and first expansion only; lacking deeper reflective phases.
- Depth 5 presence correlates with stable cross-prompt variance reduction in prior analyses.
- Missing only depth 6 typically reflects benign early stopping; treated as informational.

## Enforcement Workflow
1. Run validator with depth policy:
   ```bash
   python MVP/scripts/validate_recursive_dataset.py \
     --root knowledge_storage/experiments/final_comprehensive \
     --expected-conditions recursive single_pass shuffled_recursive \
     --max-depth 6 --enforce-depth --min-depth 5 --critical-depth-threshold 3 \
     --json-report MVP/validation_report_with_depth_policy.json \
     --shallow-report MVP/shallow_runs.json
   ```
2. Inspect JSON reports:
   - `validation_report_with_depth_policy.json` → consolidated severities
   - `shallow_runs.json` → structured entries for each shallow or critical shallow run
3. Remediate:
   - Critical shallow runs: Remove and re-run (or quarantine) before statistical aggregation.
   - Warning shallow runs: Optionally re-run if they materially bias a condition (e.g., >20% of runs). Otherwise retain but annotate.
4. Recompute analysis-only wrapper after any removals.

## Automation Suggestions
- Integrate validator in CI: fail pipeline if `critical > 0`.
- Add optional rerun script that ingests `shallow_runs.json` and triggers only affected prompts/conditions.

## Data Provenance Considerations
- Never mutate surviving run directories; instead prune entire shallow run directory if re-running.
- Tag repository (git annotated tag) after any batch of remedial reruns for reproducibility lineage.

## Future Extensions
- Depth distribution entropy metric (flag anomalously narrow distributions even if max depth OK).
- Adaptive min-depth: dynamically calculated as median(max_observed) - 1.
- Visualization overlay comparing shallow vs full-depth contribution to aggregate metrics.

## Summary
This policy formalizes shallow-depth detection, distinguishes harmless incomplete-top-depth cases (info) from structurally compromised runs (critical), and provides a reproducible remediation path without forcing uniform hard stops that may reduce ecological validity.

## Run Directory Layout (Updated)
Each new comprehensive experiment invocation now writes to a slugged run directory under `MVP/experiment_runs/`:

```
MVP/experiment_runs/<RUN_SLUG>/
   run_metadata.json              # Provenance (model, depth, hashes, git commit)
   ENV_SNAPSHOT.txt               # Non-secret env snapshot (MODEL, BASE_URL)
   raw/                           # prompt_<n>/<condition>/<uuid>/ records
   statistical_analysis_prompt_*.json
   comprehensive_statistical_analysis.json
   publication_summary.json
   FINAL_EXPERIMENT_REPORT.md
   visualizations/
```

Legacy root path `knowledge_storage/experiments/final_comprehensive` is migrated via `MVP/scripts/migrate_experiment_layout.py` and should no longer receive new writes. Validators can target `<RUN_SLUG>/raw` or be enhanced to auto-detect when given the run slug root.
