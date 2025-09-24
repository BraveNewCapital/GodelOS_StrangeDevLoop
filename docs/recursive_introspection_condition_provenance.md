# Recursive Introspection Condition Provenance

## Overview
Accurate condition attribution is essential for valid statistical comparisons across recursive introspection experiments. An earlier issue caused all runs to appear under a single `unknown` condition in aggregated statistical output because manifests stored the key `condition` while the analysis loader expected `mode`.

This document records the provenance design, fixes applied, and rerun/backfill procedures.

## Schema Enhancements
- `IntrospectionRecord` now includes optional fields:
  - `condition: Optional[str]`
  - `prompt_variant: Optional[str]`
  - `run_number: Optional[int]`
- `build_record` accepts these fields; `llm_client` injects them using values passed via `introspection_state` from `introspection_runner`.
- `final_comprehensive_experiment.py` supplies both `mode` and `condition` in the manifest conditions block for forward & backward compatibility.

## Analysis Loader Robustness
`load_experiment_data` now resolves condition via ordered fallback:
1. `mode`
2. `condition`
3. `variant`
4. `prompt_variant`
5. default `unknown`

## Backfilling Legacy Manifests
A script `scripts/backfill_condition_mode.py` adds a `mode` key mirroring existing `condition` when absent.

Dry run example:
```bash
cd MVP
source mvp_venv/bin/activate
python scripts/backfill_condition_mode.py --dry-run
```
Apply changes:
```bash
python scripts/backfill_condition_mode.py
```

## Minimal Sanity Rerun
To verify condition propagation end-to-end:
```bash
cd MVP
source mvp_venv/bin/activate
python - <<'PY'
import asyncio, json
from final_comprehensive_experiment import ComprehensiveExperimentRunner, FINAL_EXPERIMENT_CONFIG
from pathlib import Path
cfg = dict(FINAL_EXPERIMENT_CONFIG)
cfg['base_prompts'] = cfg['base_prompts'][:1]
cfg['conditions'] = ['recursive','single_pass']
cfg['runs_per_condition_per_prompt'] = 1
cfg['max_depth'] = 2
runner = ComprehensiveExperimentRunner(cfg)
async def main():
    await runner.execute_comprehensive_experiments()
    await runner.run_comprehensive_statistical_analysis()
    comp = Path('knowledge_storage/experiments/final_comprehensive/comprehensive_statistical_analysis.json')
    data = json.loads(comp.read_text())
    print('Conditions analyzed:', data['individual_analyses']['prompt_1']['conditions_analyzed'])
asyncio.run(main())
PY
```
Expected output contains both `recursive` and `single_pass`.

## Full Experiment Rerun
When ready to reproduce the 72-run full experiment after validation:
```bash
cd MVP
source mvp_venv/bin/activate
python final_comprehensive_experiment.py
```
Artifacts will appear under `knowledge_storage/experiments/final_comprehensive/`.

## Post-Rerun Integrity Checklist
1. `comprehensive_statistical_analysis.json` lists all expected conditions per prompt.
2. Each `manifest.json` includes both `condition` and `mode`.
3. Individual record lines (`*.jsonl`) include `condition` field (spot-check with `grep -m1 '"condition"'`).
4. `significance_tests` sections are populated (not empty lists) after enough data.
5. Effect size values reproducible from raw descriptive stats.

## Troubleshooting
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Conditions still show `unknown` | Backfill script not run; old manifests reused | Run backfill, delete stale analysis JSON, re-run analysis |
| Records missing `condition` | Old runs before schema change | Regenerate runs after fix |
| Empty significance tests | Insufficient samples per condition/depth | Ensure each condition has >=3 runs with records per depth |

## Provenance Commit Notes
- Added fields in `cognitive_metrics.py`
- Updated `introspection_runner.py` to seed introspection_state with provenance
- Updated `llm_client.py` to pass provenance into `build_record`
- Patched `final_comprehensive_experiment.py` to include `mode`
- Hardened `statistical_analysis.load_experiment_data`
- Added backfill script & this documentation.
- Introduced hierarchical run layout: `knowledge_storage/experiments/final_comprehensive/prompt_<n>/<condition>/<run_uuid>/`.
- Added per-prompt visualization exports under `visualizations/prompt_<n>/`.
- Statistical summary now includes `raw_values` (per-depth raw metric arrays).
- Added validation script: `scripts/validate_recursive_dataset.py`.

## Next Recommendations
- Store raw per-depth metric arrays in a dedicated `raw_metrics` block of the summary for audit.
- Add a validation script that asserts non-empty condition sets before effect size computation.
- Incorporate a version tag for provenance schema (e.g., `provenance_version`).
- Integrate validator into CI to fail if conditions collapse or raw_values missing.

---
Maintainer: Recursive Introspection Pipeline
Date: 2025-09-20
