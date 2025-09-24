#!/usr/bin/env python3
"""Migrate legacy experiment layout to new slugged run directory schema.

Legacy source (repo root): knowledge_storage/experiments/final_comprehensive
Target root (default): MVP/experiment_runs/<slug>/

Slug pattern: MIGRATED_<timestamp>

Actions:
 1. Verify legacy path exists & not already migrated.
 2. Create target slug dir with required substructure; move legacy prompt_* dirs under raw/.
 3. Move analysis & visualization artifacts if present.
 4. Write run_metadata.json with migrated_legacy=True.
 5. Leave a symlink or MIGRATION_NOTE.txt at old location (optional) then remove old directory.

Usage:
  python MVP/scripts/migrate_experiment_layout.py \
      --legacy-root knowledge_storage/experiments/final_comprehensive \
      --output-root MVP/experiment_runs
"""
from __future__ import annotations
import argparse, json, shutil, time, hashlib, os
from pathlib import Path

REQUIRED_TOP = ['comprehensive_statistical_analysis.json', 'publication_summary.json', 'FINAL_EXPERIMENT_REPORT.md']

def build_slug():
    return f"MIGRATED_{time.strftime('%Y%m%d_%H%M%S')}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--legacy-root', default='knowledge_storage/experiments/final_comprehensive')
    ap.add_argument('--output-root', default='MVP/experiment_runs')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    legacy = Path(args.legacy_root)
    if not legacy.exists():
        print('Legacy path not found; nothing to migrate.')
        return 0

    # Heuristic: ensure we see at least one prompt_* or statistical file
    prompt_dirs = list(legacy.glob('prompt_*'))
    if not prompt_dirs:
        print('No prompt_* directories found in legacy path; aborting.')
        return 1

    out_root = Path(args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    slug = build_slug()
    run_dir = out_root / slug
    if run_dir.exists():
        print(f'Target run directory already exists: {run_dir}')
        return 1
    if args.dry_run:
        print(f"[DRY-RUN] Would migrate {legacy} -> {run_dir}")
        return 0

    run_dir.mkdir()
    raw_dir = run_dir / 'raw'
    raw_dir.mkdir()
    (run_dir / 'visualizations').mkdir()

    # Move prompt_* directories under raw/
    for p in prompt_dirs:
        shutil.move(str(p), str(raw_dir / p.name))

    # Move visualization directory if present
    viz = legacy / 'visualizations'
    if viz.exists():
        for item in viz.iterdir():
            shutil.move(str(item), str(run_dir / 'visualizations' / item.name))
        try:
            viz.rmdir()
        except Exception:
            pass

    # Move top-level known files
    for fname in REQUIRED_TOP:
        src = legacy / fname
        if src.exists():
            shutil.move(str(src), str(run_dir / fname))

    # Collect run metadata summary
    metadata = {
        'run_slug': slug,
        'migrated_legacy': True,
        'timestamp_migrated': time.time(),
        'legacy_source': str(legacy.resolve()),
        'prompts_count': len(prompt_dirs),
    }
    # Hash prompt text concatenation if manifests available
    all_prompts = []
    for pdir in (raw_dir).glob('prompt_*'):
        # Look for one manifest inside first condition dir
        for cdir in pdir.iterdir():
            if cdir.is_dir():
                # pick a manifest from first run
                for run in cdir.iterdir():
                    man = run / 'manifest.json'
                    if man.exists():
                        try:
                            m = json.loads(man.read_text())
                            base_prompt = m.get('base_prompt') or m.get('prompt')
                            if base_prompt:
                                all_prompts.append(base_prompt)
                        except Exception:
                            pass
                    break
            break
    if all_prompts:
        metadata['prompts_hash'] = hashlib.sha256('\n'.join(all_prompts).encode()).hexdigest()[:16]

    (run_dir / 'run_metadata.json').write_text(json.dumps(metadata, indent=2))

    # Create migration note
    (legacy / 'MIGRATION_NOTE.txt').write_text(f'Migrated to {run_dir}\n')

    # Remove legacy directory if empty
    try:
        # attempt to remove leftover files (only MIGRATION_NOTE expected)
        for item in legacy.iterdir():
            if item.name != 'MIGRATION_NOTE.txt':
                print(f'Leaving residual item: {item}')
                break
        else:
            # only note exists
            (legacy / 'MIGRATION_NOTE.txt').unlink()
            legacy.rmdir()
    except Exception:
        pass

    print(f'Migration complete -> {run_dir}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
