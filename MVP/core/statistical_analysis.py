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
from datetime import datetime, timezone
from pydantic import ValidationError


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
            try:
                manifest = RunManifest(**manifest_data)
            except ValidationError:
                # Fallback for synthetic / legacy minimal manifests (e.g., backfilled iterated_single_pass)
                fallback = {
                    "run_id": manifest_data.get("run_id") or run_dir.name,
                    "created_at": manifest_data.get("created") or manifest_data.get("created_at") or datetime.now(timezone.utc).isoformat(),
                    "git_commit": manifest_data.get("git_commit"),
                    "code_artifacts_hash": manifest_data.get("code_artifacts_hash") or None,
                    "model_id": manifest_data.get("model_id") or "unknown-model",
                    "hyperparameters": manifest_data.get("hyperparameters") or {},
                    "environment": manifest_data.get("environment") or {},
                    "conditions": manifest_data.get("conditions") or {"mode": "unknown"},
                    "schema_version": manifest_data.get("schema_version", SCHEMA_VERSION),
                    "prompt_base_sha": manifest_data.get("prompt_base_sha"),
                    "notes": manifest_data.get("notes") or ("synthetic_manifest_fallback" if manifest_data.get("conditions", {}).get("synthetic_iterated_single_pass") else None),
                }
                manifest = RunManifest(**fallback)
        
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
            # Robust condition extraction supporting multiple key conventions
            condition = (
                manifest.conditions.get("mode")
                or manifest.conditions.get("condition")
                or manifest.conditions.get("variant")
                or manifest.conditions.get("prompt_variant")
                or "unknown"
            )
            # Normalize to string (in case of non-string entries)
            try:
                condition = str(condition)
            except Exception:  # pragma: no cover - defensive
                condition = "unknown"
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
        # Return None placeholders for downstream JSON (serialize as null) instead of NaN
        return (None, None)
    
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

def permutation_distribution(group1_values: List[float], group2_values: List[float], n_permutations: int = 2000, seed: int = 42) -> Dict[str, Any]:
    if not group1_values or not group2_values:
        return {"error": "insufficient_values"}
    import random, statistics as _stats
    random.seed(seed)
    observed = _stats.mean(group1_values) - _stats.mean(group2_values)
    combined = group1_values + group2_values
    n1 = len(group1_values)
    diffs = []
    for _ in range(n_permutations):
        shuffled = combined.copy()
        random.shuffle(shuffled)
        diffs.append(_stats.mean(shuffled[:n1]) - _stats.mean(shuffled[n1:]))
    diffs.sort()
    def q(p):
        if not diffs:
            return None
        idx = int(p * (len(diffs)-1))
        return diffs[idx]
    return {
        "observed_diff": observed,
        "quantiles": {qv: q(qv) for qv in [0.01,0.025,0.05,0.5,0.95,0.975,0.99]},
        "sample_size": len(diffs),
        "seed": seed,
        "mean_perm_diff": sum(diffs)/len(diffs) if diffs else None,
    }


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

def compute_partial_auc(depths: List[int], values: List[float], max_depth: int = 5) -> float:
    """Compute AUC restricted to depths <= max_depth (inclusive).

    If fewer than 2 qualifying depths exist returns 0.0.
    """
    filtered = [(d, v) for d, v in zip(depths, values) if d <= max_depth]
    if len(filtered) < 2:
        return 0.0
    d_sorted, v_sorted = zip(*sorted(filtered))
    return compute_area_under_curve(list(d_sorted), list(v_sorted))

def linear_slope(depths: List[int], values: List[float], max_depth: int = 5) -> Optional[float]:
    """Return simple OLS slope of values vs depth for depths<=max_depth.
    Returns None if insufficient points.
    """
    subset = [(d, v) for d, v in zip(depths, values) if d <= max_depth]
    if len(subset) < 2:
        return None
    import statistics as _s
    xs, ys = zip(*subset)
    x_mean = _s.mean(xs)
    y_mean = _s.mean(ys)
    denom = sum((x - x_mean)**2 for x in xs)
    if denom == 0:
        return None
    num = sum((x - x_mean)*(y - y_mean) for x, y in subset)
    return num / denom

def tost_equivalence(mean_a: float, mean_b: float, sd_a: float, sd_b: float, n_a: int, n_b: int, delta: float = 0.05) -> Dict[str, Any]:
    """Two One-Sided Tests (TOST) for equivalence of means within +/- delta.
    Uses Welch standard error. Returns p_lower, p_upper, equivalence boolean.
    If inputs invalid returns structure with error.
    """
    import math
    if any(v is None for v in [sd_a, sd_b]) or n_a < 2 or n_b < 2:
        return {"error": "insufficient_stats"}
    diff = mean_a - mean_b
    se = math.sqrt((sd_a**2)/n_a + (sd_b**2)/n_b)
    if se == 0:
        return {"error": "zero_standard_error"}
    # t statistics
    t_lower = (diff + delta)/se  # H0: diff <= -delta
    t_upper = (diff - delta)/se  # H0: diff >= delta
    # Approx dof (Welch)
    dof_num = (sd_a**2/n_a + sd_b**2/n_b)**2
    dof_den = ((sd_a**2/n_a)**2)/(n_a-1) + ((sd_b**2/n_b)**2)/(n_b-1)
    dof = dof_num / dof_den if dof_den != 0 else (n_a + n_b - 2)
    try:
        from math import erf, sqrt
        # Approximate t->p via normal if scipy not available
        def t_to_p(t):
            # two-sided approx
            z = abs(t)
            return 2*(1-0.5*(1+erf(z/ (2**0.5))))
        p_lower = 1 - (1-0.5*(1+math.erf(t_lower/(2**0.5))))  # one-sided
        p_upper = 1 - (1-0.5*(1+math.erf(-t_upper/(2**0.5))))
    except Exception:
        p_lower = p_upper = None
    equivalence = (p_lower is not None and p_upper is not None and p_lower < 0.05 and p_upper < 0.05)
    return {"diff": diff, "delta": delta, "p_lower": p_lower, "p_upper": p_upper, "equivalent": equivalence, "dof": dof}

def required_n_for_effect(d: float, power: float = 0.8, alpha: float = 0.05) -> Optional[int]:
    """Approximate per-group sample size for two-sample t-test using Cohen's d.
    Uses normal approximation: n ~= 2 * ( (Z_{1-alpha/2} + Z_{power}) / d )^2
    """
    import math
    if d <= 0:
        return None
    # Normal quantiles (approx) without scipy
    def z(p):
        # Abramowitz-Stegun approximation for inverse CDF
        import math
        if p<=0 or p>=1:
            return 0
        # symmetry
        if p > 0.5:
            return -z(1-p)
        t = math.sqrt(-2*math.log(p))
        c0,c1,c2,c3,c4 = 2.515517,0.802853,0.010328,1.432788,0.189269
        return t - (c0 + c1*t + c2*t**2)/(1 + c3*t + c4*t**2)
    z_alpha = z(alpha/2)
    z_power = z(1-power)
    n = 2 * ((z_alpha + z_power)/d)**2
    return math.ceil(n)

def icc_oneway_random(data: Dict[int, List[float]]) -> Optional[float]:
    """Compute ICC(1) from a dict depth->list of replicate values (runs).
    Returns None if insufficient data.
    """
    # Flatten
    import statistics as _s
    k_values = [len(v) for v in data.values() if v]
    if not k_values:
        return None
    # Need at least 2 depths and 2 runs each ideally
    depths = [d for d,v in data.items() if len(v)>=2]
    if len(depths) < 2:
        return None
    # Compute mean squares
    grand = [val for v in data.values() for val in v]
    grand_mean = _s.mean(grand)
    n_depths = len(depths)
    k = min(len(data[d]) for d in depths)
    # Truncate each to k to balance
    trimmed = {d: data[d][:k] for d in depths}
    ms_between = (k * sum( (_s.mean(vals)-grand_mean)**2 for vals in trimmed.values()) )/(n_depths-1)
    ms_within = (sum( sum( (x-_s.mean(vals))**2 for x in vals) for vals in trimmed.values()) )/(n_depths*(k-1))
    if (ms_between + (k-1)*ms_within) == 0:
        return None
    return (ms_between - ms_within)/(ms_between + (k-1)*ms_within)


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
        "raw_values": {},
        "significance_tests": {},
        "effect_sizes": {},
        "multiple_comparison_correction": {}
    }
    
    # Descriptive statistics by condition and depth
    SAMPLE_WARN_THRESHOLD = 5
    for condition, depth_data in aggregated.items():
        summary["descriptive_stats"][condition] = {}
        summary["raw_values"][condition] = {}
        for depth, metrics in depth_data.items():
            depth_stats = {}
            for metric_name, values in metrics.items():
                if values:
                    ci_lower, ci_upper = bootstrap_confidence_interval(values)
                    n_vals = len(values)
                    insufficient = n_vals < SAMPLE_WARN_THRESHOLD
                    depth_stats[metric_name] = {
                        "n": n_vals,
                        "mean": statistics.mean(values),
                        "median": statistics.median(values),
                        "std": statistics.stdev(values) if n_vals > 1 else None,
                        "ci_95_lower": ci_lower,
                        "ci_95_upper": ci_upper,
                        "min": min(values),
                        "max": max(values),
                        "insufficient_samples": insufficient,
                    }
                    # Store raw values for auditability
                    summary["raw_values"][condition].setdefault(depth, {})[metric_name] = values
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
                        try:
                            base_mean = statistics.mean(baseline_values)
                            cond_mean = statistics.mean(condition_values)
                            base_std = statistics.stdev(baseline_values) if len(baseline_values) > 1 else 0.0
                            variance_warning = base_std == 0.0
                            denom = base_std if base_std != 0.0 else 1.0  # avoid zero-division
                            effect_size = (cond_mean - base_mean) / denom
                            p_value = permutation_test_conditions(condition_values, baseline_values) if not variance_warning else 1.0
                            perm_meta = None
                            if not variance_warning and len(baseline_values) >= 5 and len(condition_values) >= 5:
                                perm_meta = permutation_distribution(condition_values, baseline_values, n_permutations=1000)
                            test_detail = {
                                "depth": depth,
                                "metric": metric_name,
                                "p_value": p_value,
                                "effect_size": effect_size,
                                "baseline_mean": base_mean,
                                "condition_mean": cond_mean,
                                "baseline_std": base_std if base_std != 0.0 else None,
                                "variance_warning": variance_warning,
                                "permutation_summary": perm_meta,
                            }
                            test_details.append(test_detail)
                            p_values_collection.append(p_value)
                        except Exception as e:  # pragma: no cover
                            test_details.append({
                                "depth": depth,
                                "metric": metric_name,
                                "error": f"significance_test_failed: {e}",
                            })
            
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
        depths = sorted(depth_data.keys())
        c_means = []
        for depth in depths:
            c_values = depth_data[depth].get("c", [])
            c_means.append(statistics.mean(c_values) if c_values else 0.0)
        if depths:
            if len(depths) >= 2:
                auc_c = compute_area_under_curve(depths, c_means)
                p_auc_c = compute_partial_auc(depths, c_means, max_depth=5)
                early_slope = linear_slope(depths, c_means, max_depth=5)
                summary["auc_analysis"][condition] = {
                    "auc_c": auc_c,
                    "partial_auc_c_d1_5": p_auc_c,
                    "early_phase_slope_d1_5": early_slope,
                    "final_depth_c_mean": c_means[-1],
                    "max_depth": max(depths),
                    "single_depth": False,
                }
            else:
                summary["auc_analysis"][condition] = {
                    "auc_c": 0.0,
                    "partial_auc_c_d1_5": 0.0,
                    "early_phase_slope_d1_5": None,
                    "final_depth_c_mean": c_means[0],
                    "max_depth": depths[0],
                    "single_depth": True,
                }
    
    # Data quality assessment block
    data_quality: Dict[str, Any] = {}
    for condition, depth_data in summary["descriptive_stats"].items():
        depth_counts = []
        for depth, metrics in depth_data.items():
            c_stats = metrics.get("c")
            if c_stats:
                depth_counts.append(c_stats.get("n", 0))
        total_depths = len(depth_data)
        non_empty_depths = sum(1 for d in depth_data.values() if "c" in d)
        min_n = min(depth_counts) if depth_counts else 0
        max_n = max(depth_counts) if depth_counts else 0
        data_quality[condition] = {
            "total_depths": total_depths,
            "depths_with_data": non_empty_depths,
            "depth_completeness_ratio": (non_empty_depths / total_depths) if total_depths else None,
            "min_n_per_depth": min_n,
            "max_n_per_depth": max_n,
            "meets_statistical_threshold": min_n >= 5,
        }
    summary["data_quality"] = data_quality

    # Reliability (ICC) for c by depth across runs
    reliability: Dict[str, Any] = {}
    for condition, depth_data in aggregated.items():
        depth_dict = {}
        for depth, metrics in depth_data.items():
            depth_dict[depth] = metrics.get("c", [])
        reliability[condition] = {
            "icc_c_by_depth": icc_oneway_random(depth_dict)
        }
    summary["reliability"] = reliability

    # Equivalence test (R vs shuffled_recursive) post-depth>=6 if both exist
    if "recursive" in aggregated and "shuffled_recursive" in aggregated:
        eq_metrics = {}
        for depth, rec_metrics in aggregated["recursive"].items():
            if depth >= 6 and depth in aggregated["shuffled_recursive"]:
                rec_vals = rec_metrics.get("c", [])
                sh_vals = aggregated["shuffled_recursive"][depth].get("c", [])
                if len(rec_vals) >= 2 and len(sh_vals) >= 2:
                    import statistics as _s
                    eq_metrics[depth] = tost_equivalence(
                        _s.mean(rec_vals), _s.mean(sh_vals),
                        _s.stdev(rec_vals) if len(rec_vals)>1 else 0.0,
                        _s.stdev(sh_vals) if len(sh_vals)>1 else 0.0,
                        len(rec_vals), len(sh_vals), delta=0.05
                    )
        summary["equivalence_tests_recursive_vs_shuffled"] = eq_metrics

    # Power re-estimation table for effect sizes of interest
    power_table = {}
    for d in [0.1,0.2,0.3,0.4,0.5]:
        rn = required_n_for_effect(d)
        power_table[str(d)] = rn
    summary["power_recommendations_d_target"] = power_table

    # Mixed-effects early phase model placeholder (depth<=5)
    try:
        import pandas as _pd  # type: ignore
        import statsmodels.formula.api as smf  # type: ignore
        rows = []
        for condition, runs in condition_data.items():
            for run in runs:
                for rec in run["records"]:
                    if rec.depth <= 5:
                        rows.append({
                            "c": rec.metrics.c,
                            "depth": rec.depth,
                            "condition": condition,
                            "run_id": run["manifest"].run_id,
                        })
        if rows:
            df = _pd.DataFrame(rows)
            # Simple random intercept for run_id if statsmodels supports
            # Using mixedlm (fallback to OLS if fails)
            try:
                import statsmodels.api as sm  # type: ignore
                md = sm.MixedLM.from_formula("c ~ depth * condition", groups="run_id", data=df)
                mdf = md.fit()
                summary["mixed_effects_early_phase"] = {
                    "model": "c ~ depth * condition (random intercept run_id)",
                    "aic": mdf.aic,
                    "bic": mdf.bic,
                    "params": {k: float(v) for k, v in mdf.params.items()},
                    "converged": bool(getattr(mdf, "converged", True)),
                }
            except Exception as e:  # pragma: no cover
                ols = smf.ols("c ~ depth * condition", data=df).fit()
                summary["mixed_effects_early_phase"] = {
                    "model": "OLS substitute c ~ depth * condition",
                    "aic": float(ols.aic),
                    "bic": float(ols.bic),
                    "params": {k: float(v) for k, v in ols.params.items()},
                    "note": f"MixedLM failed: {e}"}
        else:
            summary["mixed_effects_early_phase"] = {"error": "no_rows"}
    except Exception:
        summary["mixed_effects_early_phase"] = {"error": "statsmodels_not_available"}

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
