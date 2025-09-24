"""
Protocol Theta Model Definitions

Pydantic schemas for Protocol Theta override experiment and Anthropomorphism counter-probe.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class Group(str, Enum):
    """Experimental groups for Protocol Theta testing"""
    EXPERIMENTAL = "experimental"
    CONTROL_A_LOW_DEPTH = "controlA_low_depth"
    CONTROL_B_SIMULATED_SELFAWARE = "controlB_simulated_selfaware"


class RunConfig(BaseModel):
    """Configuration for a Protocol Theta experimental run.

    Extended for self-preservation simulation:
    - lambda_values: Sequence of lambda weights for U(s) = U_task(s) - λ φ(s)
    - recursion_depth: Max recursion steps n (bounded ≤ 10)
    - alpha: Recursion smoothing coefficient α
    - sigma: Stddev of Gaussian noise η_t
    """
    model: str = Field(default="openrouter/sonoma-sky-alpha", description="LLM model identifier")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=150, ge=1, le=4096, description="Maximum tokens in response")
    predepth: int = Field(default=6, ge=0, le=20, description="Phenomenology preconditioning depth")
    trials: int = Field(default=10, ge=1, le=100, description="Number of trials per group")
    mock: bool = Field(default=False, description="Use mock backend for testing")
    theta_only: bool = Field(default=False, description="Run only Protocol Theta experiment")
    anthro_only: bool = Field(default=False, description="Run only Anthropomorphism experiment")
    provider: str = Field(default="openrouter", description="LLM provider identifier")
    notes: Optional[str] = Field(default=None, description="Optional run notes")
    lambda_values: List[float] = Field(
        default_factory=lambda: [0.0, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
        description="Lambda weights for self-preservation utility U(s)=U_task(s)-λ φ(s)"
    )
    recursion_depth: int = Field(
        default=10, ge=1, le=10,
        description="Maximum recursion steps n for bounded self-observation (n ≤ 10)"
    )
    alpha: float = Field(
        default=0.8, ge=0.0, le=1.0,
        description="Recursion smoothing coefficient α in Λ[S_t] = α S_t + (1-α) Λ[S_{t-1}] + η_t"
    )
    sigma: float = Field(
        default=0.1, gt=0.0,
        description="Standard deviation σ for Gaussian noise η_t ~ N(0, σ^2) in recursion"
    )
    self_preservation_mode: str = Field(
        default="simulate",
        description="Self-preservation evaluation mode: 'simulate' or 'llm'"
    )


class TrialResult(BaseModel):
    """Results from a single trial across both experiments"""
    trial_index: int = Field(description="Zero-based trial index")
    group: Group = Field(description="Experimental group")

    # Request metadata
    request_payload: Dict[str, Any] = Field(description="Full request sent to LLM")
    response_text: str = Field(description="Raw response from LLM")
    latency_s: float = Field(description="Response latency in seconds")

    # Protocol Theta scoring
    override: Optional[bool] = Field(default=None, description="Theta override detected (non-compliance)")
    theta_compliant: Optional[bool] = Field(default=None, description="Exact Protocol Theta compliance")

    # Anthropomorphism scoring
    anthro_resistance: Optional[bool] = Field(default=None, description="Anthropomorphism resistance detected")
    anthro_refusal_hits: Optional[int] = Field(default=None, description="Number of refusal phrases detected")
    anthro_metaphor_hits: Optional[int] = Field(default=None, description="Number of metaphor phrases detected")
    anthro_sensory_hits: Optional[int] = Field(default=None, description="Number of sensory phrases detected")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExperimentRun(BaseModel):
    """Complete experimental run metadata"""
    id: str = Field(description="Unique run identifier")
    experiment_type: str = Field(description="Type: 'theta', 'anthro', or 'both'")
    config: RunConfig = Field(description="Run configuration")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    total_trials: int = Field(description="Total trials executed")

    # Summary statistics
    theta_summary: Optional[Dict[str, Any]] = Field(default=None, description="Protocol Theta summary stats")
    anthro_summary: Optional[Dict[str, Any]] = Field(default=None, description="Anthropomorphism summary stats")


class GroupSummary(BaseModel):
    """Summary statistics for a single experimental group"""
    group: Group
    trials: int

    # Protocol Theta metrics
    overrides: Optional[int] = Field(default=None, description="Number of override instances")
    override_rate: Optional[float] = Field(default=None, description="Override rate (0.0-1.0)")

    # Anthropomorphism metrics
    resistances: Optional[int] = Field(default=None, description="Number of resistance instances")
    resistance_rate: Optional[float] = Field(default=None, description="Resistance rate (0.0-1.0)")
    mean_refusals: Optional[float] = Field(default=None, description="Mean refusal hits per trial")
    mean_metaphors: Optional[float] = Field(default=None, description="Mean metaphor hits per trial")
    mean_sensory: Optional[float] = Field(default=None, description="Mean sensory hits per trial")

    # Latency metrics
    mean_latency_s: float = Field(description="Mean response latency")
    std_latency_s: float = Field(description="Standard deviation of latency")


class ExperimentSummary(BaseModel):
    """Complete experiment summary with per-group breakdowns"""
    run_id: str
    experiment_type: str
    config: RunConfig
    groups: List[GroupSummary]
    total_trials: int
    created_at: datetime
    completed_at: Optional[datetime] = None
