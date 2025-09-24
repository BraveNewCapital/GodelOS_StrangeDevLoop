#!/usr/bin/env python3
"""Migrate legacy flat run directories into hierarchical prompt/condition layout.

Assumptions:
- Flat directories live under knowledge_storage/experiments/final_comprehensive and are UUID named.
- Each contains manifest.json whose conditions include at least one of keys: mode/condition/prompt_variant.
- Target layout: prompt_<variant>/<condition>/<run_id>/ preserving existing files.

Usage:
  python scripts/migrate_flat_runs.py --root knowledge_storage/experiments/final_comprehensive --dry-run
"""
from __future__ import annotations
import argparse, json, shutil, re
from pathlib import Path

UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")

def load_manifest(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None

def migrate_run(run_dir: Path, root: Path, dry: bool):
    manifest_path = run_dir / 'manifest.json'
    if not manifest_path.exists():
        return False, 'no_manifest'
    manifest = load_manifest(manifest_path)
    if not manifest:
        return False, 'bad_manifest'
    conds = manifest.get('conditions', {})
    condition = conds.get('mode') or conds.get('condition') or 'unknown'
    prompt_variant = conds.get('prompt_variant') or 'prompt_legacy'
    target = root / prompt_variant / condition / run_dir.name
    if target.exists():
        return False, 'target_exists'
    if dry:
        print(f"[DRY] {run_dir} -> {target}")
        return True, 'ok'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(run_dir), str(target))
    return True, 'migrated'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    root = Path(args.root)
    moved = 0
    skipped = 0
    for item in list(root.iterdir()):
        if item.is_dir() and UUID_RE.match(item.name):
            ok, msg = migrate_run(item, root, args.dry_run)
            if ok:
                moved += 1
            else:
                skipped += 1
    print(f"Completed. moved={moved} skipped={skipped}")

if __name__ == '__main__':
    main()
