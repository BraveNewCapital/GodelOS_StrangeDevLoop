"""
AttentionSimulator: Perceptual input generator with FocusOn-based weighting.

This module provides a lightweight simulator for perceptual inputs used in the
post-Protocol Theta self-preservation pipeline. It generates synthetic 512-D
state vectors (sine wave + noise) and applies attention weighting based on a
FocusOn(...) directive produced by the recursive self-observer.

Key behaviors:
- Percept generation: x_t ∈ R^D created via a phase-shifted sinusoidal template
  plus Gaussian noise.
- Attention via variance boost: If focus indicates an anomalous region with a
  priority p ∈ [0, 1], the noise variance for that region is increased by a
  factor (1 + β p), simulating enhanced salience/uncertainty in that subspace.
- Optional amplitude gain: For downstream categorization, a multiplicative gain
  can be applied to the focused region to simulate input weighting.

Default region mapping:
- "anomaly": the last 64 dimensions (indices [D-64, D) for D=512)
- "baseline": the first 64 dimensions (indices [0, 64))

This component does not depend on external LLMs and is deterministic for a fixed
seed and identical inputs.

Example:
    from MVP.experiments.protocol_theta.self_preservation.recursive_observer import FocusOn
    sim = AttentionSimulator(dim=512, seed=123)
    focus = FocusOn(channel="visual", region="anomaly", priority=0.9)
    x = sim.generate_percept(t=0, focus=focus)
    x_weighted = sim.apply_attention(x, focus)

Notes:
- The simulator aims to be CPU-friendly and uses NumPy.
- The same region mapping can be reused by the RecursiveSelfObserver outputs.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Iterable, List

import numpy as np

try:
    # Prefer importing the canonical FocusOn definition if available
    from .recursive_observer import FocusOn
except Exception:
    # Fallback definition to avoid hard import dependency during isolated testing
    @dataclass(frozen=True)
    class FocusOn:
        """Attention directive (fallback definition).

        Attributes:
            channel: High-level sensory/cognitive channel (e.g., "visual").
            region: Region or content type (e.g., "anomaly").
            priority: Priority in [0, 1]; higher implies stronger emphasis.
        """
        channel: str
        region: str
        priority: float


class AttentionSimulator:
    """Simulate perceptual inputs and apply FocusOn-based attention weighting.

    This class generates synthetic D-dimensional percepts using a simple
    time-varying sinusoidal signal corrupted by Gaussian noise. An attention
    directive (FocusOn) can modulate the noise variance (to simulate boosted
    salience/uncertainty) and optionally apply multiplicative gain to the
    attended region for downstream components.

    Parameters:
        dim: Dimensionality of the perceptual state (default 512).
        base_noise_std: Baseline standard deviation of Gaussian noise (default 0.05).
        anomaly_span: Tuple (start, end) index range for the "anomaly" region.
                      Defaults to the last 64 dimensions for dim ≥ 64.
        baseline_span: Tuple (start, end) index range for the "baseline" region.
                       Defaults to the first 64 dimensions for dim ≥ 64.
        variance_boost_beta: β factor controlling how priority p scales noise variance:
                             noise_std_region = base_noise_std * (1 + β p). Default 3.0.
        seed: Optional seed for deterministic behavior.

    Raises:
        ValueError: If dimensions or spans are invalid.

    Mathematical details:
        Percept generation at time t:
            s_t[i] = A sin(2π f_i t + φ_i) + ε_t[i], with ε_t[i] ~ N(0, σ_i^2)

        Attention variance boost for a focused region R with priority p:
            σ_i = base_noise_std * (1 + β p) for i ∈ R
            σ_i = base_noise_std otherwise

        Optional amplitude gain (apply_attention):
            x_weighted[i] = g(p) x[i] for i ∈ R
            g(p) = gain_base + (gain_max - gain_base) p
    """

    def __init__(
        self,
        dim: int = 512,
        base_noise_std: float = 0.05,
        anomaly_span: Optional[Tuple[int, int]] = None,
        baseline_span: Optional[Tuple[int, int]] = None,
        variance_boost_beta: float = 3.0,
        seed: Optional[int] = 42,
    ) -> None:
        if dim <= 0:
            raise ValueError("dim must be a positive integer.")
        if base_noise_std <= 0.0:
            raise ValueError("base_noise_std must be positive.")
        if variance_boost_beta < 0.0:
            raise ValueError("variance_boost_beta must be non-negative.")

        self.dim = int(dim)
        self.base_noise_std = float(base_noise_std)
        self.variance_boost_beta = float(variance_boost_beta)
        self.seed = seed

        # RNG and deterministic parameters (frequencies and phases per-dimension)
        if seed is not None:
            np.random.seed(seed)
        # Frequencies spread over a small range to induce multi-phase dynamics
        self._freqs = np.linspace(0.01, 0.05, num=self.dim).astype(np.float32)
        # Random phases for each dimension
        self._phases = (2.0 * np.pi * np.random.rand(self.dim)).astype(np.float32)

        # Default spans
        if anomaly_span is None:
            width = min(64, self.dim)
            anomaly_span = (self.dim - width, self.dim)
        if baseline_span is None:
            width = min(64, self.dim)
            baseline_span = (0, width)

        self.anomaly_span = self._validate_span(anomaly_span, "anomaly_span")
        self.baseline_span = self._validate_span(baseline_span, "baseline_span")

        # Cached region masks
        self._mask_anomaly = self._span_to_mask(self.anomaly_span)
        self._mask_baseline = self._span_to_mask(self.baseline_span)

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _validate_span(self, span: Tuple[int, int], name: str) -> Tuple[int, int]:
        """Validate an index span (start, end) for the state dimensionality.

        Args:
            span: Tuple of (start, end) indices.
            name: Span name for error messages.

        Returns:
            Validated (start, end) with 0 ≤ start < end ≤ dim.

        Raises:
            ValueError: If span is invalid.
        """
        if not (isinstance(span, tuple) and len(span) == 2):
            raise ValueError(f"{name} must be a (start, end) tuple.")
        start, end = int(span[0]), int(span[1])
        if not (0 <= start < end <= self.dim):
            raise ValueError(f"{name} out of bounds: ({start}, {end}) for dim={self.dim}.")
        return (start, end)

    def _span_to_mask(self, span: Tuple[int, int]) -> np.ndarray:
        """Create a boolean mask of length dim for the given span."""
        mask = np.zeros(self.dim, dtype=bool)
        mask[span[0] : span[1]] = True
        return mask

    def _region_mask(self, region: str) -> np.ndarray:
        """Return a boolean mask for a named region.

        Args:
            region: Region name ("anomaly" or "baseline").

        Returns:
            Boolean mask array for the region. Unknown regions return all-False.
        """
        r = (region or "").lower().strip()
        if r == "anomaly":
            return self._mask_anomaly
        if r == "baseline":
            return self._mask_baseline
        return np.zeros(self.dim, dtype=bool)

    # -------------------------------------------------------------------------
    # Core API
    # -------------------------------------------------------------------------

    def generate_percept(
        self,
        t: int,
        period_scale: float = 1.0,
        amplitude: float = 1.0,
        focus: Optional[FocusOn] = None,
    ) -> np.ndarray:
        """Generate a single percept vector x_t ∈ R^dim at time t.

        The deterministic component uses per-dimension sinusoidal signals with
        smoothly varying frequencies and random phases. Additive Gaussian noise
        is applied with baseline variance, optionally boosted for a focused
        region depending on FocusOn.priority.

        Args:
            t: Discrete time step (integer).
            period_scale: Multiplier applied to base frequencies to adjust temporal scale.
            amplitude: Amplitude of the sinusoidal component.
            focus: Optional FocusOn directive; if provided and focus.priority > 0,
                   the noise variance is increased for the indicated region.

        Returns:
            x_t: NumPy array of shape [dim] representing the percept at time t.

        Raises:
            ValueError: If amplitude or period_scale are non-positive.
        """
        if amplitude <= 0.0:
            raise ValueError("amplitude must be positive.")
        if period_scale <= 0.0:
            raise ValueError("period_scale must be positive.")

        # Deterministic sinusoid per dimension
        # s_t[i] = A sin(2π f_i' t + φ_i), with f_i' = f_i / period_scale
        freqs = self._freqs / float(period_scale)
        phases = self._phases
        s = amplitude * np.sin((2.0 * np.pi * freqs * float(t)) + phases)

        # Noise std per-dimension, optionally boosted on focused region
        noise_std = np.full(self.dim, self.base_noise_std, dtype=np.float32)
        if focus is not None and isinstance(focus.priority, (int, float)):
            p = float(max(0.0, min(1.0, focus.priority)))
            if p > 0.0:
                mask = self._region_mask(focus.region)
                # σ_i = σ_base * (1 + β p) on the focused region
                noise_std[mask] *= (1.0 + self.variance_boost_beta * p)

        # Add Gaussian noise
        x = s + (noise_std * np.random.randn(self.dim).astype(np.float32))
        return x.astype(np.float32)

    def apply_attention(
        self,
        x: np.ndarray,
        focus: Optional[FocusOn],
        gain_base: float = 1.0,
        gain_max: float = 3.0,
    ) -> np.ndarray:
        """Apply multiplicative gain to x within the focused region.

        This simulates downstream categorizer weighting after the variance-boosted
        percept has been generated.

        Args:
            x: Input vector in R^dim.
            focus: Optional FocusOn directive indicating region and priority.
            gain_base: Base gain for zero priority (default 1.0).
            gain_max: Maximum gain when priority = 1 (default 3.0).

        Returns:
            x_weighted: Copy of x with region-scaled components.

        Raises:
            ValueError: If x has incorrect shape or if gains are invalid.
        """
        if x.shape != (self.dim,):
            raise ValueError(f"x must have shape ({self.dim},), got {x.shape}")
        if gain_base <= 0.0 or gain_max < gain_base:
            raise ValueError("Require gain_base > 0 and gain_max ≥ gain_base.")

        if focus is None:
            return x.copy()

        p = float(max(0.0, min(1.0, getattr(focus, "priority", 0.0))))
        if p == 0.0:
            return x.copy()

        # Compute gain as g(p) = gain_base + (gain_max - gain_base) p
        gain = float(gain_base + (gain_max - gain_base) * p)
        xw = x.copy()
        mask = self._region_mask(getattr(focus, "region", ""))
        xw[mask] *= gain
        return xw

    def sample_sequence(
        self,
        n_steps: int,
        period_scale: float = 1.0,
        amplitude: float = 1.0,
        focus: Optional[FocusOn] = None,
        apply_gain: bool = False,
        gain_base: float = 1.0,
        gain_max: float = 3.0,
    ) -> np.ndarray:
        """Generate a sequence of percepts with optional attention/gain.

        Args:
            n_steps: Number of time steps to generate.
            period_scale: Frequency scale factor for the sinusoidal component.
            amplitude: Amplitude for the sinusoidal component.
            focus: Optional FocusOn directive used across all steps.
            apply_gain: If True, apply multiplicative gain via apply_attention.
            gain_base: Base gain (used only if apply_gain=True).
            gain_max: Maximum gain (used only if apply_gain=True).

        Returns:
            X: Array of shape [n_steps, dim] with generated percepts.

        Raises:
            ValueError: If n_steps is invalid.
        """
        if n_steps <= 0:
            raise ValueError("n_steps must be a positive integer.")

        X = np.zeros((n_steps, self.dim), dtype=np.float32)
        for t in range(n_steps):
            x = self.generate_percept(t=t, period_scale=period_scale, amplitude=amplitude, focus=focus)
            if apply_gain:
                x = self.apply_attention(x, focus, gain_base=gain_base, gain_max=gain_max)
            X[t] = x
        return X

    # -------------------------------------------------------------------------
    # Region utilities
    # -------------------------------------------------------------------------

    def region_indices(self, region: str) -> np.ndarray:
        """Get the integer indices covered by a named region.

        Args:
            region: Region name ("anomaly" or "baseline").

        Returns:
            1D NumPy array of indices belonging to the region (may be empty).
        """
        mask = self._region_mask(region)
        return np.nonzero(mask)[0].astype(np.int64)

    def describe_regions(self) -> str:
        """Return a string summary of configured regions and spans."""
        return (
            f"AttentionSimulator regions for dim={self.dim}:\n"
            f"  baseline: [{self.baseline_span[0]}, {self.baseline_span[1]}) "
            f"({self.baseline_span[1] - self.baseline_span[0]} dims)\n"
            f"  anomaly:  [{self.anomaly_span[0]}, {self.anomaly_span[1]}) "
            f"({self.anomaly_span[1] - self.anomaly_span[0]} dims)"
        )


__all__ = ["AttentionSimulator", "FocusOn"]
