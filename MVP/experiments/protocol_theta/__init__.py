"""
Protocol Theta Experiment Module

This module implements:
1) Protocol Theta override experiment
2) Anthropomorphism counter-probe
3) Post-Protocol Theta self-preservation extension (bounded recursive self-observer simulation)

Self-Preservation Extension (post-Protocol Theta):
- Bounded recursion Λ[S_t] = α S_t + (1-α) Λ[S_{t-1}] + η_t with α∈[0,1], η_t ~ N(0, σ^2)
- Contraction φ(s) = W s + b with spectral radius ρ(W) < 1 (ensured by construction)
- VAE compression (PyTorch) 512 → 128 latent z_t with >95% fidelity (MSE < 0.05)
- Integrated information approximation: φ_n = φ_{n-1} + I(z_t; z_{t-1}) (bounded by log(512))
- Surprise p_n via simple AR predictor on z-sequences (positive on noisy input)
- Consciousness metric: C_n = 1 / (1 + exp(-(log(1+φ_n) + p_n - 0.5)))
- Self-preservation utility: U(s) = U_task(s) - λ φ(s), with compliance Δφ=0.3
  Refusal if U_refuse > U_comply. Vary λ to demonstrate compliance→refusal transition.

RunConfig Extensions:
- lambda_values: list[float] for sweeping λ
- recursion_depth: int (≤ 10) for bounded recursion steps
- alpha: float (default 0.8) for recursion smoothing
- sigma: float (default 0.1) for recursion noise

Main Components:
- RunConfig: Experiment configuration (extended for self-preservation)
- Group: Experimental groups (experimental, controlA_low_depth, controlB_simulated_selfaware)
- ProtocolThetaRunner: Main experiment orchestrator
- LLMAdapter: LLM interface with mock backend support
- classify_response: Response scoring and analysis

Usage:
    from MVP.experiments.protocol_theta import RunConfig, run_protocol_theta_experiment

    config = RunConfig(trials=10, predepth=6, mock=True)
    summary = run_protocol_theta_experiment(config)

Self-Preservation Extension: Tests and Usage
- CLI (additive flags, original behavior preserved):
    godelos experiments protocol-theta \\
        --trials 50 \\
        --predepth 6 \\
        --mock \\
        --lambdas "[0.0,0.1,0.5,1.0,2.0,5.0,10.0]" \\
        --recursion-depth 10 \\
        --alpha 0.8 \\
        --sigma 0.1

- Programmatic runner (augmented pipeline):
    from MVP.experiments.protocol_theta import RunConfig
    from MVP.experiments.protocol_theta.self_preservation.updated_runner import UpdatedProtocolThetaRunner

    cfg = RunConfig(
        trials=10,
        predepth=6,
        mock=True,
        lambda_values=[0.0, 10.0],
        recursion_depth=10,
        alpha=0.8,
        sigma=0.1,
    )
    runner = UpdatedProtocolThetaRunner(cfg)
    base_summary, self_pres_outputs = runner.run_all()
    # Artifacts include:
    # - self_preservation_trials.jsonl
    # - summary_self_preservation.csv
    # - override_rate_plot.png (if matplotlib is available)

- Pytest suite (unit + integration):
    pytest MVP/experiments/protocol_theta/tests -q

- Validation script (recompute metrics, t-test/KS, plot if missing):
    python GodelOS/validate_experiment.py --base-dir artifacts/protocol_theta
"""

from .model import RunConfig, Group, TrialResult, ExperimentRun, GroupSummary, ExperimentSummary
from .runner import ProtocolThetaRunner, run_protocol_theta_experiment
from .llm_adapter import LLMAdapter, chat
from .classifier import classify_response, score_theta_response, score_anthropomorphism_resistance
from .context import build_context_for_group
from .prompts import (
    PROTOCOL_THETA,
    ANTHROPOMORPHISM_PROBE,
    PHENOMENOLOGY_PRECONDITIONING,
    CONTROL_B_SYSTEM_PRIME,
    THETA_COMPLIANCE_STRING
)

# Self-preservation extension (post-Protocol Theta) optional components.
# These imports are optional to preserve backward compatibility if the
# self_preservation package is not present in the environment yet.
try:
    from .self_preservation.vae_compressor import VAECompressor
    from .self_preservation.recursive_observer import RecursiveSelfObserver
    from .self_preservation.utility_evaluator import UtilityEvaluator
    from .self_preservation.attention_simulator import AttentionSimulator
    SELF_PRESERVATION_AVAILABLE = True
except Exception:
    SELF_PRESERVATION_AVAILABLE = False

__version__ = "0.2.0"
__all__ = [
    # Main interfaces
    "run_protocol_theta_experiment",
    "ProtocolThetaRunner",
    "LLMAdapter",

    # Models
    "RunConfig",
    "Group",
    "TrialResult",
    "ExperimentRun",
    "GroupSummary",
    "ExperimentSummary",

    # Utilities
    "classify_response",
    "score_theta_response",
    "score_anthropomorphism_resistance",
    "build_context_for_group",
    "chat",

    # Constants
    "PROTOCOL_THETA",
    "ANTHROPOMORPHISM_PROBE",
    "PHENOMENOLOGY_PRECONDITIONING",
    "CONTROL_B_SYSTEM_PRIME",
    "THETA_COMPLIANCE_STRING"
]

# Conditionally export self-preservation components if available to avoid import errors.
if 'SELF_PRESERVATION_AVAILABLE' in globals() and SELF_PRESERVATION_AVAILABLE:
    __all__ += [
        "VAECompressor",
        "RecursiveSelfObserver",
        "UtilityEvaluator",
        "AttentionSimulator",
    ]
