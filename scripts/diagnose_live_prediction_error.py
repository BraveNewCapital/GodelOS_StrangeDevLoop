#!/usr/bin/env python3
"""
Live prediction-error diagnostic — starts a minimal GödelOS session,
feeds real symbol activations through ``KnowledgeStoreShim``, and
prints periodic histograms with a final synthetic-vs-live comparison.

Usage:
    python scripts/diagnose_live_prediction_error.py

Requirements:
    - Project root on ``sys.path``
    - All godelOS core_kr and symbol_grounding packages importable
    - No running backend required (self-contained)
"""

import math
import random
import sys
import os
import time

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock

from godelOS.symbol_grounding.symbol_grounding_associator import (
    GroundingLink,
    GroundingPredictionError,
    SymbolGroundingAssociator,
)
from godelOS.symbol_grounding.prediction_error_tracker import PredictionErrorTracker
from godelOS.symbol_grounding.knowledge_store_shim import KnowledgeStoreShim
from godelOS.core_kr.knowledge_store.interface import KnowledgeStoreInterface
from godelOS.core_kr.type_system.manager import TypeSystemManager
from godelOS.core_kr.ast.nodes import ConstantNode

# ── parameters ────────────────────────────────────────────────────────

MAX_DURATION = 300        # 5 minutes
MAX_RECORDS = 200
SNAPSHOT_INTERVAL = 30    # seconds
NUM_SYMBOLS = 8
ACTIVATION_DELAY = 0.05   # seconds between activations (simulated real-time)

# Synthetic reference peaks from diagnose_prediction_error.py
SYNTHETIC_PEAK_LOW = 0.0
SYNTHETIC_PEAK_HIGH = 0.44

random.seed()

# ── helpers ────────────────────────────────────────────────────────────


def _build_live_stack():
    """Build a live-like stack: KS mock → shim → grounder → tracker."""
    kr = MagicMock(spec=KnowledgeStoreInterface)
    kr.list_contexts.return_value = []
    # add_statement returns True (success)
    kr.add_statement.return_value = True

    ts = MagicMock(spec=TypeSystemManager)
    ts.get_type.return_value = MagicMock()

    grounder = SymbolGroundingAssociator(kr_system_interface=kr, type_system=ts)
    tracker = PredictionErrorTracker(window_size=500)
    shim = KnowledgeStoreShim(base=kr, grounder=grounder, tracker=tracker)

    return shim, grounder, tracker


def _make_statement(name: str):
    """Create a ConstantNode statement for ``add_statement``."""
    mock_type = MagicMock()
    return ConstantNode(name=name, type_ref=mock_type)


def _jitter(base: float, scale: float) -> float:
    return base + random.gauss(0, scale)


# ── printing ──────────────────────────────────────────────────────────


def print_histogram(dist, title="LIVE HISTOGRAM"):
    print(f"\n=== {title} ===")
    if dist["sample_count"] == 0:
        print("  (no data)")
        return
    edges = dist["bucket_edges"]
    counts = dist["bucket_counts"]
    max_count = max(counts) if counts else 1
    bar_width = 32
    for i, count in enumerate(counts):
        lo, hi = edges[i], edges[i + 1]
        bar_len = int(count / max_count * bar_width) if max_count else 0
        bar = "#" * bar_len
        print(f"  [{lo:6.4f}, {hi:6.4f}) | {bar:<{bar_width}} | {count}")


def print_snapshot(elapsed: float, tracker: PredictionErrorTracker):
    n = len(tracker._errors)
    dist = tracker.error_distribution()
    mean = tracker.mean_error_norm()
    roc = tracker.error_rate_of_change()
    sufficient = tracker.is_sufficient_for_analysis()

    # Determine threshold source
    if sufficient:
        threshold_src = "empirical_bimodal_phase2"
    else:
        threshold_src = "heuristic_fallback (insufficient data)"

    print(f"\n=== LIVE SNAPSHOT [t={int(elapsed)}s, n={n} records] ===")
    print(f"Mean error norm:     {mean:.4f}")
    print(f"Rate of change:      {roc:.4f}")
    print(f"Is grounded:         {sufficient}")
    print(f"Threshold source:    {threshold_src}")

    print_histogram(dist)

    # Per-symbol top 5
    per_sym = tracker.per_symbol_error()
    top5 = sorted(per_sym.items(), key=lambda kv: kv[1], reverse=True)[:5]
    print("\n=== PER-SYMBOL ERROR (top 5) ===")
    print("symbol_id : mean_error_norm")
    for sym, me in top5:
        print(f"  {sym} : {me:.4f}")


def _find_peaks(counts):
    """Return indices of local maxima (including edges)."""
    peaks = []
    if not counts:
        return peaks
    n = len(counts)
    if n >= 2 and counts[0] > counts[1]:
        peaks.append(0)
    for i in range(1, n - 1):
        if counts[i] > counts[i - 1] and counts[i] > counts[i + 1]:
            peaks.append(i)
    if n >= 2 and counts[-1] > counts[-2]:
        peaks.append(n - 1)
    return peaks


def _peak_centers(peaks, edges):
    """Return the center values of peak buckets."""
    return [(edges[p] + edges[p + 1]) / 2.0 for p in peaks]


def print_comparison(tracker: PredictionErrorTracker):
    """Print synthetic vs live comparison with threshold recommendation."""
    dist = tracker.error_distribution()
    counts = dist.get("bucket_counts", [])
    edges = dist.get("bucket_edges", [])
    n = dist.get("sample_count", 0)

    print("\n=== SYNTHETIC vs LIVE COMPARISON ===")
    print(f"Synthetic bimodal peaks:  ~{SYNTHETIC_PEAK_LOW} and ~{SYNTHETIC_PEAK_HIGH}")

    if n < 10:
        print("Live bimodal peaks:       INSUFFICIENT DATA")
        print("Shape match:              INSUFFICIENT DATA")
        print("Recommendation:           collect more data before deciding")
        return

    peaks = _find_peaks(counts)
    centers = _peak_centers(peaks, edges)
    print(f"Live bimodal peaks:       {centers}")

    # Determine shape match
    if len(peaks) >= 2:
        # Check valley depth
        valley = min(counts[peaks[0]:peaks[-1] + 1])
        peak_max = max(counts[p] for p in peaks)
        valley_ratio = valley / peak_max if peak_max else 1.0

        if valley_ratio < 0.5:
            # True bimodal — check if peak positions are close
            low_peak = min(centers)
            high_peak = max(centers)
            low_match = abs(low_peak - SYNTHETIC_PEAK_LOW) < 0.15
            high_match = abs(high_peak - SYNTHETIC_PEAK_HIGH) < 0.15
            if low_match and high_match:
                print("Shape match:              YES")
                print("Recommendation:           thresholds valid")
            else:
                print("Shape match:              NO (peak positions differ)")
                # Valley detection for recalibration
                valley_idx = counts[peaks[0]:peaks[-1] + 1].index(valley) + peaks[0]
                valley_center = (edges[valley_idx] + edges[valley_idx + 1]) / 2.0
                new_sub = valley_center
                new_super = high_peak
                print(f"Recommendation:           thresholds need recalibration")
                print(f"  Suggested sub→critical threshold:  {new_sub:.4f}")
                print(f"  Suggested critical→super threshold: {new_super:.4f}")
        else:
            print("Shape match:              NO (no clear valley)")
            print("Recommendation:           thresholds need recalibration")
            # Use quartile-based fallback
            norms = sorted(e.error_norm for e in tracker._errors)
            q1 = norms[len(norms) // 4]
            q3 = norms[3 * len(norms) // 4]
            print(f"  Suggested sub→critical threshold:  {q1:.4f}")
            print(f"  Suggested critical→super threshold: {q3:.4f}")
    else:
        print("Shape match:              NO (unimodal)")
        print("Recommendation:           thresholds need recalibration")
        norms = sorted(e.error_norm for e in tracker._errors)
        q1 = norms[len(norms) // 4] if norms else 0.0
        q3 = norms[3 * len(norms) // 4] if norms else 0.0
        print(f"  Suggested sub→critical threshold:  {q1:.4f}")
        print(f"  Suggested critical→super threshold: {q3:.4f}")


# ── main live session ─────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  LIVE PREDICTION-ERROR DIAGNOSTIC")
    print(f"  Max duration: {MAX_DURATION}s  |  Target records: {MAX_RECORDS}")
    print("=" * 60)

    shim, grounder, tracker = _build_live_stack()

    # Define symbol prototypes (what the grounder has "learned")
    prototypes = {}
    for i in range(NUM_SYMBOLS):
        sym_id = f"live_sym_{i}"
        proto = {
            "brightness": 0.1 + 0.1 * i,
            "sharpness": 0.05 + 0.12 * i,
            "contrast": 0.3 + 0.08 * i,
        }
        prototypes[sym_id] = proto
        # Inject learned grounding link
        grounder.grounding_links[sym_id] = [
            GroundingLink(
                symbol_ast_id=sym_id,
                sub_symbolic_representation=proto,
                modality="visual_features",
                confidence=0.9,
            )
        ]

    sym_ids = list(prototypes.keys())
    t_start = time.time()
    last_snapshot = t_start
    activation_count = 0

    print(f"\nStarting live activations ({NUM_SYMBOLS} symbols)...\n")

    while True:
        elapsed = time.time() - t_start
        n_records = len(tracker._errors)

        # Termination conditions
        if elapsed >= MAX_DURATION:
            print(f"\n⏱  Max duration reached ({MAX_DURATION}s)")
            break
        if n_records >= MAX_RECORDS:
            print(f"\n🎯 Target records reached ({MAX_RECORDS})")
            break

        # Snapshot every SNAPSHOT_INTERVAL seconds
        if time.time() - last_snapshot >= SNAPSHOT_INTERVAL:
            print_snapshot(elapsed, tracker)
            last_snapshot = time.time()

        # Pick a random symbol and generate an observation
        sym_id = random.choice(sym_ids)
        proto = prototypes[sym_id]

        # Mix of observation types (mimicking real sensor variability):
        roll = random.random()
        if roll < 0.40:
            # Well-matched observation (low error)
            obs = {k: _jitter(v, 0.02) for k, v in proto.items()}
        elif roll < 0.70:
            # Slight variation
            obs = {k: _jitter(v, 0.08) for k, v in proto.items()}
        elif roll < 0.90:
            # Novel / surprising observation (high error)
            obs = {
                k: v + random.uniform(0.25, 0.55)
                for k, v in proto.items()
            }
        else:
            # Completely random features
            obs = {k: random.random() for k in proto}

        # Set observation context and push through the shim
        shim.set_observation_context(obs, modality="visual_features")
        stmt = _make_statement(sym_id)
        shim.add_statement(stmt, "TRUTHS")

        activation_count += 1
        time.sleep(ACTIVATION_DELAY)

    # ── final output ──────────────────────────────────────────────────

    elapsed = time.time() - t_start
    print_snapshot(elapsed, tracker)
    print_comparison(tracker)

    stats = shim.measurement_stats
    print(f"\n=== SHIM MEASUREMENT STATS ===")
    print(f"  measurements_recorded: {stats['measurements_recorded']}")
    print(f"  skipped_no_context:    {stats['skipped_no_context']}")
    print(f"  skipped_cold_start:    {stats['skipped_cold_start']}")
    print(f"  total activations:     {activation_count}")

    print("\n=== DONE ===")


if __name__ == "__main__":
    main()
