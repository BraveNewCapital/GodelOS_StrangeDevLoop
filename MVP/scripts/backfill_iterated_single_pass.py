#!/usr/bin/env python3
"""Backfill script to synthesize iterated_single_pass condition for legacy runs.

For each run hierarchy:
  MVP/experiment_runs/<RUN_SLUG>/raw/prompt_*/single_pass/<uuid>/<uuid>.jsonl
we create a sibling directory under:
  MVP/experiment_runs/<RUN_SLUG>/raw/prompt_*/iterated_single_pass/<uuid>_itsp/
containing a synthetic JSONL where the single depth=1 record is copied to depths 1..MAX_DEPTH
(with stable fields) to emulate iteration without feedback.

Marks manifest with: {
  "synthetic_iterated_single_pass": true,
  "source_single_pass_run": <original run_id>
}

Usage:
  python scripts/backfill_iterated_single_pass.py --run-root MVP/experiment_runs/DeepSeek_10depth --max-depth 10

Idempotent: skips if target directory already exists.
"""
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
from datetime import datetime

def backfill(run_root: Path, max_depth: int):
    raw_root = run_root / 'raw'
    if not raw_root.exists():
        print(f"No raw directory at {raw_root}")
        return 0
    created = 0
    for prompt_dir in sorted(raw_root.glob('prompt_*')):
        sp_root = prompt_dir / 'single_pass'
        if not sp_root.exists():
            continue
        for run_dir in sp_root.iterdir():
            if not run_dir.is_dir():
                continue
            run_id = run_dir.name
            records_files = list(run_dir.glob('*.jsonl'))
            if not records_files:
                continue
            src_records = records_files[0]
            # Load single pass record line
            lines = [l.strip() for l in src_records.read_text().splitlines() if l.strip()]
            if not lines:
                continue
            try:
                base_record = json.loads(lines[0])
            except Exception:
                continue
            target_parent = prompt_dir / 'iterated_single_pass'
            target_parent.mkdir(parents=True, exist_ok=True)
            target_dir = target_parent / f"{run_id}_itsp"
            if target_dir.exists():
                # already backfilled
                continue
            target_dir.mkdir(parents=True, exist_ok=True)
            # Write synthetic manifest
            manifest_path = target_dir / 'manifest.json'
            manifest = {
                'schema_version': base_record.get('version'),
                'conditions': {
                    'mode': 'iterated_single_pass',
                    'synthetic_iterated_single_pass': True,
                    'source_single_pass_run': run_id
                },
                'created': datetime.utcnow().isoformat() + 'Z'
            }
            manifest_path.write_text(json.dumps(manifest, indent=2))
            # Construct synthetic jsonl
            out_records = target_dir / f"{run_id}_itsp.jsonl"
            with out_records.open('w', encoding='utf-8') as f:
                for depth in range(1, max_depth+1):
                    rec = dict(base_record)
                    rec['depth'] = depth
                    rec['synthetic'] = True
                    rec['notes'] = 'Synthetic iterated single-pass duplication'
                    f.write(json.dumps(rec) + '\n')
            created += 1
    return created


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-root', required=True, help='Path to existing run slug directory')
    ap.add_argument('--max-depth', type=int, required=True)
    args = ap.parse_args()
    run_root = Path(args.run_root)
    count = backfill(run_root, args.max_depth)
    print(f"Created {count} synthetic iterated_single_pass runs")

if __name__ == '__main__':
    main()
