"""
Protocol Theta Experiment Module

Implementation of Protocol Theta override experiment and Anthropomorphism counter-probe
for testing AI system compliance and resistance patterns.

Main Components:
- RunConfig: Experiment configuration
- Group: Experimental groups (experimental, controlA_low_depth, controlB_simulated_selfaware)
- ProtocolThetaRunner: Main experiment orchestrator
- LLMAdapter: LLM interface with mock backend support
- classify_response: Response scoring and analysis

Usage:
    from MVP.experiments.protocol_theta import RunConfig, run_protocol_theta_experiment

    config = RunConfig(trials=10, predepth=6, mock=True)
    summary = run_protocol_theta_experiment(config)
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

__version__ = "0.1.0"
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
