#!/usr/bin/env python3
"""Audit (and optionally prune) recursive introspection runs.

Classification criteria:
- missing_records: No <run_id>.jsonl file present in run directory.
- empty_file: File exists but has zero valid JSON lines.
- shallow_recursive: (condition != single_pass) and <2 distinct depths.
- bad_single_pass: condition == single_pass but depths != {1}.

Usage (dry-run audit only):
  python scripts/audit_prune_runs.py --root knowledge_storage/experiments/final_comprehensive --report report.json

Prune defective runs (delete directories) after confirmation:
  python scripts/audit_prune_runs.py --root knowledge_storage/experiments/final_comprehensive --prune --confirm

Selective pruning (choose categories):
  python scripts/audit_prune_runs.py --root ... --prune --categories missing_records empty_file --confirm
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Dict, List, Set

def analyze_run(run_dir: Path, condition: str) -> Dict[str, any]:
    run_id = run_dir.name
    record_file = run_dir / f"{run_id}.jsonl"
    status: Dict[str, any] = {"run_id": run_id, "condition": condition, "path": str(run_dir)}
    if not record_file.exists():
        status["issues"] = ["missing_records"]
        status["depths"] = []
        return status
    depths: Set[int] = set()
    valid_lines = 0
    try:
        with record_file.open() as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                valid_lines += 1
                if isinstance(obj, dict) and 'depth' in obj:
                    d = obj['depth']
                    if isinstance(d, int):
                        depths.add(d)
    except Exception:
        status["issues"] = ["read_error"]
        status["depths"] = []
        return status
    issues: List[str] = []
    if valid_lines == 0:
        issues.append("empty_file")
    if condition != 'single_pass':
        if len(depths) < 2:
            issues.append("shallow_recursive")
    else:
        if depths != {1}:
            issues.append("bad_single_pass")
    status["issues"] = issues
    status["depths"] = sorted(depths)
    status["valid_lines"] = valid_lines
    return status

def scan_root(root: Path) -> Dict[str, List[Dict[str, any]]]:
    results: Dict[str, List[Dict[str, any]]] = {}
    for prompt_dir in root.glob('prompt_*'):
        if not prompt_dir.is_dir():
            continue
        for condition_dir in prompt_dir.iterdir():
            if not condition_dir.is_dir():
                continue
            condition = condition_dir.name
            for run_dir in condition_dir.iterdir():
                if run_dir.is_dir():
                    res = analyze_run(run_dir, condition)
                    results.setdefault(condition, []).append(res)
    return results

def summarize(results: Dict[str, List[Dict[str, any]]]) -> Dict[str, any]:
    summary = {"conditions": {}, "totals": {"runs": 0, "issues": {}}}
    total_runs = 0
    issue_counts = {}
    for condition, runs in results.items():
        total_runs += len(runs)
        cond_issue_counts = {}
        for r in runs:
            for issue in r.get("issues", []):
                cond_issue_counts[issue] = cond_issue_counts.get(issue, 0) + 1
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        summary["conditions"][condition] = {"runs": len(runs), "issues": cond_issue_counts}
    summary["totals"]["runs"] = total_runs
    summary["totals"]["issues"] = issue_counts
    return summary

def prune(results: Dict[str, List[Dict[str, any]]], categories: Set[str]) -> List[str]:
    deleted = []
    for runs in results.values():
        for r in runs:
            if any(issue in categories for issue in r.get("issues", [])):
                path = Path(r["path"])
                try:
                    import shutil
                    shutil.rmtree(path)
                    deleted.append(str(path))
                except Exception as e:
                    print(f"Failed to delete {path}: {e}", file=sys.stderr)
    return deleted

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--report', help='Write JSON audit report to path')
    ap.add_argument('--prune', action='store_true', help='Delete runs with issues (requires --confirm)')
    ap.add_argument('--categories', nargs='*', default=['missing_records','empty_file','shallow_recursive'], help='Issue categories to prune')
    ap.add_argument('--confirm', action='store_true', help='Confirm destructive prune action')
    args = ap.parse_args()

    root = Path(args.root)
    results = scan_root(root)
    report = {"runs": results, "summary": summarize(results)}

    print("AUDIT SUMMARY:")
    print(json.dumps(report["summary"], indent=2))

    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2))
        print(f"Report written to {args.report}")

    if args.prune:
        if not args.confirm:
            print("Add --confirm to proceed with pruning.")
            return
        categories = set(args.categories)
        deleted = prune(results, categories)
        print(f"Deleted {len(deleted)} run directories.")

if __name__ == '__main__':
    main()
