#!/usr/bin/env python3
"""Validate recursive introspection dataset integrity.

Checks:
- Directory hierarchy (prompt_<n>/<condition>/<run_id>)
- Each manifest has mode & condition & matching folder condition
- Each run has at least one record line per depth (for recursive-like conditions)
- Statistical summary raw_values present for recent analysis file

Usage:
  python scripts/validate_recursive_dataset.py --root knowledge_storage/experiments/final_comprehensive \
      --expected-conditions recursive single_pass shuffled_recursive --min-runs 3 --max-depth 6
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

# Depth policy configuration (can also be overridden via CLI flags):
# - min_depth: minimal depth value that must appear for recursive conditions
# - critical_depth_threshold: if max depth observed < this value, escalate to critical
#   (Use this when very shallow runs indicate likely aborted recursion.)
# CLI flags allow customizing these without editing the file.

def load_manifest(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None

def validate_run_dir(run_dir: Path, condition: str, max_depth: int, warnings: list, *,
                     min_depth_required: int | None = None,
                     enforce_depth: bool = False,
                     shallow_runs: list | None = None,
                     critical_depth_threshold: int | None = None):
    manifest_path = run_dir / 'manifest.json'
    if not manifest_path.exists():
        warnings.append(f"Missing manifest: {run_dir}")
        return
    manifest = load_manifest(manifest_path)
    if not manifest:
        warnings.append(f"Malformed manifest: {manifest_path}")
        return
    conds = manifest.get('conditions', {})
    if conds.get('condition') != condition or conds.get('mode') != condition:
        warnings.append(f"Condition mismatch in manifest {manifest_path}: {conds}")
    # Check records file
    jsonl_candidates = list(run_dir.glob('*.jsonl'))
    if not jsonl_candidates:
        warnings.append(f"No records file in {run_dir}")
        return
    records_path = jsonl_candidates[0]
    depths_seen = set()
    with records_path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if 'depth' in obj:
                depths_seen.add(obj['depth'])
    if condition != 'single_pass':
        if len(depths_seen) < 2:
            warnings.append(f"Insufficient depth coverage in {records_path}: {sorted(depths_seen)}")
        # Policy enforcement: ensure at least min_depth_required is present
        if enforce_depth and min_depth_required is not None:
            # Evaluate max observed depth
            max_observed = max(depths_seen) if depths_seen else 0
            if max_observed < min_depth_required:
                # Record a structured shallow depth warning (will be reclassified later)
                msg = (f"Shallow run (max_depth_observed={max_observed} < required_min_depth={min_depth_required}) "
                       f"in {records_path}")
                warnings.append(msg)
                if shallow_runs is not None:
                    shallow_runs.append({
                        "run_dir": str(run_dir),
                        "records_file": str(records_path),
                        "depths": sorted(depths_seen),
                        "max_observed": max_observed,
                        "required_min_depth": min_depth_required
                    })
            # Additional critical escalation if critical_depth_threshold set
            if critical_depth_threshold is not None and (max_observed < critical_depth_threshold):
                msg = (f"Critical shallow run (max_depth_observed={max_observed} < critical_depth_threshold={critical_depth_threshold}) "
                       f"in {records_path}")
                warnings.append(msg)
                if shallow_runs is not None:
                    shallow_runs.append({
                        "run_dir": str(run_dir),
                        "records_file": str(records_path),
                        "depths": sorted(depths_seen),
                        "max_observed": max_observed,
                        "critical_depth_threshold": critical_depth_threshold,
                        "required_min_depth": min_depth_required
                    })
        if max_depth in range(2, max_depth+1) and max_depth not in depths_seen:
            # soft info if near-complete but missing absolute max
            warnings.append(f"Max depth {max_depth} not reached in {records_path}")
    else:
        if depths_seen != {1}:
            warnings.append(f"Single pass run has unexpected depths {sorted(depths_seen)} in {records_path}")

def classify_warning(msg: str) -> str:
    """Assign a severity level to a warning string.
    Returns: critical | warning | info
    """
    if 'Malformed manifest' in msg or 'Missing manifest' in msg:
        return 'critical'
    if 'No records file' in msg:
        return 'critical'
    if 'Condition mismatch' in msg:
        return 'critical'
    if 'Critical shallow run' in msg:
        return 'critical'
    if 'Shallow run' in msg:
        return 'warning'
    if 'Insufficient depth coverage' in msg:
        return 'warning'
    if 'Max depth' in msg:
        return 'info'
    if 'Analysis missing raw_values' in msg:
        return 'warning'
    if 'Summary JSON not found' in msg:
        return 'warning'
    if 'schema mismatch' in msg:
        return 'warning'
    return 'info'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--expected-conditions', nargs='+', required=True)
    ap.add_argument('--min-runs', type=int, default=3)
    ap.add_argument('--max-depth', type=int, default=6)
    ap.add_argument('--summary', default='comprehensive_statistical_analysis.json')
    # Depth policy arguments
    ap.add_argument('--enforce-depth', action='store_true', help='Turn on depth policy enforcement')
    ap.add_argument('--min-depth', type=int, default=None, help='Minimum acceptable observed max depth for recursive runs')
    ap.add_argument('--critical-depth-threshold', type=int, default=None, help='Depth below which a run is escalated to critical')
    ap.add_argument('--shallow-report', help='Optional JSON file to write detailed shallow run records')
    ap.add_argument('--json-report', help='Optional path to write structured JSON report')
    args = ap.parse_args()

    root = Path(args.root)
    warnings = []

    # Scan prompt directories
    prompt_dirs = [d for d in root.iterdir() if d.is_dir() and d.name.startswith('prompt_')]
    if not prompt_dirs:
        warnings.append('No prompt_* directories found')

    condition_run_counts = {c: 0 for c in args.expected_conditions}

    shallow_runs: list = []
    for pdir in prompt_dirs:
        for condition in args.expected_conditions:
            cdir = pdir / condition
            if not cdir.exists():
                warnings.append(f"Missing condition directory {cdir}")
                continue
            # Each subdir should contain multiple run UUID dirs
            for run_dir in cdir.iterdir():
                if run_dir.is_dir():
                    validate_run_dir(
                        run_dir,
                        condition,
                        args.max_depth,
                        warnings,
                        min_depth_required=args.min_depth,
                        enforce_depth=args.enforce_depth,
                        shallow_runs=shallow_runs,
                        critical_depth_threshold=args.critical_depth_threshold,
                    )
                    condition_run_counts[condition] += 1

    # Summary file checks
    summary_path = root / args.summary
    if summary_path.exists():
        try:
            data = json.loads(summary_path.read_text())
            if 'individual_analyses' not in data:
                warnings.append('Summary missing individual_analyses key')
            else:
                # Spot check raw_values presence in any nested analysis (if new schema used)
                for analysis in data['individual_analyses'].values():
                    if 'raw_values' not in analysis:
                        warnings.append('Analysis missing raw_values (schema mismatch)')
                        break
        except Exception:
            warnings.append('Failed to parse summary JSON')
    else:
        warnings.append('Summary JSON not found')

    # Run count thresholds
    for cond, count in condition_run_counts.items():
        if count < args.min_runs:
            warnings.append(f"Condition {cond} has only {count} run dirs (< {args.min_runs})")

    if warnings:
        structured = []
        crit = warn = info = 0
        for w in warnings:
            sev = classify_warning(w)
            if sev == 'critical':
                crit += 1
            elif sev == 'warning':
                warn += 1
            else:
                info += 1
            structured.append({"message": w, "severity": sev})
        print('VALIDATION RESULTS:')
        print(f"  Critical: {crit}  Warnings: {warn}  Info: {info}")
        for entry in structured:
            print(f" - [{entry['severity'].upper()}] {entry['message']}")
        if args.json_report:
            report_obj = {
                "results": structured,
                "counts": {"critical": crit, "warning": warn, "info": info},
                "depth_policy": {
                    "enforced": args.enforce_depth,
                    "min_depth": args.min_depth,
                    "critical_depth_threshold": args.critical_depth_threshold,
                    "shallow_runs": shallow_runs,
                },
            }
            Path(args.json_report).write_text(json.dumps(report_obj, indent=2))
            print(f"Structured report written to {args.json_report}")
        if args.shallow_report and shallow_runs:
            Path(args.shallow_report).write_text(json.dumps(shallow_runs, indent=2))
            print(f"Shallow run details written to {args.shallow_report}")
    else:
        print('Dataset validation passed with no warnings.')

if __name__ == '__main__':
    main()
