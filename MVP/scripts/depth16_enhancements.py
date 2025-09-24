#!/usr/bin/env python3
"""Generate additional depth-16 analysis artifacts:
1. Depth distribution histogram (max depth reached per run)
2. Executive summary composite panel PNG
3. Per-run depth metrics CSV
4. Delta summary JSON vs prior archived dataset if present

Usage:
  python MVP/scripts/depth16_enhancements.py \
    --root knowledge_storage/experiments/final_comprehensive \
    --out-dir knowledge_storage/experiments/final_comprehensive/visualizations \
    [--archive-dir knowledge_storage/experiments/final_comprehensive_archive_<timestamp>]

If archive dir not supplied or not found, delta summary will record 'archive_missing'.
"""
from __future__ import annotations
import argparse, json, csv
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

plt.style.use('seaborn-v0_8')

def load_runs(root: Path):
    runs = []
    for prompt_dir in sorted(root.glob('prompt_*')):
        for condition_dir in sorted(prompt_dir.iterdir()):
            if not condition_dir.is_dir():
                continue
            for run_dir in sorted(condition_dir.iterdir()):
                if not run_dir.is_dir():
                    continue
                records_file = run_dir / f"{run_dir.name}.jsonl"
                if not records_file.exists():
                    continue
                depths = []
                c_values = []
                try:
                    with records_file.open() as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            obj = json.loads(line)
                            d = obj.get('depth')
                            if d is not None:
                                depths.append(d)
                                c_values.append(obj.get('metrics', {}).get('c', None))
                    if depths:
                        runs.append({
                            'prompt': prompt_dir.name,
                            'condition': condition_dir.name,
                            'run_dir': str(run_dir),
                            'max_depth_observed': max(depths),
                            'depth_count': len(set(depths)),
                            'depths': depths,
                            'c_values': c_values
                        })
                except Exception:
                    continue
    return runs

def depth_distribution_figure(runs, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8,6))
    max_depths = [r['max_depth_observed'] for r in runs]
    ax.hist(max_depths, bins=range(min(max_depths), max(max_depths)+2), edgecolor='black', alpha=0.75)
    ax.set_xlabel('Max Depth Observed')
    ax.set_ylabel('Run Count')
    ax.set_title('Distribution of Max Depth Reached (All Runs)')
    plt.tight_layout()
    fig.savefig(out_dir / 'depth_distribution.png', dpi=300)
    plt.close(fig)

    # Per-condition overlay
    fig, ax = plt.subplots(figsize=(8,6))
    conditions = sorted(set(r['condition'] for r in runs))
    for cond in conditions:
        cond_depths = [r['max_depth_observed'] for r in runs if r['condition']==cond]
        ax.hist(cond_depths, bins=range(min(max_depths), max(max_depths)+2), alpha=0.4, label=cond)
    ax.set_xlabel('Max Depth Observed')
    ax.set_ylabel('Run Count')
    ax.set_title('Max Depth Distribution by Condition (Overlay)')
    ax.legend()
    plt.tight_layout()
    fig.savefig(out_dir / 'depth_distribution_by_condition.png', dpi=300)
    plt.close(fig)

def executive_panel(runs, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    # Build compact summary metrics
    df = pd.DataFrame([{
        'prompt': r['prompt'],
        'condition': r['condition'],
        'max_depth_observed': r['max_depth_observed'],
        'c_start': (r['c_values'][0] if r['c_values'] else None),
        'c_final': (r['c_values'][-1] if r['c_values'] else None)
    } for r in runs])
    df['c_delta'] = df['c_final'] - df['c_start']

    fig, axes = plt.subplots(2, 2, figsize=(14,10))
    fig.suptitle('Recursive Introspection Executive Summary (Depth 16)', fontsize=16, fontweight='bold')

    # Panel 1: Max depth by condition
    df.boxplot(column='max_depth_observed', by='condition', ax=axes[0,0])
    axes[0,0].set_title('Max Depth by Condition')
    axes[0,0].set_ylabel('Max Depth')

    # Panel 2: Complexity delta by condition
    df.boxplot(column='c_delta', by='condition', ax=axes[0,1])
    axes[0,1].set_title('Complexity Change (Final - Start)')
    axes[0,1].set_ylabel('Δ Complexity (c)')

    # Panel 3: Max depth distribution (strip)
    for cond in df['condition'].unique():
        subset = df[df['condition']==cond]
        x = np.full(len(subset), list(df['condition'].unique()).index(cond))
        axes[1,0].scatter(x, subset['max_depth_observed'], alpha=0.6, label=cond)
    axes[1,0].set_xticks(range(len(df['condition'].unique())))
    axes[1,0].set_xticklabels(df['condition'].unique())
    axes[1,0].set_ylabel('Max Depth')
    axes[1,0].set_title('Per-Run Max Depth Scatter')

    # Panel 4: Complexity delta distribution histogram
    axes[1,1].hist(df['c_delta'].dropna(), bins=15, edgecolor='black', alpha=0.7)
    axes[1,1].set_xlabel('Δ Complexity (c)')
    axes[1,1].set_ylabel('Run Count')
    axes[1,1].set_title('Distribution of Complexity Changes')

    for ax in axes.flat:
        if ax != axes[0,0]:
            ax.grid(alpha=0.3)
    plt.tight_layout(rect=[0,0,1,0.96])
    fig.savefig(out_dir / 'executive_panel.png', dpi=300)
    plt.close(fig)

    # Save summary stats
    summary = {
        'max_depth_mean_by_condition': df.groupby('condition')['max_depth_observed'].mean().to_dict(),
        'complexity_delta_mean_by_condition': df.groupby('condition')['c_delta'].mean().to_dict(),
        'overall_mean_max_depth': float(df['max_depth_observed'].mean()),
        'overall_mean_c_delta': float(df['c_delta'].mean())
    }
    (out_dir / 'executive_panel_summary.json').write_text(json.dumps(summary, indent=2))

    return summary

def export_per_run_csv(runs, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / 'per_run_depth_metrics.csv'
    fieldnames = ['prompt','condition','run_dir','max_depth_observed','depth_count','c_start','c_final','c_delta']
    with csv_path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in runs:
            c_start = r['c_values'][0] if r['c_values'] else None
            c_final = r['c_values'][-1] if r['c_values'] else None
            writer.writerow({
                'prompt': r['prompt'],
                'condition': r['condition'],
                'run_dir': r['run_dir'],
                'max_depth_observed': r['max_depth_observed'],
                'depth_count': r['depth_count'],
                'c_start': c_start,
                'c_final': c_final,
                'c_delta': (c_final - c_start) if (c_start is not None and c_final is not None) else None
            })
    return csv_path

def delta_summary(current_runs, archive_root: Path | None, out_dir: Path):
    summary = {'archive_status': 'missing'}
    if archive_root and archive_root.exists():
        # Could implement deeper delta; placeholder indicates presence
        summary['archive_status'] = 'found'
        # Example: difference in mean max depth if both depths recorded
        current_mean = np.mean([r['max_depth_observed'] for r in current_runs]) if current_runs else 0
        summary['current_mean_max_depth'] = current_mean
    (out_dir / 'delta_summary.json').write_text(json.dumps(summary, indent=2))
    return summary

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--archive-dir', help='Optional previous archived final_comprehensive directory')
    args = ap.parse_args()

    root = Path(args.root)
    out_dir = Path(args.out_dir)
    archive_dir = Path(args.archive_dir) if args.archive_dir else None

    runs = load_runs(root)
    if not runs:
        print('No runs found; aborting.')
        return 1

    depth_distribution_figure(runs, out_dir)
    exec_summary = executive_panel(runs, out_dir)
    csv_path = export_per_run_csv(runs, out_dir)
    delta = delta_summary(runs, archive_dir, out_dir)

    print('Artifacts generated:')
    print(f' - depth_distribution.png')
    print(f' - depth_distribution_by_condition.png')
    print(f' - executive_panel.png')
    print(f' - executive_panel_summary.json')
    print(f' - per_run_depth_metrics.csv ({csv_path})')
    print(f' - delta_summary.json (archive status: {delta["archive_status"]})')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
