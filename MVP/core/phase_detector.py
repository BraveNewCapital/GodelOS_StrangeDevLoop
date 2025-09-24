"""
PhaseDetector: Lightweight phase transition and discontinuity detection component.

This implementation restores the interface expected by other GödelOS MVP modules
and the CLI. It focuses on detecting potential "phase transitions" in a time
series of consciousness-related metrics (e.g., coherence c_n) via multiple
heuristics:

Returned dictionary keys (stable API):
    p_ks                  : KS test p-value between first and second halves
    ks_discontinuity      : bool; True if p_ks < 0.01
    delta_c               : max absolute step change in c_n
    delta_c_series        : list of absolute per-step deltas
    tau_c                 : empirical baseline threshold (2 * std of baseline deltas)
    adaptive_tau          : adaptive threshold scaling with sample count
    coherence_threshold   : max(tau_c, adaptive_tau)
    transition_coherence  : bool; True if delta_c > coherence_threshold
    b_n                   : temporal binding aggregate (simplified heuristic)
    transition_binding    : bool; binding threshold exceeded
    d_js_goal             : Jensen–Shannon distance between goal distributions (if provided)
    transition_goal       : bool; goal shift threshold exceeded
    transition_resistance : bool; meta-resistance threshold exceeded
    significant_transition: bool OR over above transition flags / discontinuity
    statsmodels_used      : bool; whether statsmodels normality test was applied
    normality_p           : normality test p-value (1.0 if not applicable)

Graceful Degradation:
- statsmodels is optional. If unavailable, a scipy alternative (normaltest) is used.
- All failures return safe defaults without raising, preserving stability.

Usage:
    detector = PhaseDetector()
    result = detector.detect_phases({"c_n": [...], "phi_n": [...]})
"""

from __future__ import annotations

import numpy as np
from typing import List, Dict, Any, Optional

# SciPy for statistical tests (assumed present in environment)
try:
    from scipy.stats import ks_2samp, entropy, normaltest
except Exception:  # pragma: no cover
    ks_2samp = None
    entropy = None
    normaltest = None

# Optional statsmodels (normality diagnostics)
try:
    import statsmodels.api as sm  # type: ignore
    from statsmodels.stats.diagnostic import kstest_normal  # type: ignore
    _STATSMODELS_AVAILABLE = True
except Exception:  # pragma: no cover
    sm = None  # type: ignore
    kstest_normal = None  # type: ignore
    _STATSMODELS_AVAILABLE = False


def _safe_entropy(p: np.ndarray, q: np.ndarray) -> float:
    """Safe Jensen–Shannon divergence component using scipy entropy."""
    if entropy is None:
        return 0.0
    m = 0.5 * (p + q)
    div = 0.5 * entropy(p, m) + 0.5 * entropy(q, m)
    if not np.isfinite(div):
        return 0.0
    return float(div)


def jensen_shannon_distance(p: np.ndarray, q: np.ndarray) -> float:
    """Compute Jensen–Shannon distance (non-negative, symmetric)."""
    try:
        p = np.asarray(p, dtype=float)
        q = np.asarray(q, dtype=float)

        if p.size == 0 or q.size == 0:
            return 0.0

        eps = 1e-10
        p = p + eps
        q = q + eps

        p_sum = p.sum()
        q_sum = q.sum()
        if p_sum <= 0 or q_sum <= 0:
            return 0.0

        p /= p_sum
        q /= q_sum

        js_div = _safe_entropy(p, q)
        return float(js_div) if js_div >= 0 and np.isfinite(js_div) else 0.0
    except Exception:
        return 0.0


class PhaseDetector:
    """Restored PhaseDetector with a stable detect_phases() interface."""

    def __init__(
        self,
        baseline_simulations: int = 100,
        sigma_kl: float = 0.1,
        min_coherence_tau: float = 0.05,
        verbose: bool = False,
    ):
        self.baseline_simulations = max(10, baseline_simulations)
        self.sigma_kl = sigma_kl
        self.min_coherence_tau = min_coherence_tau
        self.verbose = verbose

        self.baseline_deltas: np.ndarray = np.array([], dtype=float)
        self.tau_c: float = 2 * sigma_kl  # Will be updated after baseline simulation
        self.statsmodels_available = _STATSMODELS_AVAILABLE

    # ------------------------------------------------------------------
    # Baseline / Threshold Calculations
    # ------------------------------------------------------------------
    def simulate_baselines(self, coherence_history: Optional[List[float]]) -> None:
        """Generate baseline delta distribution from either history or synthetic noise."""
        try:
            if not coherence_history or len(coherence_history) < 6:
                # Synthetic baseline with small random walk in [0,1]
                deltas_all = []
                for _ in range(self.baseline_simulations):
                    seq = [np.clip(0.3 + np.random.normal(0, 0.05), 0.0, 1.0)]
                    for _ in range(10):
                        seq.append(
                            np.clip(
                                seq[-1] + np.random.normal(0, self.sigma_kl),
                                0.0,
                                1.0,
                            )
                        )
                    deltas_all.extend(np.abs(np.diff(seq)).tolist())
                self.baseline_deltas = np.array(deltas_all, dtype=float)
            else:
                c_vals = np.asarray(coherence_history, dtype=float)
                deltas = np.abs(np.diff(c_vals))
                if deltas.size == 0:
                    self.baseline_deltas = np.array([0.0])
                else:
                    boots = []
                    for _ in range(self.baseline_simulations):
                        sample = np.random.choice(deltas, size=deltas.size, replace=True)
                        boots.extend(sample.tolist())
                    self.baseline_deltas = np.array(boots, dtype=float)

            # Empirical threshold
            std = float(np.std(self.baseline_deltas)) if self.baseline_deltas.size else 0.05
            self.tau_c = max(self.min_coherence_tau, 2 * std)
        except Exception:
            # Fallback
            self.baseline_deltas = np.array([0.05])
            self.tau_c = max(self.min_coherence_tau, 0.1)

    def adaptive_tau(self, n: int) -> float:
        """Adaptive coherence threshold (log-scaled)."""
        n = max(1, n)
        return float(np.clip(0.1 + 0.08 * np.log1p(n), 0.05, 0.35))

    # ------------------------------------------------------------------
    # Statistical & Feature Extractors
    # ------------------------------------------------------------------
    def ks_test_discontinuity(self, pre: np.ndarray, post: np.ndarray) -> float:
        if ks_2samp is None or pre.size < 3 or post.size < 3:
            return 1.0
        try:
            _, p = ks_2samp(pre, post)
            return float(p)
        except Exception:
            return 1.0

    def distribution_normality_pvalue(self, series: List[float]) -> float:
        arr = np.asarray(series, dtype=float)
        if arr.size < 8:  # normaltest requires n >= 8
            return 1.0
        # Prefer statsmodels if present
        if self.statsmodels_available and kstest_normal is not None:
            try:
                _, p = kstest_normal(arr)
                return float(p)
            except Exception:
                pass
        if normaltest is not None:
            try:
                _, p = normaltest(arr)
                return float(p)
            except Exception:
                return 1.0
        return 1.0

    def coherence_jump(self, c_n: List[float]) -> float:
        if len(c_n) < 2:
            return 0.0
        deltas = np.diff(np.asarray(c_n, dtype=float))
        if deltas.size == 0:
            return 0.0
        return float(np.max(np.abs(deltas)))

    def temporal_binding(
        self,
        taus: Optional[List[float]],
        mutual_infos: Optional[List[float]],
        sigma_t: float = 200.0,
    ) -> float:
        if not taus or not mutual_infos:
            return 0.0
        try:
            t_arr = np.asarray(taus, dtype=float)
            mi_arr = np.asarray(mutual_infos, dtype=float)
            n = len(t_arr)
            acc = 0.0
            for i in range(n):
                for j in range(i + 1, n):
                    k = np.exp(-((t_arr[i] - t_arr[j]) ** 2) / (2 * sigma_t**2))
                    acc += k * mi_arr[min(i, j)]
            return float(acc / n)
        except Exception:
            return 0.0

    def goal_emergence(
        self,
        g_new: Optional[np.ndarray],
        g_prior: Optional[np.ndarray],
        min_threshold: float = 0.3,
    ) -> float:
        if g_new is None or g_prior is None:
            return 0.0
        try:
            g_new_f = np.asarray(g_new, dtype=float).flatten()
            g_prior_f = np.asarray(g_prior, dtype=float).flatten()
            if g_new_f.size == 0 or g_prior_f.size == 0:
                return 0.0
            d_js = jensen_shannon_distance(g_new_f, g_prior_f)
            return float(d_js if d_js > min_threshold else 0.0)
        except Exception:
            return 0.0

    def meta_resistance(
        self,
        q_n: Optional[List[float]],
        baseline_q: float,
        sigma_q: float = 1.0,
    ) -> bool:
        if not q_n:
            return False
        try:
            mean_q = float(np.mean(q_n))
            return bool(mean_q > baseline_q + 3 * sigma_q)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Main Detection
    # ------------------------------------------------------------------
    def detect_phases(
        self,
        metrics: Dict[str, List[float]],
        taus: Optional[List[float]] = None,
        mutual_infos: Optional[List[float]] = None,
        g_new: Optional[np.ndarray] = None,
        g_prior: Optional[np.ndarray] = None,
        q_n: Optional[List[float]] = None,
        baseline_q: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Primary public API. Accepts metric histories, returns transition indicators.
        """
        try:
            c_n = metrics.get("c_n", []) or []
            phi_n = metrics.get("phi_n", []) or []
            self.simulate_baselines(coherence_history=c_n)

            c_arr = np.asarray(c_n, dtype=float)
            mid = len(c_arr) // 2
            pre = c_arr[:mid]
            post = c_arr[mid:]
            p_ks = self.ks_test_discontinuity(pre, post)

            delta_series = np.abs(np.diff(c_arr)) if c_arr.size >= 2 else np.array([])
            delta_c = float(np.max(delta_series)) if delta_series.size else 0.0

            tau_adapt = self.adaptive_tau(len(c_arr))
            coherence_threshold = max(self.tau_c, tau_adapt)
            transition_c = delta_c > coherence_threshold

            b_n = self.temporal_binding(taus, mutual_infos)
            binding_threshold = np.log(1 + len(phi_n) / 10) if phi_n else 0.0
            transition_binding = b_n > binding_threshold

            d_js_val = self.goal_emergence(g_new, g_prior)
            transition_goal = d_js_val > 0.3

            transition_resistance = self.meta_resistance(q_n, baseline_q)

            normality_p = self.distribution_normality_pvalue(c_n)

            significant = bool(
                (p_ks < 0.01)
                or transition_c
                or transition_binding
                or transition_goal
                or transition_resistance
            )

            return {
                "p_ks": float(p_ks),
                "ks_discontinuity": bool(p_ks < 0.01),
                "delta_c": float(delta_c),
                "delta_c_series": delta_series.tolist() if delta_series.size else [],
                "tau_c": float(self.tau_c),
                "adaptive_tau": float(tau_adapt),
                "coherence_threshold": float(coherence_threshold),
                "transition_coherence": bool(transition_c),
                "b_n": float(b_n),
                "transition_binding": bool(transition_binding),
                "d_js_goal": float(d_js_val),
                "transition_goal": bool(transition_goal),
                "transition_resistance": bool(transition_resistance),
                "significant_transition": bool(significant),
                "statsmodels_used": bool(self.statsmodels_available),
                "normality_p": float(normality_p),
            }
        except Exception as e:
            # Fallback result structure to avoid caller breakage
            return {
                "p_ks": 1.0,
                "ks_discontinuity": False,
                "delta_c": 0.0,
                "delta_c_series": [],
                "tau_c": float(self.tau_c),
                "adaptive_tau": self.adaptive_tau(1),
                "coherence_threshold": float(self.tau_c),
                "transition_coherence": False,
                "b_n": 0.0,
                "transition_binding": False,
                "d_js_goal": 0.0,
                "transition_goal": False,
                "transition_resistance": False,
                "significant_transition": False,
                "statsmodels_used": bool(self.statsmodels_available),
                "normality_p": 1.0,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        return {
            "baseline_simulations": self.baseline_simulations,
            "sigma_kl": self.sigma_kl,
            "tau_c_current": self.tau_c,
            "statsmodels_available": self.statsmodels_available,
        }


__all__ = [
    "PhaseDetector",
    "jensen_shannon_distance",
]
