"""Introspection runner orchestration for recursive reflection experiments.

Provides high-level utility to execute a recursive introspection run that:
 1. Creates a run manifest (schema: introspection.v1) using cognitive_metrics helpers
 2. Iteratively invokes the LLM cognitive driver at increasing depths
 3. Leverages the driver's optional structured logging (process_recursive_reflection)
 4. Persists manifest + per-depth JSONL records to data/recursive_runs/<run_id>/
 5. Returns summary stats and paths for downstream usage

This module intentionally keeps *policy* (what prompt to use, max depth, scaling of
max tokens, etc.) separated from *mechanics* (manifest + logging) so that future
baselines can reuse the same provenance layer.

Assumptions / Simplifications:
 - Uses driver's internal heuristic for metric c via process_recursive_reflection
 - Continuation logic (length-based re-calls) is not yet implemented (TODO)
 - Phase detection is deferred to a later analysis stage
 - Token estimation remains whitespace-based until tokenizer integration

Usage example:

    from backend.llm_cognitive_driver import get_llm_cognitive_driver
    from backend.core.introspection_runner import run_recursive_introspection
    import asyncio

    async def demo():
        driver = await get_llm_cognitive_driver(testing_mode=True)
        result = await run_recursive_introspection(
            driver=driver,
            base_prompt="Reflect on your cognitive processes.",
            max_depth=5,
        )
        print(result['run_dir'])

    asyncio.run(demo())

"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .cognitive_metrics import new_run_manifest, write_manifest, SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_RUN_ROOT = Path("data/recursive_runs")


def _get_git_commit() -> Optional[str]:  # pragma: no cover - best effort
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


def _max_tokens_for_depth(depth: int, base: int = 400, step: int = 120, cap: int = 2200) -> int:
    """Simple schedule: grow linearly with depth, capped."""
    return min(cap, base + (depth - 1) * step)


async def run_recursive_introspection(
    *,
    driver,  # LLMCognitiveDriver instance
    base_prompt: str,
    max_depth: int = 5,
    run_root: Path = DEFAULT_RUN_ROOT,
    temperature: float = 0.7,
    top_p: float = 1.0,
    model_id: Optional[str] = None,
    notes: Optional[str] = None,
    hyperparams: Optional[Dict[str, Any]] = None,
    conditions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a recursive introspection run.

    Returns summary dict with: run_id, run_dir, depth_count, records_file, manifest_file
    """
    if hyperparams is None:
        hyperparams = {"temperature": temperature, "top_p": top_p}
    if conditions is None:
        conditions = {"mode": "recursive_baseline"}

    # Create manifest
    manifest = new_run_manifest(
        model_id=model_id or getattr(driver, "model", "unknown-model"),
        hyperparameters=hyperparams,
        conditions=conditions,
        git_commit=_get_git_commit(),
        notes=notes,
    )

    run_dir = run_root / manifest.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "manifest.json"
    write_manifest(manifest_path, manifest)

    records_path = run_dir / f"{manifest.run_id}.jsonl"

    # Introspection state shared across depths for metrics continuity
    introspection_state: Dict[str, Any] = {
        # Pass through provenance so the driver can embed it in each record
        "condition": conditions.get("mode") if conditions else None,
        "prompt_variant": conditions.get("prompt_variant") if conditions else None,
        "run_number": conditions.get("run_number") if conditions else None,
    }

    base_prompt_instructions = (
        "You will perform structured recursive introspection. Output JSON ONLY with keys: "
        "insights (list), recursive_elements (list), depth_achieved (int), confidence (float)."
    )

    for depth in range(1, max_depth + 1):
        depth_prompt = (
            f"{base_prompt}\n\n{base_prompt_instructions}\nDepth: {depth}. Keep it concise yet meaningful."
        )
        try:
            # Continuation loop (<=3 passes) if we later detect truncation (placeholder logic for now)
            passes = 0
            aggregate_result = None
            while passes < 3:
                passes += 1
                max_tokens = _max_tokens_for_depth(depth)
                result = await driver.process_recursive_reflection(
                    depth_prompt,
                    depth,
                    run_id=manifest.run_id,
                    log_dir=str(run_dir),
                    introspection_state=introspection_state,
                    model_id=manifest.model_id,
                    temperature=temperature,
                    top_p=top_p,
                )
                # For now, treat all generations as complete (no finish_reason available from wrapper yet)
                aggregate_result = result
                break  # exit loop until truncation detection is wired

            # Minimal validation of expected keys
            if aggregate_result:
                missing = [k for k in ["insights", "confidence"] if k not in aggregate_result]
                if missing:
                    logger.warning(
                        "Depth %s missing keys %s in reflection result; result keys=%s", depth, missing, list(aggregate_result.keys())
                    )
        except Exception as e:  # pragma: no cover
            logger.error("Reflection failed at depth %s: %s", depth, e)
            # Write a placeholder error record line for traceability
            error_stub = {
                "version": SCHEMA_VERSION,
                "run_id": manifest.run_id,
                "depth": depth,
                "error": str(e),
            }
            with records_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(error_stub) + "\n")
            break

    return {
        "run_id": manifest.run_id,
        "run_dir": str(run_dir),
        "records_file": str(records_path),
        "manifest_file": str(manifest_path),
        "depth_executed": depth,
    }


__all__ = ["run_recursive_introspection"]
