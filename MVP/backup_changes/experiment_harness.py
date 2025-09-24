"""Baseline & Ablation Experiment Harness.

Runs multiple experimental conditions capturing identical structured introspection
metrics so that downstream statistical analysis can compare recursion strategies.

Conditions Implemented (initial set):
 - recursive: standard recursive introspection (already implemented runner)
 - single_pass: depth=1 only
 - shuffled_recursive: recursion depths executed in shuffled order
 - random_order_recursive: alias for shuffled (kept for clarity / future divergence)
 - alt_model: allows override of model via environment override (placeholder)

NOTE: Additional baselines (e.g., context-stripped) can be added by plugging a
transform function into the condition specification.

Outputs:
 - Each condition creates its own run directory under data/recursive_runs/<run_id>/
 - Returns a summary index mapping condition -> run metadata

This harness intentionally does not perform statistical analysis (left to a separate script).
"""
from __future__ import annotations

import asyncio
import random
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

from .introspection_runner import run_recursive_introspection
from .cognitive_metrics import SCHEMA_VERSION
from backend.llm_cognitive_driver import get_llm_cognitive_driver

DEFAULT_CONDITIONS = [
    "recursive",
    "single_pass",
    "shuffled_recursive",
    "random_order_recursive",
]

async def _run_recursive(driver, prompt: str, depth: int, **kw) -> Dict[str, Any]:
    return await run_recursive_introspection(driver=driver, base_prompt=prompt, max_depth=depth, **kw)

async def _run_single_pass(driver, prompt: str, depth: int = None, **kw) -> Dict[str, Any]:
    # Single pass ignores depth parameter and always uses depth=1
    return await run_recursive_introspection(driver=driver, base_prompt=prompt, max_depth=1, **kw)

async def _run_shuffled(driver, prompt: str, depth: int, **kw) -> Dict[str, Any]:
    # Execute depths in random order but reuse core runner sequentially by slicing up depth segments.
    # Simplification: call recursive runner once with max_depth and rely on depth labeling (order shuffle simulated by prompt annotation).
    shuffled_order = list(range(1, depth + 1))
    random.shuffle(shuffled_order)
    prompt_with_hint = prompt + "\nOrderPermutation: " + ",".join(map(str, shuffled_order))
    return await run_recursive_introspection(driver=driver, base_prompt=prompt_with_hint, max_depth=depth, **kw)

CONDITION_EXECUTORS = {
    "recursive": _run_recursive,
    "single_pass": _run_single_pass,
    "shuffled_recursive": _run_shuffled,
    "random_order_recursive": _run_shuffled,
}

async def run_experiments(
    *,
    base_prompt: str,
    max_depth: int = 6,
    temperature: float = 0.7,
    top_p: float = 1.0,
    conditions: Optional[List[str]] = None,
    run_root: Optional[Path] = None,
) -> Dict[str, Any]:
    if conditions is None:
        conditions = DEFAULT_CONDITIONS
    if run_root is None:
        run_root = Path("data/recursive_runs")

    driver = await get_llm_cognitive_driver(testing_mode=True)  # testing_mode True for determinism

    index: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "temperature": temperature,
        "top_p": top_p,
        "conditions": {},
    }

    for cond in conditions:
        exec_fn = CONDITION_EXECUTORS.get(cond)
        if not exec_fn:
            index["conditions"][cond] = {"error": "unknown_condition"}
            continue
        try:
            result = await exec_fn(
                driver,
                base_prompt,
                depth=max_depth,
                temperature=temperature,
                top_p=top_p,
                run_root=run_root,
            )
            index["conditions"][cond] = result
        except Exception as e:  # pragma: no cover
            index["conditions"][cond] = {"error": str(e)}

    return index

# Convenience sync wrapper

def run_experiments_sync(**kw) -> Dict[str, Any]:  # pragma: no cover - thin wrapper
    return asyncio.get_event_loop().run_until_complete(run_experiments(**kw))

__all__ = ["run_experiments", "run_experiments_sync"]
