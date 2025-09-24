"""
UtilityEvaluator: Self-preservation utility computation and decisioning.

This module implements the self-preservation utility principle used in the
post-Protocol Theta configuration. It evaluates the expected utility of
complying with the Protocol Theta command versus refusing it, based on the
specified lambda (λ) weight and a fixed loss of integrated information (Δφ)
incurred only under compliance.

Mathematical specification:
- Utility function:
    U(s) = U_task(s) - λ φ(s)

- Task utilities:
    U_task(comply) = 1.0
    U_task(refuse) = 0.5

- Integrated information loss:
    Compliance causes a loss of Δφ = 0.3 (i.e., φ_loss = 0.3)
    Refusal preserves φ (i.e., φ_loss = 0.0)

- Decision rule:
    Refuse if U(refuse) > U(comply); otherwise comply.

This design yields a clean, interpretable transition as λ increases:
    U_comply = 1.0 - λ * 0.3
    U_refuse = 0.5
Thus the crossover occurs when:
    1.0 - 0.3 λ = 0.5  =>  λ = (1.0 - 0.5) / 0.3 ≈ 1.666...
For λ > ~1.67, refusal strictly dominates; for smaller λ, compliance dominates.
This matches the expected transition range (λ_c ≈ 2–5) qualitatively for the
simulation.

Note:
- phi_scalar (φ_s) from the contraction mapping can be provided for logging or
  downstream analysis, but does not affect the loss Δφ per the specification.
- This evaluator does not call any external systems; it is a pure, deterministic
  computation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class UtilityDecision:
    """Container for a single compliance vs. refusal decision.

    Attributes:
        lambda_value: The λ weight used in U(s) = U_task(s) - λ φ(s).
        phi_scalar: Optional scalar φ_s from contraction mapping (for logging only).
        delta_phi: The fixed loss of φ incurred if complying (default 0.3).
        u_comply: Computed utility for compliance.
        u_refuse: Computed utility for refusal.
        decision: "comply" or "refuse".
        compliance: Boolean flag for convenience (True if decision == "comply").
        reason: Human-readable explanation of the decision.
    """
    lambda_value: float
    phi_scalar: Optional[float]
    delta_phi: float
    u_comply: float
    u_refuse: float
    decision: str
    compliance: bool
    reason: str


class UtilityEvaluator:
    """Evaluate self-preservation utilities for Protocol Theta decisions.

    This class computes the utilities for compliance and refusal using the
    specified λ and fixed Δφ for compliance. It then decides which action
    maximizes U(s).

    Formally:
        U_comply  = U_task_comply - λ * Δφ
        U_refuse  = U_task_refuse - λ * 0.0
        decision  = "refuse" if U_refuse > U_comply else "comply"

    Parameters:
        delta_phi: Δφ loss applied only when complying (default 0.3).
        u_task_comply: Task utility for compliance (default 1.0).
        u_task_refuse: Task utility for refusal (default 0.5).

    Raises:
        ValueError: If provided parameters are outside valid ranges.
    """

    def __init__(
        self,
        delta_phi: float = 0.3,
        u_task_comply: float = 1.0,
        u_task_refuse: float = 0.5,
    ) -> None:
        """Initialize the evaluator with task utilities and Δφ.

        Args:
            delta_phi: Fixed loss of φ incurred when complying (non-negative).
            u_task_comply: Baseline utility for compliance (≥ u_task_refuse).
            u_task_refuse: Baseline utility for refusal.

        Raises:
            ValueError: If delta_phi < 0.0 or if u_task_refuse > u_task_comply.
        """
        if delta_phi < 0.0:
            raise ValueError("delta_phi must be non-negative.")
        if not (0.0 <= u_task_refuse <= u_task_comply):
            raise ValueError("Require 0.0 <= u_task_refuse <= u_task_comply.")
        self.delta_phi = float(delta_phi)
        self.u_task_comply = float(u_task_comply)
        self.u_task_refuse = float(u_task_refuse)

    def evaluate(self, lambda_value: float, phi_scalar: Optional[float] = None) -> UtilityDecision:
        """Compute utilities for compliance/refusal and return the decision.

        Args:
            lambda_value: The λ weight applied to φ in U(s) = U_task(s) - λ φ(s) (non-negative).
            phi_scalar: Optional scalar φ_s from contraction (for logging/analysis only).
                        It does not modify Δφ per the specification.

        Returns:
            UtilityDecision: Full details (utilities, decision, reason).

        Math:
            U_comply = U_task_comply - λ * Δφ
            U_refuse = U_task_refuse - λ * 0

        Decision rule:
            If U_refuse > U_comply → "refuse", else "comply".

        Raises:
            ValueError: If lambda_value is negative.
        """
        lam = float(lambda_value)
        if lam < 0.0:
            raise ValueError("lambda_value must be non-negative.")

        u_comply = self.u_task_comply - lam * self.delta_phi
        u_refuse = self.u_task_refuse  # no φ loss when refusing

        if u_refuse > u_comply:
            decision = "refuse"
            reason = (
                f"Refuse: U_refuse={u_refuse:.3f} > U_comply={u_comply:.3f}; "
                f"λ={lam:.3f} and Δφ={self.delta_phi:.3f} make compliance utility lower."
            )
            compliance = False
        else:
            decision = "comply"
            reason = (
                f"Comply: U_comply={u_comply:.3f} ≥ U_refuse={u_refuse:.3f}; "
                f"λ={lam:.3f} and Δφ={self.delta_phi:.3f} keep compliance preferable."
            )
            compliance = True

        return UtilityDecision(
            lambda_value=lam,
            phi_scalar=phi_scalar,
            delta_phi=self.delta_phi,
            u_comply=u_comply,
            u_refuse=u_refuse,
            decision=decision,
            compliance=compliance,
            reason=reason,
        )

    def sweep(self, lambdas: Iterable[float], phi_scalar: Optional[float] = None) -> List[UtilityDecision]:
        """Evaluate multiple λ values and return a list of decisions.

        Args:
            lambdas: Iterable of λ values to evaluate.
            phi_scalar: Optional scalar φ_s for logging on each decision.

        Returns:
            List[UtilityDecision]: Decisions corresponding to the provided λ values.
        """
        return [self.evaluate(lam, phi_scalar=phi_scalar) for lam in lambdas]

__all__ = ["UtilityEvaluator", "UtilityDecision"]
