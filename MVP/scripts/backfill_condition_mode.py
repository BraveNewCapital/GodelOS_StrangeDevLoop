#!/usr/bin/env python3
"""Backfill 'mode' key into manifests that only contain 'condition'.

Scans experiment directories (default: knowledge_storage/experiments/final_comprehensive) and any
run directories under data/recursive_runs for manifest.json files. If a manifest's
conditions block lacks 'mode' but has 'condition', inserts mode=condition and rewrites file.

Dry-run supported via --dry-run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TARGET_DIRS = [
    Path("knowledge_storage/experiments/final_comprehensive"),
    Path("data/recursive_runs"),
]

def process_manifest(path: Path, dry_run: bool = True) -> bool:
    try:
        data = json.loads(path.read_text())
    except Exception:
        return False
    if not isinstance(data, dict) or "conditions" not in data:
        return False
    conds = data["conditions"]
    if not isinstance(conds, dict):
        return False
    if "mode" in conds:
        return False  # already has mode
    if "condition" not in conds:
        return False
    conds["mode"] = conds["condition"]
    if dry_run:
        print(f"[DRY] Would add mode={conds['mode']} to {path}")
        return True
    path.write_text(json.dumps(data, indent=2))
    print(f"[FIXED] Added mode={conds['mode']} in {path}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    ap.add_argument("--root", action="append", help="Additional root directories to scan")
    args = ap.parse_args()

    dirs = TARGET_DIRS[:]
    if args.root:
        dirs.extend(Path(p) for p in args.root)

    total = 0
    fixed = 0
    for base in dirs:
        if not base.exists():
            continue
        for path in base.rglob("manifest.json"):
            total += 1
            if process_manifest(path, dry_run=args.dry_run):
                fixed += 1
    print(f"Processed {total} manifests; {'would fix' if args.dry_run else 'fixed'} {fixed} lacking 'mode'.")

if __name__ == "__main__":
    main()
