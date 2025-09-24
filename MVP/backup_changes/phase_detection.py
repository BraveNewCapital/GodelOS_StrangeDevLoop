"""Phase Detection Module for Recursive Introspection Analysis.

Detects change points in introspection metrics using adaptive threshold methods.
Supports multiple detection algorithms and enriches IntrospectionRecord phase blocks.

Current Implementation:
- MAD-based adaptive threshold for delta_c signal detection
- Simple CUSUM for trend change detection
- Windowed permutation test for distribution shift
- Effect size calculation (Cohen's d) for significant changes

Future extensions: Binary segmentation, Pelt algorithm integration.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover
    np = None

from .cognitive_metrics import IntrospectionRecord, PhaseBlock

def mad_threshold(values: List[float], k: float = 2.5) -> float:
    """Compute MAD-based adaptive threshold."""
    if len(values) < 2:
        return float('inf')
    median_val = statistics.median(values)
    abs_deviations = [abs(x - median_val) for x in values]
    mad = statistics.median(abs_deviations)
    return k * mad if mad > 0 else 0.1  # fallback for constant series

def cohens_d(pre_values: List[float], post_values: List[float]) -> float:
    """Compute Cohen's d effect size between two groups."""
    if len(pre_values) < 2 or len(post_values) < 2:
        return 0.0
    
    mean_pre = statistics.mean(pre_values)
    mean_post = statistics.mean(post_values)
    
    var_pre = statistics.variance(pre_values)
    var_post = statistics.variance(post_values)
    
    # Pooled standard deviation
    n_pre, n_post = len(pre_values), len(post_values)
    pooled_std = math.sqrt(((n_pre - 1) * var_pre + (n_post - 1) * var_post) / (n_pre + n_post - 2))
    
    if pooled_std == 0:
        return 0.0
    
    return (mean_post - mean_pre) / pooled_std

def permutation_test(pre_values: List[float], post_values: List[float], 
                    n_permutations: int = 1000) -> float:
    """Simple permutation test for mean difference."""
    if len(pre_values) < 2 or len(post_values) < 2:
        return 1.0
    
    observed_diff = statistics.mean(post_values) - statistics.mean(pre_values)
    combined = pre_values + post_values
    n_pre = len(pre_values)
    
    import random
    random.seed(42)  # Reproducible for pilot
    
    extreme_count = 0
    for _ in range(n_permutations):
        shuffled = combined.copy()
        random.shuffle(shuffled)
        perm_pre = shuffled[:n_pre]
        perm_post = shuffled[n_pre:]
        perm_diff = statistics.mean(perm_post) - statistics.mean(perm_pre)
        
        if abs(perm_diff) >= abs(observed_diff):
            extreme_count += 1
    
    return extreme_count / n_permutations

def detect_max_delta_change(records: List[IntrospectionRecord], 
                           min_depth_offset: int = 2) -> Optional[Tuple[int, float, float]]:
    """Detect change point using maximum |delta_c| with adaptive threshold.
    
    Returns: (change_depth, max_delta_c, threshold) or None if no change detected.
    """
    delta_values = []
    depths = []
    
    for record in records:
        if record.metrics.delta_c is not None:
            delta_values.append(record.metrics.delta_c)
            depths.append(record.depth)
    
    if len(delta_values) < 3:
        return None
    
    # Adaptive threshold based on MAD of |delta_c|
    abs_deltas = [abs(d) for d in delta_values]
    threshold = mad_threshold(abs_deltas)
    
    # Find maximum |delta_c| exceeding threshold
    max_abs_delta = 0.0
    change_depth = None
    
    for i, (depth, delta) in enumerate(zip(depths, delta_values)):
        if depth <= min_depth_offset:  # Skip early depths
            continue
        
        abs_delta = abs(delta)
        if abs_delta > threshold and abs_delta > max_abs_delta:
            max_abs_delta = abs_delta
            change_depth = depth
    
    if change_depth is None:
        return None
    
    return change_depth, delta_values[depths.index(change_depth)], threshold

def detect_cusum_change(records: List[IntrospectionRecord], 
                       threshold: float = 0.1) -> Optional[Tuple[int, float]]:
    """Simple CUSUM change detection on c values.
    
    Returns: (change_depth, cusum_score) or None if no change detected.
    """
    c_values = [r.metrics.c for r in records]
    
    if len(c_values) < 4:
        return None
    
    # Compute mean of first half as reference
    mid_point = len(c_values) // 2
    reference_mean = statistics.mean(c_values[:mid_point])
    
    # CUSUM calculation
    cusum = 0.0
    max_cusum = 0.0
    change_depth = None
    
    for i, c_val in enumerate(c_values[mid_point:], start=mid_point):
        cusum = max(0, cusum + (c_val - reference_mean))
        if cusum > threshold and cusum > max_cusum:
            max_cusum = cusum
            change_depth = records[i].depth
    
    return (change_depth, max_cusum) if change_depth else None

def analyze_phases(records: List[IntrospectionRecord]) -> List[PhaseBlock]:
    """Analyze records and return enriched phase blocks."""
    if len(records) < 3:
        return [PhaseBlock() for _ in records]  # Empty phases
    
    phase_blocks = []
    
    # Detect primary change point using max delta method
    max_delta_result = detect_max_delta_change(records)
    cusum_result = detect_cusum_change(records)
    
    primary_change_depth = None
    method_used = "none"
    
    if max_delta_result:
        primary_change_depth = max_delta_result[0]
        method_used = "max_delta_mad"
    elif cusum_result:
        primary_change_depth = cusum_result[0]
        method_used = "cusum"
    
    # Build phase blocks for each record
    for record in records:
        phase = PhaseBlock()
        
        if primary_change_depth and record.depth == primary_change_depth:
            phase.change_point = True
            phase.change_point_method = method_used
            
            if max_delta_result:
                phase.change_point_score = abs(max_delta_result[1])
                
                # Effect size calculation (pre vs post window)
                change_idx = next(i for i, r in enumerate(records) if r.depth == primary_change_depth)
                pre_window = records[max(0, change_idx-2):change_idx]
                post_window = records[change_idx:min(len(records), change_idx+3)]
                
                if len(pre_window) >= 2 and len(post_window) >= 2:
                    pre_c_values = [r.metrics.c for r in pre_window]
                    post_c_values = [r.metrics.c for r in post_window]
                    
                    phase.effect_size_delta_c = cohens_d(pre_c_values, post_c_values)
                    phase.p_value = permutation_test(pre_c_values, post_c_values)
                    phase.window_pre = [r.depth for r in pre_window]
                    phase.window_post = [r.depth for r in post_window]
        
        # Add simple phase labeling
        if primary_change_depth:
            if record.depth < primary_change_depth:
                phase.detected_phase = "pre_transition"
            elif record.depth == primary_change_depth:
                phase.detected_phase = "transition_point"
            else:
                phase.detected_phase = "post_transition"
        else:
            phase.detected_phase = "stable"
        
        phase_blocks.append(phase)
    
    return phase_blocks

def enrich_records_with_phases(records: List[IntrospectionRecord]) -> List[IntrospectionRecord]:
    """Add phase detection results to existing records."""
    phase_blocks = analyze_phases(records)
    
    enriched_records = []
    for record, phase in zip(records, phase_blocks):
        # Create new record with updated phase
        enriched_record = record.copy(deep=True)
        enriched_record.phase = phase
        enriched_records.append(enriched_record)
    
    return enriched_records

def enrich_jsonl_file(input_path: Path, output_path: Optional[Path] = None) -> None:
    """Read JSONL file, enrich with phase detection, write to output."""
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_phases{input_path.suffix}"
    
    # Load records
    records = []
    with input_path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                record = IntrospectionRecord(**data)
                records.append(record)
    
    # Enrich with phases
    enriched_records = enrich_records_with_phases(records)
    
    # Write enriched records
    with output_path.open('w', encoding='utf-8') as f:
        for record in enriched_records:
            f.write(record.json() + '\n')

__all__ = [
    "analyze_phases",
    "enrich_records_with_phases", 
    "enrich_jsonl_file",
    "detect_max_delta_change",
    "detect_cusum_change",
    "cohens_d",
    "permutation_test"
]
