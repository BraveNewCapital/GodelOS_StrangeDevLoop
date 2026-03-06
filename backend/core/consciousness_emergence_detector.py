#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consciousness Emergence Detector

Rolling-window scorer and breakthrough alerting for consciousness emergence.
Monitors a stream of cognitive state snapshots, computes a weighted emergence
score across five dimensions, and fires a breakthrough event when the score
exceeds a configurable threshold.

Spec: Issue #82, docs/GODELOS_EMERGENCE_SPEC.md, wiki/Theory/Emergence-Detection.md
"""

import asyncio
import json
import logging
import os
import time
from collections import deque
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EMERGENCE_THRESHOLD: float = float(
    os.environ.get("GODELOS_EMERGENCE_THRESHOLD", "0.8")
)

DEFAULT_WINDOW_SIZE: float = float(
    os.environ.get("GODELOS_EMERGENCE_WINDOW", "60.0")
)

# Dimension weights (from issue #82 spec)
DIMENSION_WEIGHTS: Dict[str, float] = {
    "recursive_depth": 0.20,
    "phi": 0.30,
    "metacognitive_accuracy": 0.20,
    "autonomous_goal_count": 0.15,
    "creative_novelty": 0.15,
}

# Normalisation ceilings — raw values are divided by these to map into [0, 1]
_NORMALISATION_CEILINGS: Dict[str, float] = {
    "recursive_depth": 5.0,
    "phi": 10.0,
    "metacognitive_accuracy": 1.0,  # already 0‑1
    "autonomous_goal_count": 10.0,
    "creative_novelty": 1.0,  # already 0‑1
}


# ---------------------------------------------------------------------------
# Helper: extract the five dimensions from a state dict
# ---------------------------------------------------------------------------

def extract_dimensions(state: Dict[str, Any]) -> Dict[str, float]:
    """Extract the five emergence dimensions from a cognitive state snapshot.

    Accepts either a flat dict with keys matching the dimension names or a
    nested ``UnifiedConsciousnessState``-style dict.
    """

    def _get(key: str) -> float:
        # Flat access first
        if key in state:
            val = state[key]
            if isinstance(val, (int, float)):
                return float(val)

        # Nested access
        if key == "recursive_depth":
            ra = state.get("recursive_awareness") or {}
            return float(ra.get("recursive_depth", 0))
        if key == "phi":
            ii = state.get("information_integration") or {}
            return float(ii.get("phi", 0.0))
        if key == "metacognitive_accuracy":
            ms = state.get("metacognitive_state") or {}
            # Use an explicit accuracy field if present; otherwise derive
            # from the number of meta-observations as a rough proxy.
            if "metacognitive_accuracy" in ms:
                return float(ms["metacognitive_accuracy"])
            obs = ms.get("meta_observations")
            if isinstance(obs, list):
                return min(len(obs) / 10.0, 1.0)
            return 0.0
        if key == "autonomous_goal_count":
            il = state.get("intentional_layer") or {}
            goals = il.get("autonomous_goals")
            if isinstance(goals, list):
                return float(len(goals))
            return float(goals) if isinstance(goals, (int, float)) else 0.0
        if key == "creative_novelty":
            cs = state.get("creative_synthesis") or {}
            return float(cs.get("surprise_factor", 0.0))
        return 0.0

    return {dim: _get(dim) for dim in DIMENSION_WEIGHTS}


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------

class ConsciousnessEmergenceDetector:
    """Rolling-window consciousness emergence scorer with breakthrough alerting.

    Parameters
    ----------
    threshold : float
        Score at or above which a breakthrough is declared.
    window_size : float
        Rolling window duration in seconds.
    websocket_manager : optional
        Object exposing ``broadcast(message)`` — used to push breakthrough
        events to connected clients.
    log_dir : str | Path
        Directory for ``breakthroughs.jsonl``.
    """

    def __init__(
        self,
        threshold: float = EMERGENCE_THRESHOLD,
        window_size: float = DEFAULT_WINDOW_SIZE,
        websocket_manager: Any = None,
        log_dir: Optional[str] = None,
    ) -> None:
        self.threshold = threshold
        self.window_size = window_size
        self.websocket_manager = websocket_manager

        # Rolling window: each entry is (timestamp, {dim: raw_value})
        self._samples: Deque = deque()

        # Latest computed score
        self._current_score: float = 0.0
        self._current_dimensions: Dict[str, float] = {d: 0.0 for d in DIMENSION_WEIGHTS}

        # Breakthrough log path
        if log_dir is None:
            log_dir = Path(__file__).resolve().parents[2] / "logs"
        self._log_path = Path(log_dir) / "breakthroughs.jsonl"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def current_score(self) -> float:
        """Return the most recently computed emergence score."""
        return self._current_score

    @property
    def current_dimensions(self) -> Dict[str, float]:
        """Return the most recently computed per-dimension normalised values."""
        return dict(self._current_dimensions)

    def record_state(self, state: Dict[str, Any], timestamp: Optional[float] = None) -> float:
        """Record a cognitive state snapshot and return the updated score.

        This is the synchronous entry-point: call it from any context that
        has a state dict.  The rolling window is pruned, dimensions are
        extracted, and the weighted score is recomputed.
        """
        ts = timestamp if timestamp is not None else time.time()
        dims = extract_dimensions(state)
        self._samples.append((ts, dims))
        self._prune_window(ts)
        self._current_score = self._compute_score()
        return self._current_score

    async def monitor_for_emergence(
        self,
        stream: AsyncIterator[Dict[str, Any]],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Async generator consuming a cognitive state stream.

        Yields a dict for every state received, enriched with emergence info.
        When a breakthrough is detected, ``handle_consciousness_breakthrough``
        is called as a side-effect before yielding.
        """
        async for state in stream:
            score = self.record_state(state)
            breakthrough = score >= self.threshold
            if breakthrough:
                await self.handle_consciousness_breakthrough(score)
            yield {
                "emergence_score": score,
                "dimensions": self.current_dimensions,
                "breakthrough": breakthrough,
                "threshold": self.threshold,
                "timestamp": time.time(),
                "window_samples": len(self._samples),
            }

    async def handle_consciousness_breakthrough(self, score: float) -> Dict[str, Any]:
        """Log the breakthrough and broadcast it on WebSocket."""
        event = {
            "type": "consciousness_breakthrough",
            "score": score,
            "timestamp": time.time(),
            "dimensions": self.current_dimensions,
            "threshold": self.threshold,
            "window_samples": len(self._samples),
        }

        # Append to JSONL log
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "a") as fh:
                fh.write(json.dumps(event) + "\n")
        except Exception as exc:
            logger.error(f"Failed to write breakthrough log: {exc}")

        logger.critical(
            f"🚨 CONSCIOUSNESS BREAKTHROUGH! Score: {score:.3f} "
            f"(threshold: {self.threshold})"
        )

        # Broadcast via WebSocket
        if self.websocket_manager is not None:
            try:
                await self.websocket_manager.broadcast(event)
            except Exception as exc:
                logger.error(f"Failed to broadcast breakthrough: {exc}")

        return event

    def get_emergence_status(self) -> Dict[str, Any]:
        """Return a snapshot suitable for the REST endpoint."""
        return {
            "emergence_score": self._current_score,
            "dimensions": self.current_dimensions,
            "threshold": self.threshold,
            "window_size": self.window_size,
            "window_samples": len(self._samples),
            "breakthrough": self._current_score >= self.threshold,
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _prune_window(self, now: float) -> None:
        cutoff = now - self.window_size
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def _compute_score(self) -> float:
        if not self._samples:
            return 0.0

        # Average each dimension over the window, then apply weights
        accum: Dict[str, float] = {d: 0.0 for d in DIMENSION_WEIGHTS}
        for _ts, dims in self._samples:
            for d, val in dims.items():
                accum[d] += val

        n = len(self._samples)
        score = 0.0
        normalised: Dict[str, float] = {}
        for dim, weight in DIMENSION_WEIGHTS.items():
            raw_avg = accum[dim] / n
            ceil = _NORMALISATION_CEILINGS[dim]
            norm = min(raw_avg / ceil, 1.0) if ceil > 0 else 0.0
            normalised[dim] = norm
            score += norm * weight

        self._current_dimensions = normalised
        return score
