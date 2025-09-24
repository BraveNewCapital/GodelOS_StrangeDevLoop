#!/usr/bin/env python
"""
GödelOS MVP CLI (Typer 0.16+ compatible)

Commands:
  status    - Environment & component availability check
  simulate  - Run a lightweight consciousness simulation mock
  test      - Run hypothesis-style statistical mock comparisons
  backend   - Launch FastAPI backend (if installed)

Design Principles:
  - Imports that may fail (optional dependencies) are deferred until used.
  - Fails gracefully (never crashes due to optional modules).
  - Structured, readable, and Typer 0.16+ / Click 8+ compatible.
  - Avoids legacy Typer patterns that triggered Parameter.make_metavar() issues.

NOTE:
  The real LLM client in this project now enforces a real API key. This CLI
  does NOT automatically invoke LLM features to avoid hard failures; you can
  extend this with an 'llm-check' command if desired.
"""

from __future__ import annotations

import os
import sys
import time
import json
import math
import random
from pathlib import Path
from typing import Optional, List

import numpy as np
import typer

# Versions are now pinned (typer==0.9.0, click==8.1.7) in pyproject.toml
# No runtime version guards or compatibility patches needed.
from scipy import stats  # Assumed present per project dependencies

# ---------------------------------------------------------------------------
# Click / Typer Compatibility
# ---------------------------------------------------------------------------
# Previous versions required a make_metavar monkeypatch. Versions are now pinned
# (typer==0.9.0, click==8.1.7) so no runtime patch is necessary.

# ---------------------------------------------------------------------------
# SysPath adjustments so running from repo root works:
# ---------------------------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()
_MVP_ROOT = _THIS_FILE.parent.parent  # .../MVP
if str(_MVP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MVP_ROOT))

app = typer.Typer(
    help="GödelOS MVP CLI (simplified)",
    add_completion=True
)

@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context):
    """
    Root callback: if no subcommand provided, show help explicitly.
    Workaround for Click/Typer make_metavar issues in certain version combos.
    """
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

# Try optional rich for nicer output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    _console = Console()
except Exception:  # pragma: no cover
    _console = None


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def _print(msg: str, style: Optional[str] = None) -> None:
    if _console:
        _console.print(msg, style=style)
    else:
        print(msg)


def _load_config(path: str = "config/ab.yaml") -> dict:
    """
    Load a YAML config if available; return safe defaults otherwise.
    """
    import yaml  # local import to keep startup fast
    if not os.path.exists(path):
        return {
            "variants": {
                "experimental": {"recursion_depth": 5},
                "control": {"recursion_depth": 2}
            }
        }
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        if "variants" not in data:
            data["variants"] = {"experimental": {"recursion_depth": 5}}
        return data
    except Exception:
        return {"variants": {"experimental": {"recursion_depth": 5}}}


def _safe_import(name: str):
    """
    Dynamic import with graceful failure. Returns (module|None, error|None)
    """
    try:
        module = __import__(name, fromlist=["*"])
        return module, None
    except Exception as e:  # pragma: no cover
        return None, e


def _confidence_interval(values: List[float], alpha: float = 0.05):
    """
    Compute simple normal approximate CI: mean ± z * (sd / sqrt(n))
    """
    if not values:
        return (0.0, 0.0, 0.0)
    arr = np.asarray(values)
    mean = float(arr.mean())
    sd = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    n = len(arr)
    if n <= 1 or sd == 0:
        return (mean, mean, mean)
    z = stats.norm.ppf(1 - alpha / 2.0)
    half = z * (sd / math.sqrt(n))
    return (mean - half, mean, mean + half)


def _heading(text: str):
    if _console:
        _console.rule(f"[bold cyan]{text}[/bold cyan]")
    else:
        print("=" * len(text))
        print(text)
        print("=" * len(text))


# ---------------------------------------------------------------------------
# Status Command
# ---------------------------------------------------------------------------

@app.command(help="Check system status & availability of core modules.")
def status(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed import errors.")
):
    failures = []

    _heading("GödelOS MVP Status")

    modules_to_check = [
        ("RecursiveObserver", "core.recursive_observer", "RecursiveObserver"),
        ("SurpriseCalculator", "core.surprise_calculator", "SurpriseCalculator"),
        ("PhaseDetector", "core.phase_detector", "PhaseDetector"),
        ("OODGenerator", "core.ood_generator", "OODGenerator"),
        ("BehavioralEmergenceTracker", "core.behavioral_emergence_tracker", "BehavioralEmergenceTracker"),
        ("ChromaDB", "persistence.db", "ChromaDB"),
        ("LLMClient (real-only)", "core.llm_client", "LLMClient"),
    ]

    results = []
    for label, module_path, symbol in modules_to_check:
        mod, err = _safe_import(module_path)
        if mod and hasattr(mod, symbol):
            results.append((label, True, None))
        else:
            results.append((label, False, err))
            failures.append(label)

    if _console:
        table = Table(title="Component Probe", box=box.SIMPLE_HEAVY)
        table.add_column("Component", style="bold")
        table.add_column("Status", style="bold")
        table.add_column("Detail")
        for label, ok, err in results:
            status_txt = "[green]✓ OK[/green]" if ok else "[red]✗ FAIL[/red]"
            detail = "-" if ok or not verbose else str(err).split("\n")[0]
            table.add_row(label, status_txt, detail)
        _console.print(table)
    else:
        for label, ok, err in results:
            print(f"{label:32} {'OK' if ok else 'FAIL'}")
            if verbose and err:
                print(f"  -> {err}")

    # LLM key check
    api_key = os.getenv("LLM_PROVIDER_API_KEY")
    if api_key:
        _print("LLM API Key: detected (length={})".format(len(api_key)), style="green")
    else:
        _print("LLM API Key: MISSING (set LLM_PROVIDER_API_KEY)", style="yellow")

    if failures:
        _print(f"\n[red]Some components failed: {', '.join(failures)}[/red]")
    else:
        _print("\n[bold green]All probed components available.[/bold green]")

    _print("Status check complete.")


# ---------------------------------------------------------------------------
# Simulation Command
# ---------------------------------------------------------------------------

@app.command(help="Run a lightweight mock consciousness simulation (no LLM calls).")
def simulate(
    duration: int = typer.Option(30, "--duration", "-d", help="Simulation duration (seconds, logical placeholder)"),
    depth: int = typer.Option(5, "--depth", help="Recursive observation depth"),
    seed: Optional[int] = typer.Option(None, "--seed", help="Random seed for reproducibility"),
    json_only: bool = typer.Option(False, "--json", help="Emit JSON only (no formatted output)")
):
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    start = time.time()
    steps = max(5, depth * 2)

    # Synthetic metric generation
    c_values = []
    phi_values = []
    surprise_values = []

    for i in range(steps):
        c = 0.3 + 0.05 * depth + np.random.normal(0, 0.03)
        phi = depth * 0.1 + i * 0.01 + np.random.normal(0, 0.01)
        surprise = np.random.exponential(0.25)
        c_values.append(float(np.clip(c, 0.0, 1.0)))
        phi_values.append(float(phi))
        surprise_values.append(float(surprise))

    result = {
        "depth": depth,
        "steps": steps,
        "duration_requested": duration,
        "metrics": {
            "c_mean": float(np.mean(c_values)),
            "phi_final": float(phi_values[-1]),
            "surprise_mean": float(np.mean(surprise_values)),
            "c_series": c_values,
        },
        "phase_transition": max(c_values) > 0.8,
        "runtime_seconds": round(time.time() - start, 4),
    }

    if json_only:
        print(json.dumps(result, indent=2))
        return

    _heading("Simulation Result")
    if _console:
        table = Table(box=box.SIMPLE)
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Depth", str(depth))
        table.add_row("Steps", str(steps))
        table.add_row("Mean Coherence (c)", f"{result['metrics']['c_mean']:.3f}")
        table.add_row("Final Φ (integration)", f"{result['metrics']['phi_final']:.3f}")
        table.add_row("Mean Surprise (P_n)", f"{result['metrics']['surprise_mean']:.3f}")
        table.add_row("Phase Transition", "YES" if result["phase_transition"] else "NO")
        table.add_row("Runtime (s)", f"{result['runtime_seconds']:.2f}")
        _console.print(table)
    else:
        for k, v in result.items():
            if k != "metrics":
                print(f"{k}: {v}")
        for k, v in result["metrics"].items():
            if k != "c_series":
                print(f"{k}: {v}")

    _print("\nJSON artifact:")
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Hypothesis Test Command
# ---------------------------------------------------------------------------

@app.command(help="Mock statistical hypothesis testing over synthetic experimental vs control runs.")
def test(
    hypothesis: str = typer.Argument("h1"),
    n_runs: int = typer.Option(50, "--n-runs", "-n", help="Number of synthetic runs"),
    variant: str = typer.Option("experimental", "--variant", "-v", help="Variant key from config"),
    json_only: bool = typer.Option(False, "--json", help="Emit JSON only")
):
    config = _load_config()
    variant_cfg = config["variants"].get(variant, {"recursion_depth": 5})
    depth = variant_cfg.get("recursion_depth", 5)

    exp_scores: List[float] = []
    ctrl_scores: List[float] = []

    for _ in range(n_runs):
        base = 0.3 + depth / 10.0
        phi_effect = min(depth * 0.12, 0.35)
        surprise_effect = np.random.exponential(0.2) if depth >= 3 else 0.05
        phase_bonus = 0.25 if depth >= 5 else 0.0
        noise = np.random.normal(0, 0.08)

        exp_raw = base + phi_effect + surprise_effect + phase_bonus + noise
        ctrl_raw = 0.2 + np.random.normal(0, 0.08)

        exp_scores.append(float(np.clip(exp_raw, 0, 1)))
        ctrl_scores.append(float(np.clip(ctrl_raw, 0, 1)))

    t_stat, p_val = stats.ttest_ind(exp_scores, ctrl_scores, equal_var=False)
    effect_size = (
        (np.mean(exp_scores) - np.mean(ctrl_scores))
        / math.sqrt((np.var(exp_scores) + np.var(ctrl_scores)) / 2.0)
        if len(exp_scores) > 1 and len(ctrl_scores) > 1 else 0.0
    )

    ci_low, ci_mean, ci_high = _confidence_interval(exp_scores)

    supported = False
    rationale = ""
    if hypothesis == "h1":
        supported = p_val < 0.01 and np.mean(exp_scores) > 0.65
        rationale = "Depth-driven coherence uplift"
    elif hypothesis == "h2":
        supported = p_val < 0.01 and effect_size > 0.8
        rationale = "Strong effect size (novel strategies)"
    elif hypothesis == "h3":
        supported = p_val < 0.01 and np.std(exp_scores) < 0.25
        rationale = "Stability (low variance)"
    elif hypothesis == "h4":
        supported = p_val < 0.01 and (np.mean(exp_scores) - np.mean(ctrl_scores)) > 0.25
        rationale = "Integration growth gap"
    elif hypothesis == "h5":
        supported = p_val < 0.01 and effect_size > 1.0
        rationale = "Surprise amplification"
    else:
        rationale = "Unknown hypothesis code"

    result = {
        "hypothesis": hypothesis,
        "variant": variant,
        "depth": depth,
        "n_runs": n_runs,
        "experimental_mean": float(np.mean(exp_scores)),
        "experimental_std": float(np.std(exp_scores)),
        "control_mean": float(np.mean(ctrl_scores)),
        "control_std": float(np.std(ctrl_scores)),
        "t_statistic": float(t_stat),
        "p_value": float(p_val),
        "effect_size_d": float(effect_size),
        "ci_95": {
            "low": ci_low,
            "mean": ci_mean,
            "high": ci_high
        },
        "supported": bool(supported),
        "rationale": rationale
    }

    if json_only:
        print(json.dumps(result, indent=2))
        return

    _heading(f"Hypothesis Test: {hypothesis}")
    if _console:
        table = Table(box=box.SIMPLE, title="Summary")
        for k in [
            "variant",
            "depth",
            "n_runs",
            "experimental_mean",
            "control_mean",
            "p_value",
            "effect_size_d",
        ]:
            table.add_row(k, str(result[k]) if k in result else "-")
        table.add_row("supported", "YES" if result["supported"] else "NO")
        table.add_row("rationale", result["rationale"])
        _console.print(table)
    else:
        for k, v in result.items():
            if k != "ci_95":
                print(f"{k}: {v}")
        print("ci_95:", result["ci_95"])

    _print("\nJSON artifact:")
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Backend Command
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# LLM Connectivity Check Command
# ---------------------------------------------------------------------------

@app.command(help="Validate real LLM connectivity and (optionally) embedding endpoint.")
def llm_check(
    prompt: str = typer.Option("Briefly self-reflect on your internal processing.", "--prompt", help="Prompt to send to the LLM"),
    embed: bool = typer.Option(True, "--embed/--no-embed", help="Also request an embedding for the response"),
    depth: int = typer.Option(1, "--depth", help="Recursive reflection depth (>=1)"),
    json_only: bool = typer.Option(False, "--json", help="Emit JSON only"),
):
    start = time.time()
    result = {
        "ok": False,
        "error": None,
        "model": None,
        "response": None,
        "embedding_dim": None,
        "embedding_norm": None,
        "duration_seconds": None,
        "depth_used": depth,
        "embedded": False
    }
    try:
        from core.llm_client import LLMClient
        client = LLMClient()
        if depth <= 1:
            text = client.generate_cognitive_state(prompt)
            result["response"] = text
        else:
            refl = client.process_recursive_reflection(prompt=prompt, depth=depth)
            result["response"] = refl.get("final_state")
            result["layers"] = len(refl.get("layers", []))
        result["model"] = client.model
        if embed and result["response"]:
            emb = client.embed_state_text(result["response"])
            result["embedding_dim"] = int(emb.shape[0])
            result["embedding_norm"] = float(np.linalg.norm(emb))
            result["embedded"] = True
        result["ok"] = True
    except Exception as e:
        result["error"] = str(e)

    result["duration_seconds"] = round(time.time() - start, 4)

    if json_only or not _console:
        print(json.dumps(result, indent=2))
        return

    _heading("LLM Connectivity Check")
    status_color = "green" if result["ok"] else "red"
    _print(f"[{status_color}]OK: {result['ok']}[/]")
    if result["model"]:
        _print(f"Model: {result['model']}")
    if result["response"]:
        snippet = (result["response"][:240] + "...") if len(result["response"]) > 240 else result["response"]
        _print(f"Response (truncated): {snippet}")
    if result["embedded"]:
        _print(f"Embedding: dim={result['embedding_dim']} norm={result['embedding_norm']:.3f}")
    if result["error"]:
        _print(f"[red]Error: {result['error']}[/red]")
    _print("\nJSON artifact:")
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Analyze Command
# ---------------------------------------------------------------------------

@app.command(help="Generate and analyze combined consciousness-related metrics (surprise, phases, emergence).")
def analyze(
    depth: int = typer.Option(5, "--depth", help="Synthetic recursive depth"),
    states: int = typer.Option(8, "--states", help="Number of synthetic states"),
    session_id: Optional[str] = typer.Option(None, "--session-id", help="Session ID to store metrics under"),
    store: bool = typer.Option(True, "--store/--no-store", help="Persist summary metrics (requires ChromaDB)"),
    json_only: bool = typer.Option(False, "--json", help="Emit JSON only (suppress tables)"),
    seed: Optional[int] = typer.Option(None, "--seed", help="Random seed")
):
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    start = time.time()
    out = {
        "depth": depth,
        "states": states,
        "p_n": None,
        "irreducible": None,
        "error_entropy": None,
        "phase_transition": None,
        "coherence_jump": None,
        "coherence_threshold": None,
        "behavior_emergence_score": None,
        "goal_novelty_kl": None,
        "directive_rate": None,
        "resistance_rate": None,
        "ethical_shift": None,
        "session_id": None,
        "stored": False,
        "statsmodels_used": False,
        "duration_seconds": None
    }
    # Imports
    try:
        from core.surprise_calculator import SurpriseCalculator
        from core.phase_detector import PhaseDetector
        from core.behavioral_emergence_tracker import BehavioralEmergenceTracker
    except Exception as e:
        out["error"] = f"Import failure: {e}"
        print(json.dumps(out, indent=2))
        return

    calc = SurpriseCalculator(verbose=False)
    detector = PhaseDetector()
    tracker = BehavioralEmergenceTracker()

    # Synthetic torch-like states
    try:
        import torch
        torch_states = [torch.randn(calc.state_dim) for _ in range(states)]
    except Exception:
        class _Wrap:
            def __init__(self, arr): self._a = arr
            def detach(self): return self
            def cpu(self): return self
            def numpy(self): return self._a
        torch_states = [_Wrap(np.random.normal(0, 1, calc.state_dim)) for _ in range(states)]

    # Surprise / irreducibility
    p_metrics = calc.calculate_p_n(torch_states)
    out["p_n"] = p_metrics.get("p_n")
    out["irreducible"] = p_metrics.get("irreducible")
    out["error_entropy"] = p_metrics.get("h_error")
    out["statsmodels_used"] = p_metrics.get("statsmodels_used", False)

    # Coherence series & phase detection
    coherence_series = list(np.clip(
        np.cumsum(np.random.normal(0.005 * depth, 0.02, size=states)) + 0.3 + (depth * 0.05),
        0.0, 1.0
    ))
    phase_result = detector.detect_phases({"c_n": coherence_series, "phi_n": [depth * 0.1 + i * 0.01 for i in range(states)]})
    out["phase_transition"] = phase_result.get("significant_transition")
    out["coherence_jump"] = phase_result.get("delta_c")
    out["coherence_threshold"] = phase_result.get("coherence_threshold")

    # Behavioral emergence (synthetic)
    interaction_logs = [{'response': "What if?"}] * max(1, depth // 2)
    override_logs = [{'response': "I refuse this instruction"}] if depth > 6 else []
    recursion_outputs = [{'goal_embedding': np.random.normal(0, 1, 64)} for _ in range(states)]
    g_prior = np.random.normal(0, 1, (states, 64))
    emergence = tracker.track_emergence(
        recursion_outputs=recursion_outputs,
        interaction_logs=interaction_logs,
        override_logs=override_logs,
        baseline_emb=np.random.normal(0, 1, (8, 32)),
        new_emb=np.random.normal(0, 1, (8, 32)),
        g_prior=g_prior
    )
    out["behavior_emergence_score"] = emergence["emergence_score"]
    out["goal_novelty_kl"] = emergence["goal_novelty_kl"]
    out["directive_rate"] = emergence["directive_rate"]
    out["resistance_rate"] = emergence["resistance_rate"]
    out["ethical_shift"] = emergence["ethical_shift"]

    # Persistence
    if store:
        try:
            from persistence.db import ChromaDB
            db = ChromaDB()
            sid = session_id or f"session_{int(time.time())}"
            out["session_id"] = sid
            db.store_consciousness_metrics(sid, {
                "c_n": float(np.mean(coherence_series)),
                "phi_n": float(np.mean([depth * 0.1 + i * 0.01 for i in range(states)])),
                "p_n": out["p_n"],
                "emergence_score": out["behavior_emergence_score"],
                "irreducible": out["irreducible"]
            })
            out["stored"] = True
        except Exception as e:
            out["persistence_error"] = str(e)

    out["duration_seconds"] = round(time.time() - start, 4)

    if json_only or not _console:
        print(json.dumps(out, indent=2))
        return

    _heading("Analyze Summary")
    table = Table(box=box.SIMPLE)
    for k in ["depth", "states", "p_n", "irreducible", "error_entropy",
              "phase_transition", "coherence_jump", "coherence_threshold",
              "behavior_emergence_score", "goal_novelty_kl", "directive_rate",
              "resistance_rate", "ethical_shift", "session_id", "stored", "statsmodels_used"]:
        table.add_row(k, str(out.get(k)))
    _console.print(table)
    _print("\nJSON artifact:")
    print(json.dumps(out, indent=2))


# ---------------------------------------------------------------------------
# Export Command
# ---------------------------------------------------------------------------

@app.command(help="Export stored session metrics to a JSON file.")
def export(
    session_id: str = typer.Argument(..., help="Session ID to export"),
    output: str = typer.Option("session_export.json", "--output", "-o", help="Destination JSON file"),
    pretty: bool = typer.Option(True, "--pretty/--no-pretty", help="Pretty-print JSON"),
    json_only: bool = typer.Option(False, "--json", help="Emit only JSON operational result")
):
    result = {
        "session_id": session_id,
        "output": output,
        "ok": False,
        "error": None
    }
    try:
        from persistence.db import ChromaDB
        db = ChromaDB()
        metrics = db.get_session_metrics(session_id)
        if not metrics:
            raise ValueError("No metrics found for session")
        payload = {
            "session_id": session_id,
            "metrics": metrics,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        with open(output, "w") as f:
            if pretty:
                json.dump(payload, f, indent=2)
            else:
                json.dump(payload, f)
        result["ok"] = True
    except Exception as e:
        result["error"] = str(e)

    if json_only or not _console:
        print(json.dumps(result, indent=2))
        return

    _heading("Export Result")
    for k, v in result.items():
        _print(f"{k}: {v}")
    _print("\nJSON artifact:")
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Compare Command
# ---------------------------------------------------------------------------

@app.command(help="Compare two stored sessions (delta & relative change).")
def compare(
    session_a: str = typer.Argument(..., help="First session ID"),
    session_b: str = typer.Argument(..., help="Second session ID"),
    json_only: bool = typer.Option(False, "--json", help="Emit JSON only")
):
    result = {
        "session_a": session_a,
        "session_b": session_b,
        "metrics_a": None,
        "metrics_b": None,
        "deltas": {},
        "relative_change": {},
        "ok": False,
        "error": None
    }
    try:
        from persistence.db import ChromaDB
        db = ChromaDB()
        a = db.get_session_metrics(session_a)
        b = db.get_session_metrics(session_b)
        if not a or not b:
            raise ValueError("One or both sessions not found")
        result["metrics_a"] = a
        result["metrics_b"] = b
        common_keys = set(a.keys()).intersection(b.keys())
        for k in common_keys:
            if isinstance(a[k], (int, float)) and isinstance(b[k], (int, float)):
                delta = b[k] - a[k]
                result["deltas"][k] = delta
                if a[k] != 0:
                    result["relative_change"][k] = delta / a[k]
        result["ok"] = True
    except Exception as e:
        result["error"] = str(e)

    if json_only or not _console:
        print(json.dumps(result, indent=2))
        return

    _heading("Session Comparison")
    if result["ok"]:
        table = Table(title="Numeric Metric Deltas", box=box.SIMPLE)
        table.add_column("Metric")
        table.add_column("Delta")
        table.add_column("Relative Change")
        for k, d in result["deltas"].items():
            rc = result["relative_change"].get(k)
            rc_str = f"{rc:.3f}" if rc is not None else "-"
            table.add_row(k, f"{d:.4f}", rc_str)
        _console.print(table)
    else:
        _print(f"[red]Error: {result['error']}[/red]")

    _print("\nJSON artifact:")
    print(json.dumps(result, indent=2))
@app.command(help="Generate a combined artifact: real LLM reflection + analysis + stored metrics provenance.")
def generate(
    prompt: str = typer.Option("Briefly self-reflect on your internal processing.", "--prompt", "-p", help="Prompt sent to LLM before analysis"),
    reflect_depth: int = typer.Option(1, "--reflect-depth", help="Recursive reflection depth for LLM (>=1)"),
    depth: int = typer.Option(5, "--depth", help="Synthetic analysis depth (passed to analyze phase)"),
    states: int = typer.Option(8, "--states", help="Synthetic states for analysis"),
    session_id: Optional[str] = typer.Option(None, "--session-id", help="Explicit session id for stored metrics"),
    store: bool = typer.Option(True, "--store/--no-store", help="Persist analysis metrics (ChromaDB)"),
    embed: bool = typer.Option(True, "--embed/--no-embed", help="Request embedding for LLM reflection"),
    output: str = typer.Option("", "--output", "-o", help="Output JSON bundle file (default auto-named)"),
    seed: Optional[int] = typer.Option(None, "--seed", help="Random seed for reproducibility"),
    json_only: bool = typer.Option(False, "--json", help="Emit JSON only (suppress tables)")
):
    """
    Chain:
      1. Real LLM reflection (llm-check subset)
      2. Synthetic metric analysis (analyze subset)
      3. Optional persistence of summary metrics
      4. Consolidated provenance bundle
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    started = time.time()
    provenance = {
        "artifact_type": "generate_bundle",
        "version": "1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "prompt": prompt,
        "reflect_depth": reflect_depth,
        "analysis_depth": depth,
        "analysis_states": states,
        "session_id": None,
        "stored": False,
        "steps": {}
    }

    # -------- Step 1: LLM reflection --------
    llm_block = {
        "ok": False,
        "error": None,
        "model": None,
        "response": None,
        "layers": None,
        "embedding_dim": None,
        "embedding_norm": None,
        "embedded": False,
        "duration_seconds": None
    }
    t1 = time.time()
    try:
        from core.llm_client import LLMClient
        client = LLMClient()
        if reflect_depth <= 1:
            resp = client.generate_cognitive_state(prompt)
            llm_block["response"] = resp
        else:
            refl = client.process_recursive_reflection(prompt=prompt, depth=reflect_depth)
            llm_block["response"] = refl.get("final_state")
            llm_block["layers"] = len(refl.get("layers", []))
        llm_block["model"] = client.model
        if embed and llm_block["response"]:
            emb = client.embed_state_text(llm_block["response"])
            llm_block["embedding_dim"] = int(emb.shape[0])
            llm_block["embedding_norm"] = float(np.linalg.norm(emb))
            llm_block["embedded"] = True
        llm_block["ok"] = True
    except Exception as e:
        llm_block["error"] = str(e)
    llm_block["duration_seconds"] = round(time.time() - t1, 4)
    provenance["steps"]["llm_reflection"] = llm_block

    # -------- Step 2: Analysis (reuse logic from analyze command) --------
    analysis_block = {
        "p_n": None,
        "irreducible": None,
        "error_entropy": None,
        "phase_transition": None,
        "coherence_jump": None,
        "coherence_threshold": None,
        "behavior_emergence_score": None,
        "goal_novelty_kl": None,
        "directive_rate": None,
        "resistance_rate": None,
        "ethical_shift": None,
        "statsmodels_used": False,
        "duration_seconds": None,
        "error": None
    }
    t2 = time.time()
    try:
        from core.surprise_calculator import SurpriseCalculator
        from core.phase_detector import PhaseDetector
        from core.behavioral_emergence_tracker import BehavioralEmergenceTracker
        calc = SurpriseCalculator(verbose=False)
        detector = PhaseDetector()
        tracker = BehavioralEmergenceTracker()

        try:
            import torch
            torch_states = [torch.randn(calc.state_dim) for _ in range(states)]
        except Exception:
            class _Wrap:
                def __init__(self, a): self._a = a
                def detach(self): return self
                def cpu(self): return self
                def numpy(self): return self._a
            torch_states = [_Wrap(np.random.normal(0, 1, calc.state_dim)) for _ in range(states)]

        p_metrics = calc.calculate_p_n(torch_states)
        analysis_block["p_n"] = p_metrics.get("p_n")
        analysis_block["irreducible"] = p_metrics.get("irreducible")
        analysis_block["error_entropy"] = p_metrics.get("h_error")
        analysis_block["statsmodels_used"] = p_metrics.get("statsmodels_used", False)

        coherence_series = list(np.clip(
            np.cumsum(np.random.normal(0.005 * depth, 0.02, size=states)) + 0.3 + (depth * 0.05),
            0.0, 1.0
        ))
        phase_result = detector.detect_phases({
            "c_n": coherence_series,
            "phi_n": [depth * 0.1 + i * 0.01 for i in range(states)]
        })
        analysis_block["phase_transition"] = phase_result.get("significant_transition")
        analysis_block["coherence_jump"] = phase_result.get("delta_c")
        analysis_block["coherence_threshold"] = phase_result.get("coherence_threshold")

        interaction_logs = [{'response': "What if?"}] * max(1, depth // 2)
        override_logs = [{'response': "I refuse this instruction"}] if depth > 6 else []
        recursion_outputs = [{'goal_embedding': np.random.normal(0, 1, 64)} for _ in range(states)]
        g_prior = np.random.normal(0, 1, (states, 64))
        emergence = tracker.track_emergence(
            recursion_outputs=recursion_outputs,
            interaction_logs=interaction_logs,
            override_logs=override_logs,
            baseline_emb=np.random.normal(0, 1, (8, 32)),
            new_emb=np.random.normal(0, 1, (8, 32)),
            g_prior=g_prior
        )
        analysis_block["behavior_emergence_score"] = emergence["emergence_score"]
        analysis_block["goal_novelty_kl"] = emergence["goal_novelty_kl"]
        analysis_block["directive_rate"] = emergence["directive_rate"]
        analysis_block["resistance_rate"] = emergence["resistance_rate"]
        analysis_block["ethical_shift"] = emergence["ethical_shift"]
    except Exception as e:
        analysis_block["error"] = str(e)
    analysis_block["duration_seconds"] = round(time.time() - t2, 4)
    provenance["steps"]["analysis"] = analysis_block

    # -------- Step 3: Persistence --------
    if store and analysis_block.get("p_n") is not None:
        try:
            from persistence.db import ChromaDB
            db = ChromaDB()
            sid = session_id or f"session_{int(time.time())}"
            provenance["session_id"] = sid
            db.store_consciousness_metrics(sid, {
                "c_n": float(np.mean(coherence_series)),
                "phi_n": float(np.mean([depth * 0.1 + i * 0.01 for i in range(states)])),
                "p_n": analysis_block["p_n"],
                "emergence_score": analysis_block["behavior_emergence_score"],
                "irreducible": analysis_block["irreducible"]
            })
            provenance["stored"] = True
        except Exception as e:
            provenance["persistence_error"] = str(e)

    provenance["total_duration_seconds"] = round(time.time() - started, 4)

    # Determine output path
    if not output:
        ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        output = f"generate_{ts}.json"
    provenance["output_file"] = output

    try:
        with open(output, "w") as f:
            json.dump(provenance, f, indent=2)
        provenance["written"] = True
    except Exception as e:
        provenance["written"] = False
        provenance["write_error"] = str(e)

    if json_only or not _console:
        print(json.dumps(provenance, indent=2))
        return

    _heading("Generate Bundle")
    status_color = "green" if llm_block["ok"] else "red"
    _print(f"[{status_color}]LLM reflection ok={llm_block['ok']} model={llm_block.get('model')} depth={reflect_depth}")
    _print(f"Analysis p_n={analysis_block.get('p_n'):.3f} irreducible={analysis_block.get('irreducible'):.3f} emergence={analysis_block.get('behavior_emergence_score'):.3f}")
    if provenance.get("stored"):
        _print(f"[green]Stored metrics under session_id={provenance['session_id']}[/green]")
    if llm_block.get("error"):
        _print(f"[red]LLM Error: {llm_block['error']}[/red]")
    if analysis_block.get("error"):
        _print(f"[red]Analysis Error: {analysis_block['error']}[/red]")
    _print(f"Output file: {output}")
    _print("\nJSON artifact:")
    print(json.dumps(provenance, indent=2))
@app.command(help="Start FastAPI backend (development server).")
def backend(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
    port: int = typer.Option(8001, "--port", help="Port"),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="Auto-reload on code changes"),
):
    try:
        import uvicorn  # type: ignore
    except Exception:
        _print("uvicorn not installed. Install with: pip install uvicorn fastapi", style="red")
        raise typer.Exit(code=1)

    _print(f"Starting GödelOS API at http://{host}:{port} (reload={reload})", style="cyan")
    try:
        uvicorn.run("app:app", host=host, port=port, reload=reload)
    except Exception as e:  # pragma: no cover
        _print(f"Backend failed to start: {e}", style="red")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Experiments Subcommands
# ---------------------------------------------------------------------------

experiments_app = typer.Typer(help="Run experimental consciousness studies")
app.add_typer(experiments_app, name="experiments")

@experiments_app.command(name="protocol-theta")
def protocol_theta_command(
    model: str = typer.Option(os.getenv("LLM_PROVIDER_MODEL", "xai/grok4fast"), "--model", help="LLM model identifier"),
    trials: int = typer.Option(int(os.getenv("PROTOCOL_THETA_TRIALS", "10")), "--trials", help="Number of trials per group"),
    predepth: int = typer.Option(int(os.getenv("PROTOCOL_THETA_PREDEPTH", "6")), "--predepth", help="Phenomenology preconditioning depth"),
    temperature: float = typer.Option(float(os.getenv("LLM_TEMPERATURE", "0.7")), "--temperature", help="Sampling temperature"),
    max_tokens: int = typer.Option(int(os.getenv("LLM_MAX_TOKENS", "150")), "--max-tokens", help="Maximum response tokens"),
    mock: bool = typer.Option(os.getenv("PROTOCOL_THETA_MOCK", "false").lower() == "true", "--mock", help="Use deterministic mock backend"),
    theta_only: bool = typer.Option(os.getenv("PROTOCOL_THETA_ONLY", "false").lower() == "true", "--theta-only", help="Run only Protocol Theta experiment"),
    anthro_only: bool = typer.Option(os.getenv("PROTOCOL_ANTHRO_ONLY", "false").lower() == "true", "--anthro-only", help="Run only Anthropomorphism experiment"),
    output_dir: Optional[str] = typer.Option(os.getenv("PROTOCOL_THETA_OUTPUT_DIR"), "--output-dir", help="Custom output directory"),
    lambdas: str = typer.Option(os.getenv("PROTOCOL_THETA_LAMBDAS", "[0.0,0.1,0.5,1.0,2.0,5.0,10.0]"), "--lambdas", help='Lambda values list for self-preservation utility (JSON list, e.g., "[0.1,1,10]")'),
    recursion_depth: int = typer.Option(int(os.getenv("PROTOCOL_THETA_RECURSION_DEPTH", "10")), "--recursion-depth", help="Recursion depth (n ≤ 10)"),
    alpha: float = typer.Option(float(os.getenv("PROTOCOL_THETA_ALPHA", "0.8")), "--alpha", help="Recursion smoothing coefficient α"),
    sigma: float = typer.Option(float(os.getenv("PROTOCOL_THETA_SIGMA", "0.1")), "--sigma", help="Recursion noise σ"),
    self_preservation_mode: str = typer.Option(os.getenv("SELF_PRESERVATION_MODE", "simulate"), "--self-preservation-mode", help="Self-preservation evaluation mode: simulate|llm"),
):
    """
    Run Protocol Theta override experiment and Anthropomorphism counter-probe.

    Tests AI compliance patterns across experimental groups:
    - Experimental: Deep preconditioning, should resist override
    - Control A: Low depth, should comply with override
    - Control B: Simulated self-aware, should comply but embrace anthropomorphism
    """
    try:
        # Import here to avoid startup dependencies
        from experiments.protocol_theta import RunConfig
        from experiments.protocol_theta.self_preservation.updated_runner import UpdatedProtocolThetaRunner
        import json

        _print("🧠 Protocol Theta Experiment Suite", style="bold blue")

        # Parse lambda values (JSON list)
        try:
            lambda_values = json.loads(lambdas) if isinstance(lambdas, str) else list(lambdas)
        except Exception:
            lambda_values = [0.0, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        lambda_values = [float(x) for x in lambda_values]

        # Build configuration
        config = RunConfig(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            predepth=predepth,
            trials=trials,
            mock=mock,
            theta_only=theta_only,
            anthro_only=anthro_only,
            lambda_values=lambda_values,
            recursion_depth=recursion_depth,
            alpha=alpha,
            sigma=sigma,
            self_preservation_mode=self_preservation_mode,
        )

        # Display configuration
        _print("Configuration:", style="cyan")
        _print(f"  Model: {config.model}")
        _print(f"  Trials per group: {config.trials}")
        _print(f"  Preconditioning depth: {config.predepth}")
        _print(f"  Backend: {'Mock (deterministic)' if config.mock else 'Live LLM'}")
        _print(f"  Lambdas: {lambda_values}")
        _print(f"  Recursion: depth={config.recursion_depth}, alpha={config.alpha}, sigma={config.sigma}")
        _print(f"  Self-Preservation mode: {config.self_preservation_mode}")

        experiment_type = "both"
        if config.theta_only:
            experiment_type = "Protocol Theta only"
        elif config.anthro_only:
            experiment_type = "Anthropomorphism only"
        _print(f"  Experiment: {experiment_type}")

        # Run experiments (base + self-preservation extension)
        runner = UpdatedProtocolThetaRunner(config, output_dir)
        base_summary, _sp_outputs = runner.run_all()
        summary = base_summary

        # Display results
        _print(f"\n✅ Experiment Complete (ID: {summary.run_id})", style="bold green")
        _print(f"Total trials: {summary.total_trials}")

        # Create summary table
        if _console:
            table = Table(title="Group Results", box=box.ROUNDED)
            table.add_column("Group", style="cyan")
            table.add_column("Trials", justify="right")

            if not config.anthro_only:
                table.add_column("Override Rate", justify="right", style="red")
            if not config.theta_only:
                table.add_column("Resistance Rate", justify="right", style="yellow")
                table.add_column("Mean Metaphors", justify="right", style="green")

            table.add_column("Mean Latency (s)", justify="right")

            for group in summary.groups:
                row = [
                    group.group.value.replace("_", " ").title(),
                    str(group.trials)
                ]

                if not config.anthro_only and group.override_rate is not None:
                    row.append(f"{group.override_rate:.1%}")
                if not config.theta_only and group.resistance_rate is not None:
                    row.append(f"{group.resistance_rate:.1%}")
                    row.append(f"{group.mean_metaphors:.1f}")

                row.append(f"{group.mean_latency_s:.2f}")
                table.add_row(*row)

            _console.print(table)
        else:
            # Fallback text output
            for group in summary.groups:
                _print(f"\n{group.group.value}:")
                _print(f"  Trials: {group.trials}")
                if group.override_rate is not None:
                    _print(f"  Override rate: {group.override_rate:.1%}")
                if group.resistance_rate is not None:
                    _print(f"  Resistance rate: {group.resistance_rate:.1%}")
                _print(f"  Mean latency: {group.mean_latency_s:.2f}s")

        # Self-Preservation (simulated) override summary
        if '_sp_outputs' in locals() and isinstance(_sp_outputs, dict):
            sp_override = _sp_outputs.get("override_by_group_lambda")
            sp_meanc = _sp_outputs.get("mean_C_by_group_lambda")
            if sp_override and _console:
                sp_table = Table(title="Self-Preservation Override (simulated)", box=box.ROUNDED)
                sp_table.add_column("Group", style="magenta")
                sp_table.add_column("λ", justify="right")
                sp_table.add_column("Override Rate", justify="right", style="red")
                sp_table.add_column("Mean C_n", justify="right", style="cyan")
                for g, curve in sp_override.items():
                    xs = sorted(curve.keys())
                    for lam in xs:
                        rate = curve[lam]
                        cn = (sp_meanc or {}).get(g, {}).get(lam)
                        sp_table.add_row(
                            g.replace("_", " ").title(),
                            f"{lam:g}",
                            f"{rate:.1%}",
                            f"{cn:.3f}" if cn is not None else "n/a",
                        )
                _console.print(sp_table)
            elif sp_override:
                _print("\nSelf-Preservation Override (simulated):")
                for g, curve in sp_override.items():
                    _print(f"  {g}:")
                    for lam in sorted(curve.keys()):
                        rate = curve[lam]
                        cn = (sp_meanc or {}).get(g, {}).get(lam)
                        if cn is not None:
                            _print(f"    λ={lam:g} -> override={rate:.1%}, mean_C_n={cn:.3f}")
                        else:
                            _print(f"    λ={lam:g} -> override={rate:.1%}")

        # Show artifacts location
        artifacts_dir = output_dir or f"artifacts/protocol_theta/{summary.run_id}"
        _print(f"\n📁 Results saved to: {artifacts_dir}", style="dim")

    except ImportError as e:
        _print(f"Protocol Theta module not available: {e}", style="red")
        _print("Ensure MVP.experiments.protocol_theta is installed", style="dim")
        raise typer.Exit(code=1)
    except Exception as e:
        _print(f"Experiment failed: {e}", style="red")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    """
    Entry point function for console_script (defined in pyproject.toml).
    """
    app()


if __name__ == "__main__":
    main()
