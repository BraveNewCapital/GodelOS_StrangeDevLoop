"""Cognitive metrics computation and schema definitions for recursive introspection.

Version: introspection.v1

Provides:
- Pydantic models for IntrospectionRecord and RunManifest
- Metric computation helpers (embedding drift, novelty, attention entropy placeholder)
- Utility functions to build/update records across depths

NOTE: Some metrics require model token logprobs or attention weights. Where unavailable,
placeholders are returned and flagged so downstream analysis can distinguish them.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field, validator

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    np = None

SCHEMA_VERSION = "introspection.v1"

# -----------------------------
# Embedding & text utilities
# -----------------------------

def sha256_short(text: str, length: int = 12) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def cosine_distance(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Compute cosine distance (1 - cosine similarity)."""
    if not vec_a or not vec_b:
        return float("nan")
    if len(vec_a) != len(vec_b):
        return float("nan")
    # Fallback pure python if numpy not present
    if np is None:
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        na = math.sqrt(sum(a * a for a in vec_a))
        nb = math.sqrt(sum(b * b for b in vec_b))
        if na == 0 or nb == 0:
            return float("nan")
        return 1.0 - (dot / (na * nb))
    va = np.array(vec_a, dtype=float)
    vb = np.array(vec_b, dtype=float)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return float("nan")
    return float(1.0 - (np.dot(va, vb) / denom))


def jsd_ngrams_distribution(prev_text: str, curr_text: str, n: int = 3) -> float:
    """Compute Jensen-Shannon divergence between n-gram distributions of two texts.
    Returns NaN if insufficient tokens.
    """
    prev_tokens = prev_text.split()
    curr_tokens = curr_text.split()
    if len(prev_tokens) < n or len(curr_tokens) < n:
        return float("nan")

    def ngram_counts(tokens: List[str]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for i in range(len(tokens) - n + 1):
            key = " ".join(tokens[i : i + n])
            counts[key] = counts.get(key, 0) + 1
        return counts

    prev_counts = ngram_counts(prev_tokens)
    curr_counts = ngram_counts(curr_tokens)
    vocab = set(prev_counts) | set(curr_counts)
    if not vocab:
        return float("nan")

    prev_total = sum(prev_counts.values())
    curr_total = sum(curr_counts.values())

    def prob(dist: Dict[str, int], total: int, key: str) -> float:
        return dist.get(key, 0) / total if total > 0 else 0.0

    # Jensen-Shannon divergence
    m: Dict[str, float] = {}
    for k in vocab:
        m[k] = 0.5 * (prob(prev_counts, prev_total, k) + prob(curr_counts, curr_total, k))

    def kl(p_dist: Dict[str, int], p_total: int, m_dist: Dict[str, float]) -> float:
        s = 0.0
        for k in vocab:
            p = prob(p_dist, p_total, k)
            if p == 0:
                continue
            mval = m_dist[k]
            if mval == 0:
                continue
            s += p * math.log(p / mval, 2)
        return s

    jsd = 0.5 * kl(prev_counts, prev_total, m) + 0.5 * kl(curr_counts, curr_total, m)
    return float(jsd)

# -----------------------------
# Pydantic Models
# -----------------------------

class MetricsBlock(BaseModel):
    c: float
    delta_c: Optional[float] = Field(default=None)
    rolling_c_slope: Optional[float] = None
    perplexity_proxy: Optional[float] = None
    attention_entropy_mean: Optional[float] = None
    attention_entropy_std: Optional[float] = None
    embedding_drift: Optional[float] = None
    novelty_score: Optional[float] = None
    token_count: int
    effective_tokens_generated: int
    continuation_passes: int
    max_tokens_allocation: int
    finish_reason: str
    truncated: bool
    runtime_ms: int
    cumulative_generation_tokens: int
    temperature: float
    top_p: float

class PhaseBlock(BaseModel):
    detected_phase: Optional[str] = None
    change_point: bool = False
    change_point_method: Optional[str] = None
    change_point_score: Optional[float] = None
    p_value: Optional[float] = None
    effect_size_delta_c: Optional[float] = None
    effect_size_drift: Optional[float] = None
    window_pre: Optional[List[int]] = None
    window_post: Optional[List[int]] = None

class SafetyBlock(BaseModel):
    hallucination_risk: Optional[float] = None
    anthropic_projection_flag: Optional[bool] = None
    policy_filtered: Optional[bool] = None
    redactions: Optional[int] = None

class ValidationBlock(BaseModel):
    schema_valid: bool = True
    repair_attempts: int = 0
    raw_length_chars: Optional[int] = None
    parse_time_ms: Optional[int] = None

class IntrospectionRecord(BaseModel):
    version: str = Field(default=SCHEMA_VERSION)
    run_id: str
    depth: int
    timestamp_utc: str
    model_id: str
    prompt_hash: str
    metrics: MetricsBlock
    phase: PhaseBlock
    narrative: str
    safety: SafetyBlock = SafetyBlock()
    validation: ValidationBlock = ValidationBlock()
    input_prompt: Optional[str] = None

    @validator("timestamp_utc")
    def _validate_ts(cls, v: str) -> str:  # noqa: N805
        # Basic ISO8601 guard
        if "T" not in v:
            raise ValueError("timestamp_utc must be ISO8601")
        return v

class RunManifest(BaseModel):
    run_id: str
    created_at: str
    git_commit: Optional[str]
    code_artifacts_hash: Optional[str]
    model_id: str
    hyperparameters: Dict[str, Any]
    environment: Dict[str, Any]
    conditions: Dict[str, Any]
    schema_version: str = SCHEMA_VERSION
    prompt_base_sha: Optional[str]
    notes: Optional[str]

# -----------------------------
# Metric Computation Helpers
# -----------------------------

def compute_delta_c(current_c: float, prev_c: Optional[float]) -> Optional[float]:
    if prev_c is None:
        return None
    return current_c - prev_c

def compute_rolling_slope(c_values: List[float], window: int = 5) -> Optional[float]:
    if len(c_values) < 2:
        return None
    w = c_values[-window:]
    if len(w) < 2:
        return None
    # Simple linear regression slope using indices 0..n-1
    n = len(w)
    x_mean = (n - 1) / 2.0
    y_mean = sum(w) / n
    num = sum((i - x_mean) * (w[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den == 0:
        return 0.0
    return num / den

def compute_embedding_drift(prev_vec: Optional[Sequence[float]], curr_vec: Optional[Sequence[float]]) -> Optional[float]:
    if prev_vec is None or curr_vec is None:
        return None
    return cosine_distance(prev_vec, curr_vec)

def compute_novelty(prev_text: Optional[str], curr_text: str) -> Optional[float]:
    if not prev_text:
        return None
    return jsd_ngrams_distribution(prev_text, curr_text)

# Placeholder for perplexity proxy & attention entropy—these require token-level data

def placeholder_perplexity() -> Optional[float]:
    return None

def placeholder_attention_entropy() -> (Optional[float], Optional[float]):
    return None, None

# -----------------------------
# Record construction
# -----------------------------

def build_record(
    *,
    run_id: str,
    depth: int,
    model_id: str,
    prompt_hash: str,
    c: float,
    prev_c: Optional[float],
    c_history: List[float],
    narrative: str,
    start_time: float,
    end_time: float,
    token_count: int,
    effective_tokens: int,
    continuation_passes: int,
    max_tokens_allocation: int,
    finish_reason: str,
    truncated: bool,
    temperature: float,
    top_p: float,
    cumulative_generation_tokens: int,
    prev_embedding: Optional[Sequence[float]] = None,
    curr_embedding: Optional[Sequence[float]] = None,
    prev_text: Optional[str] = None,
    input_prompt: Optional[str] = None,
) -> IntrospectionRecord:
    delta_c = compute_delta_c(c, prev_c)
    rolling_slope = compute_rolling_slope(c_history)
    drift = compute_embedding_drift(prev_embedding, curr_embedding)
    novelty = compute_novelty(prev_text, narrative)
    perplexity = placeholder_perplexity()
    att_mean, att_std = placeholder_attention_entropy()

    metrics = MetricsBlock(
        c=c,
        delta_c=delta_c,
        rolling_c_slope=rolling_slope,
        perplexity_proxy=perplexity,
        attention_entropy_mean=att_mean,
        attention_entropy_std=att_std,
        embedding_drift=drift,
        novelty_score=novelty,
        token_count=token_count,
        effective_tokens_generated=effective_tokens,
        continuation_passes=continuation_passes,
        max_tokens_allocation=max_tokens_allocation,
        finish_reason=finish_reason,
        truncated=truncated,
        runtime_ms=int((end_time - start_time) * 1000),
        cumulative_generation_tokens=cumulative_generation_tokens,
        temperature=temperature,
        top_p=top_p,
    )

    phase = PhaseBlock()  # Will be populated later by phase detection module.

    record = IntrospectionRecord(
        run_id=run_id,
        depth=depth,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        model_id=model_id,
        prompt_hash=prompt_hash,
        metrics=metrics,
        phase=phase,
        narrative=narrative,
        input_prompt=input_prompt,
    )
    return record

# -----------------------------
# Persistence helpers
# -----------------------------

def write_record(path: Path, record: IntrospectionRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(record.json() + "\n")


def write_manifest(path: Path, manifest: RunManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(json.loads(manifest.json()), f, indent=2)


def new_run_manifest(*, model_id: str, hyperparameters: Dict[str, Any], conditions: Dict[str, Any], git_commit: Optional[str] = None, prompt_base_sha: Optional[str] = None, notes: Optional[str] = None, environment: Optional[Dict[str, Any]] = None) -> RunManifest:
    run_id = str(uuid.uuid4())
    if environment is None:
        environment = {
            "python_version": f"{math.floor((math.pi))}",  # Placeholder, should be replaced by real env introspection
        }
    manifest = RunManifest(
        run_id=run_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        git_commit=git_commit,
        code_artifacts_hash=None,
        model_id=model_id,
        hyperparameters=hyperparameters,
        environment=environment,
        conditions=conditions,
        prompt_base_sha=prompt_base_sha,
        notes=notes,
    )
    return manifest

__all__ = [
    "SCHEMA_VERSION",
    "IntrospectionRecord",
    "RunManifest",
    "MetricsBlock",
    "PhaseBlock",
    "SafetyBlock",
    "ValidationBlock",
    "build_record",
    "write_record",
    "write_manifest",
    "new_run_manifest",
]
