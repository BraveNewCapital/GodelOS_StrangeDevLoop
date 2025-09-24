"""Statistical analysis and aggregation for recursive introspection experiments.

Aggregates data across multiple experimental runs and conditions, performs
statistical comparisons, and generates summary reports with significance testing.

Key features:
1. Load and align multiple JSONL + manifest files by experimental condition
2. Compute descriptive statistics (mean, median, 95% bootstrap CI) per depth
3. Permutation tests comparing recursive vs baseline conditions
4. Benjamini-Hochberg multiple comparison correction
5. Effect size calculations and AUC over depth analysis
6. Export statistical summary reports
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from .cognitive_metrics import IntrospectionRecord, RunManifest, SCHEMA_VERSION


def load_experiment_data(run_dirs: List[Path]) -> Dict[str, List[Dict[str, Any]]]:
    """Load multiple experimental runs grouped by condition.
    
    Returns:
        Dict mapping condition -> list of run data (manifest + records)
    """
    condition_data = defaultdict(list)
    
    for run_dir in run_dirs:
        if not run_dir.is_dir():
            continue
            
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
            
        # Load manifest
        with manifest_path.open('r', encoding='utf-8') as f:
            manifest_data = json.load(f)
            manifest = RunManifest(**manifest_data)
        
        # Find and load records file
        records_files = list(run_dir.glob("*.jsonl"))
        if not records_files:
            continue
            
        records_path = records_files[0]  # Use first .jsonl file found
        
        # Load records
        records = []
        with records_path.open('r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):  # Skip empty lines and comments
                    try:
                        data = json.loads(line)
                        if 'error' not in data:  # Skip error records
                            record = IntrospectionRecord(**data)
                            records.append(record)
                    except Exception:
                        continue  # Skip malformed records
        
        if records:
            condition = manifest.conditions.get("mode", "unknown")
            condition_data[condition].append({
                "manifest": manifest,
                "records": sorted(records, key=lambda r: r.depth),
                "run_dir": run_dir
            })
    
    return dict(condition_data)


def bootstrap_confidence_interval(values: List[float], 
                                confidence: float = 0.95,
                                n_bootstrap: int = 1000) -> Tuple[float, float]:
    """Compute bootstrap confidence interval for mean."""
    if len(values) < 2:
        return (float('nan'), float('nan'))
    
    import random
    random.seed(42)  # Reproducible results
    
    bootstrap_means = []
    for _ in range(n_bootstrap):
        sample = [random.choice(values) for _ in range(len(values))]
        bootstrap_means.append(statistics.mean(sample))
    
    alpha = 1 - confidence
    lower_percentile = (alpha / 2) * 100
    upper_percentile = (1 - alpha / 2) * 100
    
    bootstrap_means.sort()
    n = len(bootstrap_means)
    lower_idx = int(lower_percentile / 100 * n)
    upper_idx = int(upper_percentile / 100 * n)
    
    return bootstrap_means[lower_idx], bootstrap_means[upper_idx]


def permutation_test_conditions(group1_values: List[float], 
                               group2_values: List[float],
                               n_permutations: int = 10000) -> float:
    """Permutation test comparing means of two conditions."""
    if not group1_values or not group2_values:
        return 1.0
    
    observed_diff = statistics.mean(group1_values) - statistics.mean(group2_values)
    combined = group1_values + group2_values
    n1 = len(group1_values)
    
    import random
    random.seed(42)  # Reproducible
    
    extreme_count = 0
    for _ in range(n_permutations):
        shuffled = combined.copy()
        random.shuffle(shuffled)
        perm_group1 = shuffled[:n1]
        perm_group2 = shuffled[n1:]
        perm_diff = statistics.mean(perm_group1) - statistics.mean(perm_group2)
        
        if abs(perm_diff) >= abs(observed_diff):
            extreme_count += 1
    
    return extreme_count / n_permutations


def benjamini_hochberg_correction(p_values: List[float], alpha: float = 0.05) -> List[bool]:
    """Apply Benjamini-Hochberg correction for multiple comparisons.
    
    Returns list of booleans indicating which tests remain significant.
    """
    if not p_values:
        return []
    
    # Sort p-values with their original indices
    indexed_p_values = [(p, i) for i, p in enumerate(p_values)]
    indexed_p_values.sort()
    
    m = len(p_values)
    significant = [False] * m
    
    # Apply BH procedure
    for rank, (p_value, original_idx) in enumerate(indexed_p_values, 1):
        critical_value = (rank / m) * alpha
        if p_value <= critical_value:
            significant[original_idx] = True
        else:
            break  # Since p-values are sorted, all remaining will also fail
    
    return significant


def compute_area_under_curve(depths: List[int], values: List[float]) -> float:
    """Compute AUC using trapezoidal rule."""
    if len(depths) < 2 or len(values) < 2:
        return 0.0
    
    auc = 0.0
    for i in range(1, len(depths)):
        width = depths[i] - depths[i-1]
        height = (values[i] + values[i-1]) / 2
        auc += width * height
    
    return auc


def aggregate_metrics_by_depth(condition_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[int, Dict[str, Any]]]:
    """Aggregate metrics by depth for each condition.
    
    Returns:
        Dict[condition][depth] -> {metric_name: [values], ...}
    """
    aggregated = {}
    
    for condition, runs in condition_data.items():
        depth_metrics = defaultdict(lambda: defaultdict(list))
        
        for run_data in runs:
            for record in run_data["records"]:
                depth = record.depth
                metrics = record.metrics
                
                # Collect all non-null metric values
                depth_metrics[depth]["c"].append(metrics.c)
                if metrics.delta_c is not None:
                    depth_metrics[depth]["delta_c"].append(metrics.delta_c)
                if metrics.rolling_c_slope is not None:
                    depth_metrics[depth]["rolling_c_slope"].append(metrics.rolling_c_slope)
                if metrics.embedding_drift is not None:
                    depth_metrics[depth]["embedding_drift"].append(metrics.embedding_drift)
                if metrics.novelty_score is not None:
                    depth_metrics[depth]["novelty_score"].append(metrics.novelty_score)
                
                depth_metrics[depth]["token_count"].append(metrics.token_count)
                depth_metrics[depth]["runtime_ms"].append(metrics.runtime_ms)
        
        aggregated[condition] = dict(depth_metrics)
    
    return aggregated


def generate_statistical_summary(condition_data: Dict[str, List[Dict[str, Any]]],
                                baseline_condition: str = "single_pass") -> Dict[str, Any]:
    """Generate comprehensive statistical summary report."""
    
    # Aggregate metrics by depth
    aggregated = aggregate_metrics_by_depth(condition_data)
    
    summary = {
        "schema_version": SCHEMA_VERSION,
        "analysis_timestamp": json.dumps(None),  # Will be filled by caller
        "conditions_analyzed": list(condition_data.keys()),
        "baseline_condition": baseline_condition,
        "run_counts": {cond: len(runs) for cond, runs in condition_data.items()},
        "descriptive_stats": {},
        "significance_tests": {},
        "effect_sizes": {},
        "multiple_comparison_correction": {}
    }
    
    # Descriptive statistics by condition and depth
    for condition, depth_data in aggregated.items():
        summary["descriptive_stats"][condition] = {}
        
        for depth, metrics in depth_data.items():
            depth_stats = {}
            
            for metric_name, values in metrics.items():
                if values:  # Only compute stats for non-empty metrics
                    ci_lower, ci_upper = bootstrap_confidence_interval(values)
                    depth_stats[metric_name] = {
                        "n": len(values),
                        "mean": statistics.mean(values),
                        "median": statistics.median(values),
                        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
                        "ci_95_lower": ci_lower,
                        "ci_95_upper": ci_upper,
                        "min": min(values),
                        "max": max(values)
                    }
            
            summary["descriptive_stats"][condition][depth] = depth_stats
    
    # Significance tests comparing each condition to baseline
    if baseline_condition in aggregated:
        baseline_data = aggregated[baseline_condition]
        
        for condition in aggregated:
            if condition == baseline_condition:
                continue
                
            condition_data_agg = aggregated[condition]
            summary["significance_tests"][condition] = {}
            
            # Test each metric at each depth
            p_values_collection = []
            test_details = []
            
            for depth in set(baseline_data.keys()) & set(condition_data_agg.keys()):
                for metric_name in ["c", "delta_c", "embedding_drift", "novelty_score"]:
                    baseline_values = baseline_data[depth].get(metric_name, [])
                    condition_values = condition_data_agg[depth].get(metric_name, [])
                    
                    if len(baseline_values) >= 3 and len(condition_values) >= 3:
                        p_value = permutation_test_conditions(condition_values, baseline_values)
                        effect_size = (statistics.mean(condition_values) - statistics.mean(baseline_values)) / \
                                    (statistics.stdev(baseline_values) if len(baseline_values) > 1 else 1.0)
                        
                        test_detail = {
                            "depth": depth,
                            "metric": metric_name,
                            "p_value": p_value,
                            "effect_size": effect_size,
                            "baseline_mean": statistics.mean(baseline_values),
                            "condition_mean": statistics.mean(condition_values)
                        }
                        
                        test_details.append(test_detail)
                        p_values_collection.append(p_value)
            
            summary["significance_tests"][condition] = test_details
            
            # Apply multiple comparison correction
            if p_values_collection:
                significant_flags = benjamini_hochberg_correction(p_values_collection)
                summary["multiple_comparison_correction"][condition] = [
                    {**test, "significant_after_correction": sig}
                    for test, sig in zip(test_details, significant_flags)
                ]
    
    # AUC analysis
    summary["auc_analysis"] = {}
    for condition, depth_data in aggregated.items():
        # Compute AUC for c metric across depths
        depths = sorted(depth_data.keys())
        c_means = []
        
        for depth in depths:
            c_values = depth_data[depth].get("c", [])
            if c_values:
                c_means.append(statistics.mean(c_values))
            else:
                c_means.append(0.0)  # Missing data fallback
        
        if len(depths) >= 2:
            auc_c = compute_area_under_curve(depths, c_means)
            summary["auc_analysis"][condition] = {
                "auc_c": auc_c,
                "final_depth_c_mean": c_means[-1] if c_means else 0.0,
                "max_depth": max(depths) if depths else 0
            }
    
    return summary


def run_statistical_analysis(run_dirs: List[Path], 
                            output_path: Optional[Path] = None,
                            baseline_condition: str = "single_pass") -> Dict[str, Any]:
    """Complete statistical analysis pipeline.
    
    Args:
        run_dirs: List of run directories to analyze
        output_path: Optional path to save summary JSON
        baseline_condition: Condition to use as baseline for comparisons
    
    Returns:
        Statistical summary dictionary
    """
    # Load data
    condition_data = load_experiment_data(run_dirs)
    
    if not condition_data:
        return {"error": "No valid experimental data found"}
    
    # Generate summary
    summary = generate_statistical_summary(condition_data, baseline_condition)
    
    # Add timestamp
    from datetime import datetime, timezone
    summary["analysis_timestamp"] = datetime.now(timezone.utc).isoformat()
    
    # Save if requested
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
    
    return summary


def print_summary_report(summary: Dict[str, Any]) -> None:
    """Print human-readable summary of statistical analysis."""
    print("=== Recursive Introspection Statistical Analysis ===")
    print(f"Analysis completed: {summary.get('analysis_timestamp', 'Unknown')}")
    print(f"Conditions: {', '.join(summary.get('conditions_analyzed', []))}")
    print(f"Baseline: {summary.get('baseline_condition', 'N/A')}")
    print()
    
    # Run counts
    print("Run Counts by Condition:")
    for condition, count in summary.get("run_counts", {}).items():
        print(f"  {condition}: {count} runs")
    print()
    
    # AUC comparison
    print("Area Under Curve (AUC) for coherence metric c:")
    auc_data = summary.get("auc_analysis", {})
    for condition, auc_info in auc_data.items():
        print(f"  {condition}: AUC = {auc_info.get('auc_c', 0):.3f}, Final c = {auc_info.get('final_depth_c_mean', 0):.3f}")
    print()
    
    # Significance test summary
    if "multiple_comparison_correction" in summary:
        print("Significant Differences (after Benjamini-Hochberg correction):")
        for condition, tests in summary["multiple_comparison_correction"].items():
            significant_tests = [t for t in tests if t.get("significant_after_correction", False)]
            if significant_tests:
                print(f"  {condition} vs baseline:")
                for test in significant_tests:
                    print(f"    Depth {test['depth']}, {test['metric']}: p={test['p_value']:.4f}, effect={test['effect_size']:.3f}")
            else:
                print(f"  {condition} vs baseline: No significant differences detected")
        print()


__all__ = [
    "load_experiment_data",
    "generate_statistical_summary", 
    "run_statistical_analysis",
    "print_summary_report",
    "bootstrap_confidence_interval",
    "permutation_test_conditions",
    "benjamini_hochberg_correction"
]
