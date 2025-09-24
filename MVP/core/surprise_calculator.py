import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import List, Optional, Tuple, Dict, Any

# Optional statsmodels import (graceful degradation if missing)
try:
    import statsmodels.api as sm  # type: ignore
    _STATSMODELS_AVAILABLE = True
except Exception:
    sm = None  # type: ignore
    _STATSMODELS_AVAILABLE = False


class AutoregressiveModel(nn.Module):
    """
    Minimal autoregressive predictor used to derive a phenomenological
    'prediction error' component for phenomenal surprise.

    This is intentionally lightweight; deeper modeling belongs in a
    dedicated temporal modeling module.
    """
    def __init__(self, state_dim: int = 512, hidden_dim: int = 256, num_layers: int = 2):
        super().__init__()
        self.lstm = nn.LSTM(state_dim, hidden_dim, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_dim, state_dim)
        self.softmax = nn.Softmax(dim=-1)

    def forward(self, states: torch.Tensor):
        """
        states: (batch, seq_len, state_dim)
        Returns a probability distribution over the next state's dimensions.
        """
        lstm_out, _ = self.lstm(states)
        out = self.fc(lstm_out[:, -1, :])
        return self.softmax(out)


class SurpriseCalculator:
    """
    Computes multiple components related to phenomenal surprise (P_n) and
    associated irreducibility characteristics.

    Statsmodels dependency:
      - If statsmodels is available, AIC/BIC are computed via OLS fits.
      - If not, a NumPy fallback computes closed‑form OLS + Gaussian likelihood
        to approximate AIC/BIC. If even that fails, NaNs are returned.

    Public methods preserved for compatibility:
      - train_on_states
      - compute_surprise
      - filter_noise
      - compute_aic_bic
      - is_irreducible
      - compute_error_entropy
      - calculate_p_n

    The overall design keeps side‑effects (prints) minimal; callers can
    inspect `self.statsmodels_available`.
    """

    def __init__(
        self,
        state_dim: int = 512,
        baseline_noise: float = 0.1,
        lr: float = 1e-3,
        device: Optional[str] = None,
        use_statsmodels: bool = True,
        verbose: bool = False
    ):
        self.state_dim = state_dim
        self.baseline_noise = baseline_noise
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model = AutoregressiveModel(state_dim).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        self.entropy_baseline = -np.log(self.baseline_noise)
        self.statsmodels_requested = use_statsmodels
        self.statsmodels_available = _STATSMODELS_AVAILABLE and use_statsmodels
        self.verbose = verbose

        if self.verbose:
            print(f"[SurpriseCalculator] statsmodels_available={self.statsmodels_available}")

    # ------------------------------------------------------------------
    # Training (lightweight / illustrative)
    # ------------------------------------------------------------------
    def train_on_states(self, states: List[torch.Tensor], epochs: int = 10):
        """
        Very lightweight training loop; expects each tensor shape (state_dim,)
        and will internally batch them as a single sequence.
        """
        if len(states) < 2:
            if self.verbose:
                print("[SurpriseCalculator] Not enough states to train.")
            return

        states_tensor = torch.stack(states).unsqueeze(0).to(self.device)  # (1, seq_len, dim)
        for epoch in range(epochs):
            self.optimizer.zero_grad()
            preds = self.model(states_tensor[:, :-1])  # Predict next from all but last
            targets = states_tensor[:, 1:].argmax(dim=-1)  # Simplified discrete target
            loss = F.cross_entropy(preds, targets)
            loss.backward()
            self.optimizer.step()
            if self.verbose:
                print(f"[SurpriseCalculator] Epoch {epoch+1}/{epochs} Loss: {loss.item():.4f}")

    # ------------------------------------------------------------------
    # Core surprise calculation
    # ------------------------------------------------------------------
    def compute_surprise(self, states: List[torch.Tensor]) -> float:
        """
        Phenomenal surprise P_n based on:
          - Mean squared prediction deviation between consecutive states
          - Entropy component derived from intra-state variance

        Returns P_n >= 0.0
        """
        if len(states) < 2:
            return 0.0

        # Move tensors to CPU for numpy ops
        state_arrays = [s.detach().cpu().numpy() for s in states]

        surprises: List[float] = []
        for i in range(len(state_arrays) - 1):
            current_state = state_arrays[i]
            next_state = state_arrays[i + 1]

            prediction_error = float(np.mean((next_state - current_state) ** 2))
            state_variance = float(np.var(current_state))
            entropy_component = -np.log(1.0 / (1.0 + state_variance + 1e-9))
            surprise = prediction_error + entropy_component
            surprises.append(surprise)

        avg_surprise = float(np.mean(surprises)) if surprises else 0.0
        state_complexity = float(np.mean([np.std(s) for s in state_arrays]))

        # Add mild stochasticity to avoid degenerate flat scores
        final_surprise = avg_surprise * (1.0 + state_complexity) + float(np.random.normal(0, 0.5))
        return max(0.0, final_surprise)

    # ------------------------------------------------------------------
    # Noise filtering (placeholder smoothing)
    # ------------------------------------------------------------------
    def filter_noise(self, states: List[torch.Tensor]) -> List[torch.Tensor]:
        if not states:
            return []
        smoothed = [states[0]]
        for s in states[1:]:
            smoothed.append(0.8 * smoothed[-1] + 0.2 * s)
        return smoothed

    # ------------------------------------------------------------------
    # AIC / BIC with optional statsmodels
    # ------------------------------------------------------------------
    def compute_aic_bic(self, model: Any, X: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
        """
        Compute (AIC, BIC).

        Preferred path:
            statsmodels OLS -> uses sm.OLS(y, sm.add_constant(X))
        Fallback path (no statsmodels):
            Closed form OLS via normal equations + Gaussian log-likelihood.

        On any fatal error returns (nan, nan).
        """
        try:
            X = np.asarray(X, dtype=float)
            y = np.asarray(y, dtype=float)
            if X.ndim == 1:
                X = X.reshape(-1, 1)

            if self.statsmodels_available:
                sm_model = sm.OLS(y, sm.add_constant(X)).fit()
                return float(sm_model.aic), float(sm_model.bic)

            # NumPy fallback
            n = y.shape[0]
            X_aug = np.hstack([np.ones((n, 1)), X])  # add intercept
            XtX = X_aug.T @ X_aug
            # Regularize if singular
            if np.linalg.cond(XtX) > 1e12:
                XtX += np.eye(XtX.shape[0]) * 1e-6
            beta = np.linalg.pinv(XtX) @ X_aug.T @ y
            residuals = y - X_aug @ beta
            rss = float(np.sum(residuals ** 2))
            k = X_aug.shape[1]
            if n <= k:
                return float("nan"), float("nan")
            sigma2 = rss / n
            # Gaussian log-likelihood
            logL = -0.5 * n * (np.log(2 * np.pi * sigma2) + 1)
            aic = 2 * k - 2 * logL
            bic = k * np.log(n) - 2 * logL
            return float(aic), float(bic)
        except Exception as e:
            if self.verbose:
                print(f"[SurpriseCalculator] AIC/BIC computation failed: {e}")
            return float("nan"), float("nan")

    # ------------------------------------------------------------------
    # Irreducibility heuristic
    # ------------------------------------------------------------------
    def is_irreducible(self, states: List[torch.Tensor], max_layers: int = 4) -> float:
        """
        Heuristic irreducibility score in [0,1].

        Present implementation:
          - Uses average absolute consecutive state difference (complexity)
          - Adds entropy over normalized differences as transition entropy
          - Injects light noise
        """
        if len(states) < 2:
            return 0.0

        initial_surprise = self.compute_surprise(states)  # currently unused but kept for parity

        state_arrays = [s.detach().cpu().numpy() for s in states]
        complexity_scores: List[float] = []
        for i in range(len(state_arrays) - 1):
            state_diff = float(np.mean(np.abs(state_arrays[i+1] - state_arrays[i])))
            complexity_scores.append(state_diff)

        avg_complexity = float(np.mean(complexity_scores)) if complexity_scores else 0.5

        transition_entropy = 0.0
        for i in range(len(state_arrays) - 1):
            diff = np.abs(state_arrays[i+1] - state_arrays[i])
            denom = float(np.sum(diff))
            if denom > 0:
                norm_diff = diff / denom
                transition_entropy += -float(np.sum(norm_diff * np.log(norm_diff + 1e-10)))

        irreducibility = min(1.0, avg_complexity * (1.0 + transition_entropy / max(1, len(states))))
        noise = float(np.random.normal(0, 0.1))
        final_irreducibility = max(0.0, min(1.0, irreducibility + noise))
        return final_irreducibility

    # ------------------------------------------------------------------
    # Error entropy
    # ------------------------------------------------------------------
    def compute_error_entropy(self, errors: np.ndarray) -> float:
        hist, _ = np.histogram(errors, bins=10, density=True)
        hist = hist[hist > 0]
        if hist.size == 0:
            return 0.0
        return float(-np.sum(hist * np.log2(hist + 1e-10)))

    # ------------------------------------------------------------------
    # Composite P_n + related metrics
    # ------------------------------------------------------------------
    def calculate_p_n(self, states: List[torch.Tensor], model_expansions: int = 10) -> Dict[str, Any]:
        """
        Returns a dictionary of:
          p_n: phenomenal surprise
          h_error: entropy of synthetic error distribution
          irreducible: irreducibility heuristic
          persistence_ratio: (p_n / raw_surprise) > threshold
          statsmodels_used: bool
        """
        if not states:
            return {
                "p_n": 0.0,
                "h_error": 0.0,
                "irreducible": 0.0,
                "persistence_ratio": False,
                "statsmodels_used": False
            }

        smoothed = self.filter_noise(states)
        p_n = self.compute_surprise(smoothed)
        raw_surprise = self.compute_surprise(states) or 1e-9

        # Placeholder synthetic errors (would be model residuals in full system)
        errors = np.random.normal(0, 1, len(states))
        h_error = self.compute_error_entropy(errors)
        irreducible = self.is_irreducible(smoothed)
        persistence = (p_n / raw_surprise) > 0.8

        return {
            "p_n": float(p_n),
            "h_error": float(h_error),
            "irreducible": float(irreducible),
            "persistence_ratio": bool(persistence),
            "statsmodels_used": bool(self.statsmodels_available)
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        return {
            "state_dim": self.state_dim,
            "baseline_noise": self.baseline_noise,
            "statsmodels_requested": self.statsmodels_requested,
            "statsmodels_available": self.statsmodels_available
        }


__all__ = ["SurpriseCalculator", "AutoregressiveModel"]
