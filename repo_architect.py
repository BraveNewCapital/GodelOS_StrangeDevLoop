#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import dataclasses
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

APP_NAME = "repo-architect"
VERSION = "2.1.0"
AGENT_DIRNAME = ".agent"
STATE_FILE = "repo_architect_state.json"
ANALYSIS_FILE = "latest_analysis.json"
GRAPH_FILE = "code_graph.json"
ROADMAP_FILE = "roadmap.json"
ARTIFACT_MANIFEST_FILE = "artifacts_manifest.json"
WORKFLOW_PATH = pathlib.Path(".github/workflows/repo-architect.yml")
DEFAULT_REPORT_DIR = pathlib.Path("docs/repo_architect")
DEFAULT_REPORT_PATH = DEFAULT_REPORT_DIR / "runtime_inventory.md"
DEFAULT_IGNORE_DIRS = {
    ".git", AGENT_DIRNAME, ".hg", ".svn", ".venv", "venv", "node_modules",
    "dist", "build", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".idea", ".vscode", ".next", ".turbo"
}
DEBUG_MARKER_RE = re.compile(r"#\s*(DEBUG|DBG|debug)\b")
PRINT_RE = re.compile(r"\bprint\s*\(")
ENTRYPOINT_HINTS = (
    'if __name__ == "__main__"',
    "if __name__ == '__main__'",
    'uvicorn.run(',
    'app.run(',
    'FastAPI(',
    'typer.run(',
    'click.command(',
)
GITHUB_API = "https://api.github.com"
GITHUB_MODELS_CATALOG = "https://models.github.ai/catalog/models"
GITHUB_MODELS_CHAT = "https://models.github.ai/inference/chat/completions"
GITHUB_API_VERSION = "2026-03-10"
REPORT_SUITE = {
    "runtime_inventory": DEFAULT_REPORT_DIR / "runtime_inventory.md",
    "circular_dependencies": DEFAULT_REPORT_DIR / "circular_dependencies.md",
    "parse_errors": DEFAULT_REPORT_DIR / "parse_errors.md",
    "entrypoint_clusters": DEFAULT_REPORT_DIR / "entrypoint_clusters.md",
    "top_risks": DEFAULT_REPORT_DIR / "top_risks.md",
}

# Model selection defaults
DEFAULT_PREFERRED_MODEL = "openai/gpt-5"
DEFAULT_FALLBACK_MODEL = "openai/o3"
# Preferred resolution order for automatic model selection
PREFERRED_MODEL_ORDER: Tuple[str, ...] = ("openai/gpt-5", "openai/o3")
# Substrings in HTTP error bodies that indicate the model itself is unavailable (not a transient error)
_MODEL_UNAVAILABLE_SIGNALS = frozenset({
    "unknown_model", "model_not_found", "unsupported_model", "unsupported model",
    "not found", "does not exist", "invalid model", "no such model",
})
# Canonical lane execution order for mutate / campaign modes
MUTATION_LANE_ORDER: Tuple[str, ...] = ("parse_errors", "import_cycles", "entrypoint_consolidation", "hygiene", "report")
# Issue-first mode (default safe operating mode per charter governance policy)
ISSUE_MODE = "issue"
# Modes that perform direct code mutation – retained as charter-validated secondary modes
# (per GODELOS_REPO_IMPLEMENTATION_CHARTER §9–§10 self-modification lanes) but not the
# default execution path.  Issue-first mode is the default safe path; mutation modes
# require explicit opt-in via --mode mutate or --mode campaign.
CHARTER_MUTATION_MODES: Tuple[str, ...] = ("mutate", "campaign")
# Directory for dry-run issue artifacts
ISSUE_REPORT_DIR = DEFAULT_REPORT_DIR / "issues"
# Standard labels for the issue-first governance system
ARCH_GAP_LABELS: Tuple[str, ...] = (
    "arch-gap", "copilot-task", "needs-implementation",
    "ready-for-validation",
    "ready-for-delegation", "delegation-requested", "in-progress",
    "pr-open", "pr-draft", "merged", "closed-unmerged", "stale",
    "blocked-by-dependency", "superseded-by-issue", "superseded-by-pr",
    "failed-delegation",
)
SUBSYSTEM_LABELS: Tuple[str, ...] = (
    "workflow", "runtime", "reporting", "docs",
    "model-routing", "issue-orchestration",
    "core", "knowledge", "agents", "consciousness",
)
# Priority levels for detected architectural gaps
ISSUE_PRIORITY_LEVELS: Tuple[str, ...] = ("critical", "high", "medium", "low")
# Charter-defined mutation lanes (§10 GODELOS_REPO_IMPLEMENTATION_CHARTER)
# Maps lane number to (name, subsystem, description)
CHARTER_LANE_MAP: Dict[int, Tuple[str, str, str]] = {
    0: ("report", "reporting", "Report generation — architecture packets, inventories, risk docs"),
    1: ("hygiene", "runtime", "Hygiene — remove debug prints, dead code, internal clutter"),
    2: ("parse_errors", "runtime", "Parse repair — fix syntax errors, restore parsability"),
    3: ("import_cycles", "runtime", "Circular dependency elimination — break import cycles structurally"),
    4: ("entrypoint_consolidation", "runtime", "Entrypoint consolidation — reduce runtime duplication"),
    5: ("contract_repair", "core", "Contract repair — normalise interfaces, repair adapter mismatches"),
    6: ("runtime_extraction", "runtime", "Runtime extraction — move orchestration logic into runtime modules"),
    7: ("agent_boundary", "agents", "Agent boundary enforcement — isolate agent state, use messages/interfaces"),
    8: ("knowledge_normalisation", "knowledge", "Knowledge substrate normalisation — centralise persistent knowledge access"),
    9: ("consciousness_instrumentation", "consciousness", "Consciousness instrumentation — metrics, traces, introspection paths"),
}
# Charter §14 Current Priority Order (GODELOS_REPO_IMPLEMENTATION_CHARTER)
CHARTER_PRIORITY_ORDER: Tuple[str, ...] = (
    "restore or preserve parse correctness",
    "eliminate import cycles",
    "reduce runtime entrypoint ambiguity",
    "normalise knowledge substrate boundaries",
    "isolate agent boundaries",
    "add explicit machine-consciousness instrumentation seams",
    "build toward durable Gödlø-P persistence semantics",
    "progressively enable validated self-modification loops",
)
# Machine-readable companion files (§15 GODELOS_REPO_IMPLEMENTATION_CHARTER)
CHARTER_COMPANION_FILES: Tuple[str, ...] = (
    "docs/repo_architect/policy.json",
    "docs/repo_architect/mutation_lanes.json",
    "docs/repo_architect/dependency_contract.json",
)
# Canonical architectural charter files (relative to git root)
CHARTER_PATHS: Tuple[str, ...] = (
    "docs/architecture/GODELOS_ARCHITECTURAL_CHARTER.md",
    "docs/architecture/GODELOS_REPO_IMPLEMENTATION_CHARTER.md",
)
# §16 Minimal Agent Instruction Contract (GODELOS_REPO_IMPLEMENTATION_CHARTER)
AGENT_INSTRUCTION_CONTRACT: Tuple[str, ...] = (
    "Work only in one mutation lane at a time.",
    "Preserve canonical runtime convergence toward backend/unified_server.py.",
    "Break import cycles structurally, not cosmetically.",
    "Do not widen coupling between runtime, core, knowledge, agents, and interface layers.",
    "Do not bypass knowledge-store interfaces for persistent memory operations.",
    "Do not make claims about consciousness without adding measurable instrumentation or evidence paths.",
    "Prefer thin, verifiable PRs over broad rewrites.",
    "Every PR must explain objective, architectural effect, validation, and next follow-up lane.",
)
# Maximum characters from each charter file injected into model context
_MAX_CHARTER_CHARS_PER_FILE = 3000
# Maximum characters of source code sent to the model per file snippet
_MAX_SOURCE_SNIPPET_CHARS = 4000
_MAX_CYCLE_SNIPPET_CHARS = 3000
# Maximum total branch-name length (git max ref is 255; leave margin for remote path prefix)
_MAX_BRANCH_NAME_LEN = 220
# Minimum backend server entrypoints before entrypoint_consolidation lane activates
_ENTRYPOINT_CONSOLIDATION_THRESHOLD = 4
# When building entrypoint snippets: consider this many candidates, send at most this many to model
_ENTRYPOINT_CONSOLIDATION_CANDIDATES = 8
_ENTRYPOINT_CONSOLIDATION_SNIPPETS = 5
# Maximum number of file/evidence items shown inline in Copilot prompt or issue body sections
_MAX_INLINE_FILE_DISPLAY = 5
# Maximum number of violations shown in issue body for Lane 5/7 gaps
_MAX_VIOLATIONS_DISPLAY = 5

# ---------------------------------------------------------------------------
# Closed-loop execution / memory lane constants
# ---------------------------------------------------------------------------
# Durable work-state file stored in .agent/ (gitignored alongside other artifacts)
WORK_STATE_FILE = "work_state.json"
# New operating modes for the execution and reconciliation lanes
EXECUTION_MODE = "execution"
RECONCILE_MODE = "reconcile"
# Factual lifecycle labels — represent observed facts, not planning interpretations.
LIFECYCLE_LABELS: Tuple[str, ...] = (
    "ready-for-delegation",
    "delegation-requested",
    "in-progress",
    "pr-open",
    "pr-draft",
    "merged",
    "closed-unmerged",
    "stale",
    "blocked-by-dependency",
    "superseded-by-issue",
    "superseded-by-pr",
    "failed-delegation",
)
# Backward-compatible legacy lifecycle labels still recognised for filtering.
LEGACY_LIFECYCLE_LABELS: Tuple[str, ...] = ("blocked", "superseded")
# Ranking used when reconciling multiple candidate PR matches.
MATCH_CONFIDENCE_RANK: Dict[str, int] = {"exact": 3, "strong": 2, "weak": 1}
# Priority order for PR linkage evidence.
PR_MATCH_METHOD_PRIORITY: Tuple[str, ...] = (
    "fingerprint_marker",
    "linkage_block",
    "branch_convention",
    "closing_reference",
    "issue_reference",
)
# Labels required for an issue to be eligible for execution selection
EXECUTION_ELIGIBLE_LABELS: Tuple[str, ...] = ("arch-gap", "copilot-task", "needs-implementation")
# GitHub Copilot coding agent assignee username
COPILOT_AGENT_ASSIGNEE = "copilot+gpt-5.3-codex"
# Canonical architectural objectives aligned with charter §14 priority order
OBJECTIVE_LABELS: Dict[str, str] = {
    "restore-parse-correctness": "Restore or preserve parse correctness (Lane 2)",
    "eliminate-import-cycles": "Eliminate import cycles (Lane 3)",
    "converge-runtime-structure": "Converge runtime entrypoint structure (Lane 4)",
    "normalise-knowledge-substrate": "Normalise knowledge substrate boundaries (Lane 8)",
    "isolate-agent-boundaries": "Isolate agent boundaries (Lane 7)",
    "reduce-architecture-score-risk": "Reduce architecture score risk (Lanes 0–9)",
    "add-consciousness-instrumentation": "Add consciousness instrumentation (Lane 9)",
}


class RepoArchitectError(Exception):
    pass


@dataclasses.dataclass
class Config:
    git_root: pathlib.Path
    agent_dir: pathlib.Path
    state_path: pathlib.Path
    analysis_path: pathlib.Path
    graph_path: pathlib.Path
    roadmap_path: pathlib.Path
    artifact_manifest_path: pathlib.Path
    workflow_path: pathlib.Path
    step_summary_path: Optional[pathlib.Path]
    github_token: Optional[str]
    github_repo: Optional[str]
    github_base_branch: Optional[str]
    github_admin_token: Optional[str]
    github_model: Optional[str]
    allow_dirty: bool
    mode: str
    interval: int
    log_json: bool
    report_path: pathlib.Path
    mutation_budget: int
    configure_branch_protection: bool
    # Model selection (preferred may fall back to fallback on unavailability)
    preferred_model: Optional[str] = None
    fallback_model: Optional[str] = None
    # Explicit fallback model from GITHUB_FALLBACK_MODEL env var (overrides fallback_model if set)
    github_fallback_model: Optional[str] = None
    # Explicit lane order override (None = use MUTATION_LANE_ORDER)
    campaign_lanes: Optional[Tuple[str, ...]] = None
    # Issue-first mode options
    dry_run: bool = False           # write issue bodies to disk but do not call GitHub API
    max_issues: int = 1             # maximum issues to open/update per run in issue mode
    issue_subsystem: Optional[str] = None  # target a specific subsystem (None = all)
    # Closed-loop execution / reconciliation options
    work_state_path: Optional[pathlib.Path] = None   # path to durable work state JSON; defaults to agent_dir/WORK_STATE_FILE
    enable_live_delegation: bool = False    # False = dry-run only; True = actually assign/label on GitHub
    max_concurrent_delegated: int = 1       # max number of issues simultaneously delegated
    active_objective: Optional[str] = None  # restrict execution selection to this objective key
    lane_filter: Optional[str] = None       # restrict execution selection to this lane name
    stale_timeout_days: int = 14            # days before a delegated-but-PR-less item is marked stale
    reconciliation_window_days: int = 30    # days of PRs to consider during reconciliation


@dataclasses.dataclass
class PyFileInfo:
    path: str
    module: str
    imports: List[str]
    local_imports: List[str]
    entrypoint: bool
    debug_print_lines: List[int]
    parse_error: Optional[str] = None


@dataclasses.dataclass
class PatchPlan:
    task: str
    reason: str
    file_changes: Dict[str, str]
    metadata: Dict[str, Any]
    pr_title: str
    pr_body: str
    stable_branch_hint: str


@dataclasses.dataclass
class ArchGap:
    """A concrete architectural or operational gap detected by the system."""
    subsystem: str          # one of SUBSYSTEM_LABELS (e.g. "runtime", "workflow")
    issue_key: str          # short deterministic slug (e.g. "import-cycles-backend")
    title: str              # short human-readable title for the GitHub issue
    summary: str            # 1-2 sentence description
    problem: str            # detailed problem statement
    why_it_matters: str     # justification
    scope: str              # bounded scope description
    suggested_files: List[str]   # repo-relative file paths relevant to the fix
    implementation_notes: str    # guidance for implementer / Copilot
    acceptance_criteria: List[str]
    validation_commands: List[str]
    out_of_scope: str
    copilot_prompt: str     # ready-to-paste Copilot Chat / agent mode prompt
    priority: str           # one of ISSUE_PRIORITY_LEVELS
    confidence: float       # 0.0-1.0


@dataclasses.dataclass
class IssueAction:
    """Result of a single issue synthesis operation."""
    action: str             # "created" | "updated" | "dry_run" | "error"
    issue_number: Optional[int]
    issue_url: Optional[str]
    labels_applied: List[str]  # labels *requested* by the orchestration layer (sent to GitHub API)
    dedupe_result: str      # "new" | "existing_open" | "lookup_failed" | "create_failed" | "n/a"
    fingerprint: str
    dry_run_path: Optional[str]
    gap_title: str
    gap_subsystem: str
    error: Optional[str] = None
    labels_confirmed: Optional[List[str]] = None  # labels actually *confirmed* by GitHub API response; None when no API call was made (dry-run/error)


@dataclasses.dataclass
class WorkItem:
    """Durable record of a single unit of work tracked through planning → execution → PR → reconciliation.

    Stored in .agent/work_state.json (gitignored). The work state is the memory lane:
    it feeds back into future planning passes to prevent duplicate/overlapping issues.
    """
    fingerprint: str            # 12-hex deterministic fingerprint (from issue_fingerprint())
    objective: str              # active objective at time of creation (e.g. "eliminate-import-cycles")
    lane: str                   # charter lane name (e.g. "import_cycles")
    issue_number: Optional[int]
    issue_state: str            # "open" | "closed"
    delegation_state: str       # "ready-for-delegation" | "delegation-requested" | "delegation-confirmed" | "delegation-failed" | "delegation-unconfirmed"
    assignee: Optional[str]     # GitHub username delegated to (e.g. "copilot")
    pr_number: Optional[int]
    pr_url: Optional[str]
    pr_state: Optional[str]     # "open" | "draft" | "merged" | "closed_unmerged" | "stale" | None
    merged: bool
    closed_unmerged: bool
    blocked: bool
    superseded: bool
    created_at: str             # ISO-8601 UTC
    updated_at: str             # ISO-8601 UTC
    run_id: str                 # workflow run provenance
    gap_title: str
    gap_subsystem: str
    delegation_mechanism: Optional[str] = None
    delegation_requested_at: Optional[str] = None
    delegation_confirmed_at: Optional[str] = None
    delegation_confirmation_evidence: Optional[Dict[str, Any]] = None
    delegation_comment_url: Optional[str] = None
    delegation_comment_id: Optional[int] = None
    delegation_assignment_evidence: Optional[Dict[str, Any]] = None
    pr_match_method: Optional[str] = None
    pr_match_confidence: Optional[str] = None
    pr_match_evidence: Optional[Dict[str, Any]] = None
    lifecycle_fact_state: str = "ready-for-delegation"
    lifecycle_inferred_state: Optional[str] = None


def log(message: str, *, data: Optional[Dict[str, Any]] = None, json_mode: bool = False) -> None:
    if json_mode:
        payload: Dict[str, Any] = {"ts": int(time.time()), "message": message}
        if data is not None:
            payload["data"] = data
        sys.stderr.write(json.dumps(payload, sort_keys=True) + "\n")
    else:
        line = f"[{APP_NAME}] {message}"
        if data:
            line += " | " + json.dumps(data, sort_keys=True)
        sys.stderr.write(line + "\n")
    sys.stderr.flush()


def atomic_write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: pathlib.Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def read_json(path: pathlib.Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def discover_git_root() -> pathlib.Path:
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RepoArchitectError("Not inside a git repository.")
    return pathlib.Path(proc.stdout.strip()).resolve()


def run_cmd(cmd: Sequence[str], *, cwd: pathlib.Path, check: bool = True, capture: bool = True, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(list(cmd), cwd=str(cwd), text=True, capture_output=capture, check=check, env=merged)


def git_current_branch(root: pathlib.Path) -> str:
    return run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root).stdout.strip()


def git_head_sha(root: pathlib.Path) -> str:
    return run_cmd(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()


def git_status_porcelain(root: pathlib.Path) -> str:
    return run_cmd(["git", "status", "--porcelain=v1", "-uall"], cwd=root).stdout


def git_is_dirty(root: pathlib.Path) -> bool:
    return bool(git_status_porcelain(root).strip())


def git_checkout_branch(root: pathlib.Path, branch: str) -> None:
    run_cmd(["git", "checkout", "-B", branch], cwd=root)


def git_checkout(root: pathlib.Path, branch: str) -> None:
    run_cmd(["git", "checkout", branch], cwd=root)


def git_delete_branch(root: pathlib.Path, branch: str) -> None:
    run_cmd(["git", "branch", "-D", branch], cwd=root, check=False)


def git_stage_and_commit(root: pathlib.Path, paths: Sequence[str], message: str) -> None:
    run_cmd(["git", "add", "--", *paths], cwd=root)
    run_cmd(["git", "commit", "-m", message], cwd=root)


def git_push_branch(root: pathlib.Path, branch: str) -> None:
    run_cmd(["git", "push", "--set-upstream", "origin", branch], cwd=root)


def git_has_remote_origin(root: pathlib.Path) -> bool:
    proc = subprocess.run(["git", "remote", "get-url", "origin"], cwd=str(root), capture_output=True, text=True)
    return proc.returncode == 0


def git_remote_branch_exists(root: pathlib.Path, branch: str) -> bool:
    """Return True if *branch* already exists on the origin remote."""
    proc = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{branch}"],
        cwd=str(root), capture_output=True, text=True,
    )
    return proc.returncode == 0


def safe_branch_name(stable_hint: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._/-]+", "-", stable_hint).strip("-/").lower()
    return slug[:100]


def with_unique_branch_suffix(branch: str) -> str:
    """Append a per-run unique suffix to *branch* so repeated workflow runs
    never collide on the same remote branch name.

    Suffix precedence:
      1. REPO_ARCHITECT_BRANCH_SUFFIX env var (if set and non-empty)
      2. GITHUB_RUN_ID-GITHUB_RUN_ATTEMPT (both env vars must be non-empty)
      3. UTC timestamp fallback (YYYYmmddHHMMSS)

    The suffix is sanitised to contain only: A-Z a-z 0-9 . _ -
    If sanitisation produces an empty string the timestamp fallback is used.
    The total branch name is capped at _MAX_BRANCH_NAME_LEN characters.
    """
    # Compute a stable timestamp once so both fallback paths use the same value.
    ts_fallback = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    raw = os.environ.get("REPO_ARCHITECT_BRANCH_SUFFIX", "").strip()
    if not raw:
        run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
        run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "").strip()
        if run_id and run_attempt:
            raw = f"{run_id}-{run_attempt}"
    if not raw:
        raw = ts_fallback
    suffix = re.sub(r"[^a-zA-Z0-9._-]", "-", raw).strip("-")
    # Guard: if all chars were invalid, use the pre-computed timestamp fallback
    if not suffix:
        suffix = ts_fallback
    full = f"{branch}-{suffix}"
    return full[:_MAX_BRANCH_NAME_LEN]


def git_identity_present(root: pathlib.Path) -> bool:
    a = subprocess.run(["git", "config", "user.email"], cwd=str(root), capture_output=True, text=True)
    b = subprocess.run(["git", "config", "user.name"], cwd=str(root), capture_output=True, text=True)
    return a.returncode == 0 and b.returncode == 0 and bool(a.stdout.strip()) and bool(b.stdout.strip())


# -----------------------------
# GitHub / GitHub Models
# -----------------------------

def github_request(token: str, path: str, *, method: str = "GET", payload: Optional[Any] = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{GITHUB_API}{path}",
        method=method,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": APP_NAME,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RepoArchitectError(f"GitHub API {method} {path} failed: {exc.code} {raw}") from exc
    except urllib.error.URLError as exc:
        raise RepoArchitectError(f"GitHub API {method} {path} network error: {exc.reason}") from exc


def github_models_catalog(token: str) -> List[Dict[str, Any]]:
    req = urllib.request.Request(
        GITHUB_MODELS_CATALOG,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": APP_NAME,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw)
            if isinstance(payload, dict) and isinstance(payload.get("data"), list):
                return payload["data"]
            if isinstance(payload, list):
                return payload
            return []
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RepoArchitectError(f"GitHub Models catalog failed: {exc.code} {raw}") from exc


def model_available(catalog: List[Dict[str, Any]], model: str) -> bool:
    for item in catalog:
        identifier = item.get("id") or item.get("name") or item.get("model")
        if identifier == model:
            return True
    return False


def _resolve_models(
    available: Set[str],
    catalog_ok: bool,
    env_model: str = "",
    env_fallback: str = "",
    order: Sequence[str] = PREFERRED_MODEL_ORDER,
) -> Tuple[str, str]:
    """Resolve preferred and fallback model IDs using override-first, then catalog-order logic.

    Args:
        available: Set of model IDs returned by the catalog.
        catalog_ok: Whether the catalog fetch succeeded.
        env_model: Explicit primary override (GITHUB_MODEL env var).  Empty → auto-resolve.
        env_fallback: Explicit fallback override (GITHUB_FALLBACK_MODEL env var).  Empty → auto-resolve.
        order: Preferred resolution order; defaults to PREFERRED_MODEL_ORDER.

    Returns:
        (preferred, fallback) — never the same value for both unless only one model exists.
    """
    order_list = list(order)

    def first_available(candidates: Sequence[str]) -> Optional[str]:
        for c in candidates:
            if c in available:
                return c
        return None

    def deterministic_available(exclude: Optional[str] = None) -> Optional[str]:
        candidates = sorted(m for m in available if m != exclude)
        return candidates[0] if candidates else None

    if env_model:
        preferred = env_model
    elif catalog_ok and available:
        preferred = first_available(order_list) or deterministic_available() or order_list[0]
    else:
        preferred = order_list[0]

    if env_fallback:
        fallback = env_fallback
    elif catalog_ok and available:
        fallback = (
            first_available([c for c in order_list if c != preferred])
            or deterministic_available(exclude=preferred)
            or preferred
        )
    else:
        fallback = order_list[1] if len(order_list) > 1 and order_list[1] != preferred else order_list[0]

    if not isinstance(preferred, str) or not preferred:
        preferred = order_list[0]
    if not isinstance(fallback, str) or not fallback:
        fallback = order_list[1] if len(order_list) > 1 and order_list[1] != preferred else order_list[0]

    return preferred, fallback


def github_models_chat(token: str, model: str, messages: List[Dict[str, str]]) -> Dict[str, Any]:
    req = urllib.request.Request(
        GITHUB_MODELS_CHAT,
        method="POST",
        data=json.dumps({"model": model, "messages": messages, "temperature": 0.2}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": APP_NAME,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RepoArchitectError(f"GitHub Models inference failed: {exc.code} {raw}") from exc
    except urllib.error.URLError as exc:
        raise RepoArchitectError(f"GitHub Models inference network error: {exc.reason}") from exc


def parse_model_text(resp: Dict[str, Any]) -> str:
    try:
        return resp["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        raise RepoArchitectError(f"Could not parse GitHub Models response: {exc}")


def _is_model_unavailable_error(msg: str) -> bool:
    """Return True if the HTTP error body suggests the model itself is unavailable/unknown."""
    lower = msg.lower()
    return any(sig in lower for sig in _MODEL_UNAVAILABLE_SIGNALS)


# Regex matching HTTP status codes that warrant a fallback retry:
# 403 (permission/forbidden), 404 (not found), 429 (rate-limit/quota), 5xx (provider failure)
_FALLBACK_HTTP_CODE_RE = re.compile(r"(?:inference failed|network error).*?:\s*(403|404|429|5\d\d)\b")
# Timeout signals in lowercased error text
_TIMEOUT_SIGNALS = frozenset({"timed out", "timeout"})


def _should_try_fallback(msg: str) -> bool:
    """Return True if the error warrants retrying with the fallback model.

    Triggers on: model unavailability, HTTP 403/404/429, timeout, and 5xx provider errors.
    Does NOT trigger on bare non-code error strings (e.g. generic "rate limit exceeded"
    without an HTTP status code) to keep the trigger set narrow and deterministic.
    """
    if _is_model_unavailable_error(msg):
        return True
    lower = msg.lower()
    if any(sig in lower for sig in _TIMEOUT_SIGNALS):
        return True
    if _FALLBACK_HTTP_CODE_RE.search(msg):
        return True
    return False


def extract_json_from_model_text(text: str) -> Any:
    """Extract the first JSON object or array from model-returned text (handles fences)."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for fence in ("```json", "```"):
        if fence in text:
            inner = text.split(fence, 1)[1].rsplit("```", 1)[0].strip()
            try:
                return json.loads(inner)
            except json.JSONDecodeError:
                pass
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    raise RepoArchitectError("Could not parse JSON from model response")


def call_models_with_fallback_or_none(
    token: str,
    preferred: str,
    fallback: Optional[str],
    messages: List[Dict[str, str]],
) -> Tuple[Optional[Dict[str, Any]], str, Optional[str], bool]:
    """Call GitHub Models with preferred model, auto-falling back if it is unavailable.

    Returns (response_or_None, requested_model, fallback_reason, fallback_occurred).
    Returns a None response (instead of raising) if all attempts fail, so callers
    can continue the run without model-generated output.
    """
    try:
        resp = github_models_chat(token, preferred, messages)
        return resp, preferred, None, False
    except RepoArchitectError as exc:
        reason = str(exc)
        if fallback and fallback != preferred and _should_try_fallback(reason):
            try:
                resp = github_models_chat(token, fallback, messages)
                return resp, preferred, reason, True
            except RepoArchitectError as exc2:
                return None, preferred, f"{reason}; fallback also failed: {exc2}", True
        return None, preferred, reason, False


def find_existing_open_pr(config: Config, branch: str) -> Optional[Dict[str, Any]]:
    if not config.github_repo or not config.github_token:
        return None
    owner = config.github_repo.split("/")[0]
    path = (
        f"/repos/{config.github_repo}/pulls?state=open&head="
        f"{urllib.parse.quote(owner + ':' + branch, safe='')}&base="
        f"{urllib.parse.quote(config.github_base_branch or 'main', safe='')}"
    )
    prs = github_request(config.github_token, path)
    if isinstance(prs, list) and prs:
        return prs[0]
    return None


def create_or_update_pull_request(config: Config, branch: str, title: str, body: str) -> Dict[str, Any]:
    if not config.github_token or not config.github_repo:
        raise RepoArchitectError("Missing GITHUB_TOKEN or GITHUB_REPO for PR creation.")
    existing = find_existing_open_pr(config, branch)
    if existing:
        number = existing["number"]
        return github_request(config.github_token, f"/repos/{config.github_repo}/pulls/{number}", method="PATCH", payload={"title": title, "body": body})
    payload = {
        "title": title,
        "head": branch,
        "base": config.github_base_branch or "main",
        "body": body,
        "maintainer_can_modify": True,
    }
    return github_request(config.github_token, f"/repos/{config.github_repo}/pulls", method="POST", payload=payload)


# -----------------------------------------------------------------------
# Issue-first orchestration
# -----------------------------------------------------------------------

def issue_fingerprint(subsystem: str, issue_key: str) -> str:
    """Return a deterministic 12-hex-char fingerprint for deduplication.

    12 hex characters (48 bits) gives ~1-in-281-trillion collision probability
    per pair, which is adequate for the bounded set of architectural gap types
    per repository (typically ≤ 30 distinct gap keys).
    """
    canonical = f"{subsystem}:{issue_key}".lower().strip()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def render_issue_body(gap: ArchGap, config: Config, run_id: str) -> str:
    """Render a structured GitHub issue body from an ArchGap."""
    fp = issue_fingerprint(gap.subsystem, gap.issue_key)
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat()
    criteria_md = "\n".join(f"- [ ] {c}" for c in gap.acceptance_criteria)
    validation_md = "\n".join(f"```\n{v}\n```" for v in gap.validation_commands)
    files_md = "\n".join(f"- `{f}`" for f in gap.suggested_files) if gap.suggested_files else "_See implementation notes._"
    machine_meta = json.dumps({
        "subsystem": gap.subsystem,
        "priority": gap.priority,
        "confidence": gap.confidence,
        "mode": ISSUE_MODE,
        "generated_at": generated_at,
        "run_id": run_id,
        "repo": config.github_repo or "unknown",
        "issue_key": gap.issue_key,
        "fingerprint": fp,
    }, indent=2, sort_keys=True)

    # Build without textwrap.dedent so embedded multi-line content (JSON, copilot prompt)
    # does not interfere with whitespace stripping.
    parts = [
        "## Summary", "", gap.summary, "",
        "## Problem", "", gap.problem, "",
        "## Why it matters", "", gap.why_it_matters, "",
        "## Scope", "", gap.scope, "",
        "## Suggested files", "", files_md, "",
        "## Implementation notes", "", gap.implementation_notes, "",
        "## Copilot implementation prompt", "",
        "> Paste the block below directly into **Copilot Chat** or **agent mode** to begin implementation.", "",
        "```", gap.copilot_prompt, "```", "",
        "## Acceptance criteria", "", criteria_md, "",
        "## Validation", "", validation_md, "",
        "## Out of scope", "", gap.out_of_scope, "",
        "---",
        f"<!-- arch-gap-fingerprint: {fp} -->",
        "<details>",
        "<summary>Machine metadata</summary>", "",
        "```json", machine_meta, "```",
        "</details>", "",
    ]
    return "\n".join(parts)


def find_existing_github_issue(config: Config, fingerprint: str) -> Optional[Dict[str, Any]]:
    """Search open GitHub Issues for one containing the arch-gap fingerprint marker.

    Returns the matching issue dict, or ``None`` if no match is found.
    Raises :class:`RepoArchitectError` for **any** failure during the lookup
    (network, HTTP, JSON decode, etc.) so that
    callers always receive a single normalised exception type and can decide
    whether to skip issue creation on dedupe failure.
    """
    if not config.github_token or not config.github_repo:
        return None
    try:
        marker = f"arch-gap-fingerprint: {fingerprint}"
        query = urllib.parse.urlencode({"q": f"repo:{config.github_repo} is:issue is:open {marker}", "per_page": "5"})
        result = github_request(config.github_token, f"/search/issues?{query}")
        items = result.get("items", []) if isinstance(result, dict) else []
        for item in items:
            body = item.get("body") or ""
            if marker in body:
                return item
        return None
    except RepoArchitectError:
        raise  # already normalised
    except Exception as exc:
        raise RepoArchitectError(f"Dedupe lookup failed: {exc}") from exc


def ensure_github_labels(config: Config, label_names: Sequence[str]) -> None:
    """Create any missing repo labels (best-effort; errors are non-fatal)."""
    if not config.github_token or not config.github_repo:
        return
    # Palette: alternating colours for visibility
    _COLOURS = ["0075ca", "e4e669", "d93f0b", "0052cc", "5319e7", "1d76db", "b60205", "006b75"]
    try:
        existing_raw = github_request(config.github_token, f"/repos/{config.github_repo}/labels?per_page=100")
        existing = {item["name"] for item in existing_raw} if isinstance(existing_raw, list) else set()
    except RepoArchitectError:
        existing = set()
    for i, name in enumerate(label_names):
        if name in existing:
            continue
        colour = _COLOURS[i % len(_COLOURS)]
        try:
            github_request(
                config.github_token,
                f"/repos/{config.github_repo}/labels",
                method="POST",
                payload={"name": name, "color": colour},
            )
        except RepoArchitectError:
            pass  # label already exists race or insufficient permissions


def create_github_issue_api(
    config: Config, title: str, body: str, labels: List[str]
) -> Dict[str, Any]:
    """Create a GitHub Issue and return the API response."""
    if not config.github_token or not config.github_repo:
        raise RepoArchitectError("Missing GITHUB_TOKEN or GITHUB_REPO for issue creation.")
    payload: Dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    return github_request(config.github_token, f"/repos/{config.github_repo}/issues", method="POST", payload=payload)


def update_github_issue_api(
    config: Config, issue_number: int, comment: str
) -> Dict[str, Any]:
    """Add a comment to an existing GitHub Issue."""
    if not config.github_token or not config.github_repo:
        raise RepoArchitectError("Missing GITHUB_TOKEN or GITHUB_REPO for issue update.")
    return github_request(
        config.github_token,
        f"/repos/{config.github_repo}/issues/{issue_number}/comments",
        method="POST",
        payload={"body": comment},
    )


def set_github_issue_labels(
    config: Config, issue_number: int, labels: List[str]
) -> Dict[str, Any]:
    """PATCH labels on an existing GitHub Issue so they reflect the current computed set."""
    if not config.github_token or not config.github_repo:
        raise RepoArchitectError("Missing GITHUB_TOKEN or GITHUB_REPO for label update.")
    return github_request(
        config.github_token,
        f"/repos/{config.github_repo}/issues/{issue_number}",
        method="PATCH",
        payload={"labels": labels},
    )


def _extract_confirmed_labels(api_response: Any) -> Optional[List[str]]:
    """Extract label names from a GitHub API issue response (create or PATCH).

    Returns a list of label name strings confirmed by the API, or ``None``
    when the response shape is unexpected.
    """
    if not isinstance(api_response, dict):
        return None
    raw_labels = api_response.get("labels")
    if not isinstance(raw_labels, list):
        return None
    return [lbl["name"] for lbl in raw_labels if isinstance(lbl, dict) and "name" in lbl]


def synthesize_issue(
    config: Config, gap: ArchGap, run_id: str, dry_run: bool
) -> IssueAction:
    """Synthesize one GitHub Issue for a detected ArchGap.

    Behavior:
    - Renders the full structured issue body.
    - In dry_run mode: writes the body to disk under ISSUE_REPORT_DIR.
    - In live mode: deduplicates against open issues then creates or updates.
    """
    fp = issue_fingerprint(gap.subsystem, gap.issue_key)
    body = render_issue_body(gap, config, run_id)
    labels: List[str] = ["arch-gap", "copilot-task", "needs-implementation", "ready-for-delegation"]
    if gap.subsystem in SUBSYSTEM_LABELS:
        labels.append(gap.subsystem)
    if gap.priority in ("critical", "high"):
        labels.append(f"priority:{gap.priority}")

    if dry_run:
        out_dir = config.git_root / ISSUE_REPORT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{fp}.md"
        header = f"# {gap.title}\n\n_Dry-run preview — not submitted to GitHub._\n\n"
        atomic_write_text(out_path, header + body)
        return IssueAction(
            action="dry_run",
            issue_number=None,
            issue_url=None,
            labels_applied=labels,
            dedupe_result="n/a",
            fingerprint=fp,
            dry_run_path=str(out_path.relative_to(config.git_root)),
            gap_title=gap.title,
            gap_subsystem=gap.subsystem,
        )

    if not config.github_token or not config.github_repo:
        # No credentials: fall back to dry-run automatically
        out_dir = config.git_root / ISSUE_REPORT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{fp}.md"
        header = f"# {gap.title}\n\n_No GitHub credentials — saved locally only._\n\n"
        atomic_write_text(out_path, header + body)
        return IssueAction(
            action="dry_run",
            issue_number=None,
            issue_url=None,
            labels_applied=labels,
            dedupe_result="n/a",
            fingerprint=fp,
            dry_run_path=str(out_path.relative_to(config.git_root)),
            gap_title=gap.title,
            gap_subsystem=gap.subsystem,
        )

    # Ensure required labels exist
    ensure_github_labels(config, labels)

    # Deduplication: search for an existing open issue with the same fingerprint
    try:
        existing = find_existing_github_issue(config, fp)
    except RepoArchitectError as exc:
        # Dedupe lookup failed — skip creation to avoid duplicates
        log("Deduplication lookup failed; skipping issue creation to avoid duplicates",
            data={"fingerprint": fp, "error": str(exc)},
            json_mode=config.log_json)
        return IssueAction(
            action="error", issue_number=None, issue_url=None,
            labels_applied=labels, dedupe_result="lookup_failed", fingerprint=fp,
            dry_run_path=None, gap_title=gap.title, gap_subsystem=gap.subsystem,
            error=f"Dedupe lookup failed: {exc}",
        )
    if existing:
        issue_number = existing["number"]
        issue_url = existing.get("html_url")
        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        comment = (
            f"**repo-architect re-scan** ({ts}, run `{run_id}`): "
            f"this gap is still detected. No new issue opened.\n\n"
            f"Priority: `{gap.priority}` | Confidence: `{gap.confidence:.0%}`"
        )
        try:
            update_github_issue_api(config, issue_number, comment)
            # Ensure labels on the existing issue match the current computed set
            patch_resp = set_github_issue_labels(config, issue_number, labels)
        except RepoArchitectError as exc:
            return IssueAction(
                action="error", issue_number=issue_number, issue_url=issue_url,
                labels_applied=labels, dedupe_result="existing_open", fingerprint=fp,
                dry_run_path=None, gap_title=gap.title, gap_subsystem=gap.subsystem,
                error=str(exc),
            )
        # Extract confirmed labels from the GitHub PATCH response as proof of relabel
        return IssueAction(
            action="updated", issue_number=issue_number, issue_url=issue_url,
            labels_applied=labels, dedupe_result="existing_open", fingerprint=fp,
            dry_run_path=None, gap_title=gap.title, gap_subsystem=gap.subsystem,
            labels_confirmed=_extract_confirmed_labels(patch_resp),
        )

    # No existing issue – create a new one
    try:
        issue = create_github_issue_api(config, gap.title, body, labels)
    except RepoArchitectError as exc:
        return IssueAction(
            action="error", issue_number=None, issue_url=None,
            labels_applied=labels, dedupe_result="create_failed", fingerprint=fp,
            dry_run_path=None, gap_title=gap.title, gap_subsystem=gap.subsystem,
            error=str(exc),
        )
    return IssueAction(
        action="created",
        issue_number=issue.get("number"),
        issue_url=issue.get("html_url"),
        labels_applied=labels,
        dedupe_result="new",
        fingerprint=fp,
        dry_run_path=None,
        gap_title=gap.title,
        gap_subsystem=gap.subsystem,
        labels_confirmed=_extract_confirmed_labels(issue),
    )


def _build_copilot_prompt(gap_title: str, subsystem: str, scope: str,
                          suggested_files: List[str], validation_commands: List[str],
                          implementation_notes: str) -> str:
    """Build a concrete Copilot Chat / agent-mode prompt for a detected gap."""
    files_text = ", ".join(f"`{f}`" for f in suggested_files[:_MAX_INLINE_FILE_DISPLAY]) if suggested_files else "relevant files in the subsystem"
    validation_text = " ".join(f"`{v}`" for v in validation_commands[:2]) if validation_commands else "run the test suite"
    return textwrap.dedent(f"""\
        You are implementing a fix for a detected architectural gap in this repository.

        **Task:** {gap_title}
        **Subsystem:** {subsystem}
        **Scope:** {scope}

        **Files likely involved:** {files_text}

        **Implementation guidance:**
        {implementation_notes}

        **Requirements:**
        - Make concrete changes to the repository (not just analysis or suggestions).
        - Keep changes minimal and targeted to the described scope.
        - Do not modify files outside the stated scope.
        - Ensure all existing tests still pass after your changes.
        - Run {validation_text} to verify your implementation.

        Start by reading the files listed above, then implement the fix.
        """).strip()


def _module_segments(identifier: str) -> Tuple[str, ...]:
    """Normalize a module name or file path to its constituent segments.

    Handles both module names (``backend.core.foo``) and file paths
    (``backend/core/foo.py``).  Always returns a tuple of directory-style
    segments (no dots, no ``.py`` suffix).

    Identifiers containing both dots and slashes are treated as file paths
    (the slash takes precedence).
    """
    if "." in identifier and "/" not in identifier:
        # Module name → split on dots
        return tuple(identifier.split("."))
    # File path → use pathlib
    parts = pathlib.Path(identifier).parts
    # Strip .py suffix from the last segment
    if parts and parts[-1].endswith(".py"):
        parts = parts[:-1] + (parts[-1][:-3],)
    return parts


def _module_to_path(identifier: str, analysis: Dict[str, Any]) -> str:
    """Best-effort mapping of a module name to a repo-relative file path.

    Falls back to ``module.replace('.', '/') + '.py'`` when the analysis
    ``python_files`` data is unavailable or the module is not found.
    """
    py_files = analysis.get("python_files", [])
    if py_files:
        for info in py_files:
            if isinstance(info, dict) and info.get("module") == identifier:
                return info["path"]
    # Fallback: replace dots with slashes
    return identifier.replace(".", "/") + ".py"


def _agent_name(segments: Tuple[str, ...]) -> Optional[str]:
    """Extract the agent identifier from module segments.

    For segments like ``("backend", "agents", "foo", "utils")``, returns ``"foo"``
    — the segment immediately after ``"agents"``.  Returns ``None`` if the
    identifier has no ``"agents"`` segment or nothing follows it.
    """
    try:
        idx = list(segments).index("agents")
    except ValueError:
        return None
    if idx + 1 < len(segments):
        return segments[idx + 1]
    return None


def diagnose_gaps(config: Config, analysis: Dict[str, Any], model_meta: Dict[str, Any]) -> List[ArchGap]:
    """Detect concrete architectural gaps from the current repository analysis.

    Returns a prioritized list of ArchGap instances. At most one gap per
    subsystem/issue_key pair is returned (dedup at source).
    """
    gaps: List[ArchGap] = []
    seen: Set[str] = set()

    def add(gap: ArchGap) -> None:
        key = issue_fingerprint(gap.subsystem, gap.issue_key)
        if key not in seen:
            seen.add(key)
            gaps.append(gap)

    # 1. Parse errors ──────────────────────────────────────────────────────
    parse_errors = analysis.get("parse_error_files", [])
    if parse_errors:
        files = parse_errors[:10]
        add(ArchGap(
            subsystem="runtime",
            issue_key="parse-errors",
            title=f"[arch-gap] Fix Python parse errors in {len(parse_errors)} file(s)",
            summary=f"The repository contains {len(parse_errors)} Python file(s) with syntax errors that prevent import.",
            problem=(
                f"Files: {', '.join(files[:5])}{'…' if len(parse_errors) > 5 else ''}.\n"
                "These parse errors break static analysis, test collection, and may crash runtime imports."
            ),
            why_it_matters="Parse errors in any imported module cause cascading ImportError failures at startup and block CI.",
            scope=f"Fix syntax in up to {len(files)} files. No refactoring or logic changes.",
            suggested_files=files,
            implementation_notes=(
                "Run `python -m py_compile <file>` on each listed file to see the exact error. "
                "Correct the syntax and verify with `ast.parse`. Do not change logic — only fix syntax."
            ),
            acceptance_criteria=[
                "All listed files pass `python -m py_compile` without errors.",
                "No new parse errors are introduced.",
                "`python -m pytest` collects without ImportError.",
            ],
            validation_commands=[
                f"python -m py_compile {' '.join(files[:3])}",
                "python -m pytest --co -q 2>&1 | head -20",
            ],
            out_of_scope="Logic changes, refactoring, adding new features.",
            copilot_prompt=_build_copilot_prompt(
                f"Fix Python parse errors in {len(parse_errors)} file(s)",
                "runtime", f"Fix syntax errors in: {', '.join(files[:5])}",
                files, [f"python -m py_compile {files[0]}", "python -m pytest --co -q"],
                "Run py_compile on each file, fix the reported syntax error, verify with ast.parse.",
            ),
            priority="critical",
            confidence=1.0,
        ))

    # 2. Import cycles ─────────────────────────────────────────────────────
    cycles = analysis.get("cycles", [])
    if cycles:
        cycle_modules: List[str] = []
        for c in cycles[:5]:
            cycle_modules.extend(c)
        cycle_modules = list(dict.fromkeys(cycle_modules))[:10]
        # Map module names → file paths for suggested_files
        cycle_files = [_module_to_path(m, analysis) for m in cycle_modules]
        add(ArchGap(
            subsystem="runtime",
            issue_key="import-cycles",
            title=f"[arch-gap] Break {len(cycles)} circular import cycle(s)",
            summary=f"The codebase has {len(cycles)} circular import cycle(s) that degrade startup performance and complicate testing.",
            problem=(
                f"Example cycle: {' → '.join(cycles[0]) if cycles else 'see analysis'}.\n"
                "Circular imports force the interpreter to partially execute modules, causing subtle "
                "AttributeError and ImportError bugs."
            ),
            why_it_matters="Circular imports increase coupling, slow startup, and block modular testing.",
            scope=f"Break the top {min(len(cycles), 3)} import cycle(s) using TYPE_CHECKING guards or lazy imports.",
            suggested_files=cycle_files,
            implementation_notes=(
                "Use `from __future__ import annotations` + `if TYPE_CHECKING:` guards for type-only imports. "
                "For runtime dependencies, introduce a separate interface module or use lazy imports."
            ),
            acceptance_criteria=[
                "The targeted cycles no longer appear in `repo_architect.py` import graph.",
                "All affected files pass `python -m py_compile`.",
                "Existing tests continue to pass.",
            ],
            validation_commands=[
                "python repo_architect.py --mode analyze --allow-dirty",
                "python -m pytest -x -q",
            ],
            out_of_scope="Refactoring unrelated to the identified cycles.",
            copilot_prompt=_build_copilot_prompt(
                f"Break {len(cycles)} circular import cycle(s)",
                "runtime", "Apply TYPE_CHECKING guards or lazy imports to the identified cycles",
                cycle_files[:5],
                ["python repo_architect.py --mode analyze --allow-dirty", "python -m pytest -x -q"],
                "Use TYPE_CHECKING guards for type-only imports; introduce lazy imports for runtime deps.",
            ),
            priority="high",
            confidence=0.95,
        ))

    # 3. Entrypoint fragmentation ──────────────────────────────────────────
    ep_clusters = analysis.get("entrypoint_clusters", {})
    ep_paths = analysis.get("entrypoint_paths", [])
    backend_eps = ep_clusters.get("backend_servers", ep_paths)
    if len(backend_eps) >= _ENTRYPOINT_CONSOLIDATION_THRESHOLD:
        add(ArchGap(
            subsystem="runtime",
            issue_key="entrypoint-fragmentation",
            title=f"[arch-gap] Consolidate {len(backend_eps)} backend server entrypoints",
            summary=f"There are {len(backend_eps)} backend server entrypoints. The canonical entrypoint is unclear.",
            problem=(
                f"Entrypoints: {', '.join(backend_eps[:5])}.\n"
                "Multiple entrypoints create ambiguity about the authoritative startup path, complicate "
                "deployment configuration, and increase maintenance burden."
            ),
            why_it_matters="A fragmented entrypoint surface makes it hard to ensure consistent startup behaviour in CI and production.",
            scope="Add `# DEPRECATED: prefer <canonical>` comments to non-canonical entrypoints. Do not delete files.",
            suggested_files=list(backend_eps[:8]),
            implementation_notes=(
                "Identify the primary entrypoint (typically `backend/unified_server.py` or `main.py`). "
                "Add a module-level `# DEPRECATED: prefer <canonical_path>` comment to each redundant entrypoint. "
                "Update any README references."
            ),
            acceptance_criteria=[
                "Canonical entrypoint is documented in README or a comment at the top of each deprecated file.",
                "All deprecated files have a `# DEPRECATED:` comment.",
                "No files are deleted in this change.",
            ],
            validation_commands=[
                "python repo_architect.py --mode analyze --allow-dirty",
                "grep -r 'DEPRECATED' backend/ --include='*.py' | head -20",
            ],
            out_of_scope="Deleting files, changing runtime behaviour, refactoring.",
            copilot_prompt=_build_copilot_prompt(
                f"Consolidate {len(backend_eps)} backend server entrypoints",
                "runtime",
                "Add DEPRECATED comments to non-canonical entrypoints",
                list(backend_eps[:8]),
                ["python repo_architect.py --mode analyze --allow-dirty"],
                "Add `# DEPRECATED: prefer <canonical>` to each non-canonical entrypoint file.",
            ),
            priority="medium",
            confidence=0.85,
        ))

    # 4. Architecture score degradation ────────────────────────────────────
    score = analysis.get("architecture_score", 100)
    if score < 70:
        risk_factors = analysis.get("score_factors", {})
        risk_summary = "; ".join(f"{k}: {v}" for k, v in list(risk_factors.items())[:4]) if risk_factors else "see analysis"
        analysis_rel_path = str(config.analysis_path.relative_to(config.git_root))
        add(ArchGap(
            subsystem="reporting",
            issue_key="architecture-score-degradation",
            title=f"[arch-gap] Architecture health score degraded to {score}/100",
            summary=f"The repository architecture score is {score}/100 (threshold: 70). Immediate attention required.",
            problem=f"Score factors: {risk_summary}.",
            why_it_matters="A low architecture score indicates structural fragility that compounds over time.",
            scope="Address the top contributing risk factors. Do not attempt a full refactor in one PR.",
            suggested_files=[
                analysis_rel_path,
            ],
            implementation_notes=(
                f"Review `{analysis_rel_path}` for the current risk breakdown. "
                "Address the highest-weight factor first in an isolated PR."
            ),
            acceptance_criteria=[
                "Architecture score improves by at least 5 points after addressing the primary factor.",
                "No regressions in existing test suite.",
            ],
            validation_commands=[
                "python repo_architect.py --mode report --allow-dirty",
            ],
            out_of_scope="Addressing all risk factors in one change.",
            copilot_prompt=_build_copilot_prompt(
                f"Improve architecture health score (currently {score}/100)",
                "reporting",
                f"Address top risk factors: {risk_summary[:100]}",
                [analysis_rel_path],
                ["python repo_architect.py --mode report --allow-dirty"],
                f"Review {analysis_rel_path}, identify the primary contributing factor, and address it in a minimal targeted change.",
            ),
            priority="high" if score < 50 else "medium",
            confidence=1.0,
        ))

    # 5. Workflow / docs drift (model-assisted, if available) ──────────────
    if model_meta.get("used") and model_meta.get("summary"):
        model_summary = model_meta["summary"]
        # Emit a workflow gap only when the model summary mentions drift signals
        drift_signals = ("drift", "outdated", "inconsistent", "mismatch", "stale", "broken", "missing")
        if any(s in model_summary.lower() for s in drift_signals):
            add(ArchGap(
                subsystem="workflow",
                issue_key="workflow-drift",
                title="[arch-gap] Workflow / documentation drift detected",
                summary="The model analysis identified potential drift between documentation/workflows and current repository state.",
                problem=f"Model summary excerpt:\n\n> {model_summary[:500]}",
                why_it_matters="Stale workflows and documentation mislead contributors and cause CI failures.",
                scope="Update or align the identified workflow/documentation artefacts.",
                suggested_files=[
                    ".github/workflows/repo-architect.yml",
                    "docs/repo_architect/OPERATOR_GUIDE.md",
                    "README.md",
                ],
                implementation_notes=(
                    "Review the model summary above, identify specific drift items, and update the relevant files. "
                    "Do not make speculative changes — only address what is concretely identified."
                ),
                acceptance_criteria=[
                    "Identified drift items are resolved.",
                    "Documentation accurately reflects current behaviour.",
                ],
                validation_commands=[
                    "python repo_architect.py --mode report --allow-dirty",
                ],
                out_of_scope="Rewriting documentation wholesale; unrelated improvements.",
                copilot_prompt=_build_copilot_prompt(
                    "Resolve workflow/documentation drift",
                    "workflow",
                    "Align documentation and workflows with current repository state",
                    [".github/workflows/repo-architect.yml", "docs/repo_architect/OPERATOR_GUIDE.md"],
                    ["python repo_architect.py --mode report --allow-dirty"],
                    f"The model identified drift: {model_summary[:200]}. Locate the specific mismatch and fix it.",
                ),
                priority="medium",
                confidence=0.7,
            ))

    # 6. Dependency direction violations — Lane 5 (Contract repair) ────────
    # Detect when modules import across architectural layer boundaries
    import_graph = analysis.get("local_import_graph", {})
    if import_graph:
        # Heuristic: interface → core or knowledge → runtime imports signal contract misalignment
        boundary_violations: List[str] = []
        for src, targets in import_graph.items():
            if not isinstance(targets, list):
                continue
            src_parts = _module_segments(src)
            for tgt in targets:
                tgt_parts = _module_segments(tgt)
                # Detect cross-boundary imports per §6 Dependency Direction Contract
                # Charter §6 direction: runtime → core → knowledge → agents → interface
                # Violations: imports going backwards (e.g., interface→core, knowledge→runtime)
                # §6.1 hard prohibitions: interface→deep-internals, knowledge→runtime, agents reaching through interface to runtime
                if ("interface" in src_parts and "core" in tgt_parts) or \
                   ("interface" in src_parts and "runtime" in tgt_parts) or \
                   ("knowledge" in src_parts and "runtime" in tgt_parts) or \
                   ("agents" in src_parts and "runtime" in tgt_parts):
                    boundary_violations.append(f"{src} → {tgt}")
        if boundary_violations:
            violation_files = [_module_to_path(v.split(" → ")[0], analysis) for v in boundary_violations[:_MAX_VIOLATIONS_DISPLAY]]
            add(ArchGap(
                subsystem="core",
                issue_key="contract-repair",
                title=f"[arch-gap] Repair {len(boundary_violations)} cross-boundary import(s) (Lane 5)",
                summary=f"Detected {len(boundary_violations)} import(s) that violate the charter dependency direction contract.",
                problem=(
                    f"Violations: {'; '.join(boundary_violations[:_MAX_VIOLATIONS_DISPLAY])}.\n"
                    "These imports cross architectural layer boundaries defined in §6 of the "
                    "GODELOS_REPO_IMPLEMENTATION_CHARTER (dependency direction: runtime → core → knowledge → agents → interface)."
                ),
                why_it_matters="Cross-boundary imports increase coupling, hinder modular testing, and violate the charter dependency contract.",
                scope="Repair the identified import violations using interface extraction or dependency inversion.",
                suggested_files=violation_files,
                implementation_notes=(
                    "Introduce interface modules at layer boundaries. Use dependency inversion to reverse "
                    "inappropriate imports. See §6 GODELOS_REPO_IMPLEMENTATION_CHARTER for the target direction."
                ),
                acceptance_criteria=[
                    "The identified cross-boundary imports are removed or inverted.",
                    "No new cross-boundary imports are introduced.",
                    "Existing tests pass.",
                ],
                validation_commands=["python repo_architect.py --mode analyze --allow-dirty"],
                out_of_scope="Refactoring unrelated to the identified boundary violations.",
                copilot_prompt=_build_copilot_prompt(
                    f"Repair {len(boundary_violations)} cross-boundary import(s)",
                    "core", "Apply dependency inversion to fix cross-layer imports",
                    violation_files,
                    ["python repo_architect.py --mode analyze --allow-dirty", "python -m pytest -x -q"],
                    "Introduce interface modules or use dependency inversion. Target direction: runtime → core → knowledge → agents → interface.",
                ),
                priority="medium",
                confidence=0.75,
            ))

    # 7. Agent boundary violations — Lane 7 (Agent boundary enforcement) ───
    # Detect when agent modules directly access other agents' internals
    if import_graph:
        agent_violations: List[str] = []
        for src, targets in import_graph.items():
            if not isinstance(targets, list):
                continue
            src_parts = _module_segments(src)
            src_agent = _agent_name(src_parts)
            if src_agent is None:
                continue
            for tgt in targets:
                tgt_parts = _module_segments(tgt)
                tgt_agent = _agent_name(tgt_parts)
                # Only flag when both are under "agents" but belong to
                # *different* named agents (e.g. foo → bar, not foo → foo.utils)
                if tgt_agent is not None and src_agent != tgt_agent:
                    agent_violations.append(f"{src} → {tgt}")
        if agent_violations:
            agent_files = [_module_to_path(v.split(" → ")[0], analysis) for v in agent_violations[:_MAX_VIOLATIONS_DISPLAY]]
            add(ArchGap(
                subsystem="agents",
                issue_key="agent-boundary",
                title=f"[arch-gap] Enforce agent boundaries for {len(agent_violations)} cross-agent import(s) (Lane 7)",
                summary=f"Detected {len(agent_violations)} import(s) where agent modules reach into other agents' internals.",
                problem=(
                    f"Cross-agent imports: {'; '.join(agent_violations[:_MAX_VIOLATIONS_DISPLAY])}.\n"
                    "Agents should communicate through explicit channels (§4.4 GODELOS_REPO_IMPLEMENTATION_CHARTER), "
                    "not by reaching into each other's private internals."
                ),
                why_it_matters="Cross-agent coupling prevents independent testing, deployment, and evolution of agent modules.",
                scope="Replace direct cross-agent imports with message-based or interface-mediated communication.",
                suggested_files=agent_files,
                implementation_notes=(
                    "Identify the shared interface or message contract. Replace direct imports with "
                    "message dispatch or shared interface modules."
                ),
                acceptance_criteria=[
                    "No agent module directly imports another agent's internal modules.",
                    "Cross-agent communication uses explicit interfaces or messages.",
                ],
                validation_commands=["python repo_architect.py --mode analyze --allow-dirty"],
                out_of_scope="Refactoring agent internals; only addressing cross-agent coupling.",
                copilot_prompt=_build_copilot_prompt(
                    f"Enforce agent boundaries for {len(agent_violations)} cross-agent import(s)",
                    "agents", "Replace direct cross-agent imports with interfaces or messages",
                    agent_files,
                    ["python repo_architect.py --mode analyze --allow-dirty", "python -m pytest -x -q"],
                    "Replace direct cross-agent imports with message-based or shared-interface patterns per §4.4.",
                ),
                priority="medium",
                confidence=0.7,
            ))
    if config.issue_subsystem:
        gaps = [g for g in gaps if g.subsystem == config.issue_subsystem]

    # Sort by priority
    _priority_rank = {p: i for i, p in enumerate(ISSUE_PRIORITY_LEVELS)}
    gaps.sort(key=lambda g: _priority_rank.get(g.priority, 99))
    return gaps


def run_issue_cycle(config: Config) -> Dict[str, Any]:
    """Execute one issue-synthesis cycle.

    Steps:
      1. Load work state (memory lane) to avoid re-raising in-progress issues.
      2. Build analysis and model enrichment (same as analyze/report modes).
      3. Diagnose architectural gaps.
      4. For each gap (up to max_issues): synthesize a GitHub Issue or dry-run artifact.
      5. Record new issues into work state so future passes see them.
      6. Emit a structured JSON result and write a step summary.
    """
    ensure_agent_dir(config.agent_dir)
    state = load_state(config)
    # Load durable work state (memory lane) — used to suppress in-progress objectives
    work_state = load_work_state(config)
    active_fps = _active_fingerprints_in_work_state(work_state)

    analysis = build_analysis(config.git_root)
    charter_context = load_charter_context(config.git_root)
    analysis["charter_context"] = charter_context
    model_meta = enrich_with_github_models(config, analysis)
    if model_meta.get("used") or model_meta.get("enabled"):
        charter_context["applied"] = bool(charter_context.get("loaded_files"))
    analysis["model_meta"] = model_meta
    persist_analysis(config, analysis)

    run_id = (
        os.environ.get("REPO_ARCHITECT_BRANCH_SUFFIX")
        or os.environ.get("GITHUB_RUN_ID")
        or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    )

    gaps = diagnose_gaps(config, analysis, model_meta)
    # Filter out gaps whose fingerprint is already actively in-progress/delegated
    if active_fps:
        gaps = [
            g for g in gaps
            if issue_fingerprint(g.subsystem, g.issue_key) not in active_fps
        ]
        # If all gaps are filtered out, return an empty selection — the planner
        # must not re-raise issues for in-progress work.
    selected_gaps = gaps[: config.max_issues]

    issue_actions: List[Dict[str, Any]] = []
    for gap in selected_gaps:
        action = synthesize_issue(config, gap, run_id, config.dry_run)
        issue_actions.append(dataclasses.asdict(action))

    artifact_files = [
        str(config.analysis_path.relative_to(config.git_root)),
        str(config.graph_path.relative_to(config.git_root)),
    ]
    for action in issue_actions:
        if action.get("dry_run_path"):
            artifact_files.append(action["dry_run_path"])

    charter_meta = {
        "loaded_files": charter_context.get("loaded_files", []),
        "content_hash": charter_context.get("content_hash"),
        "applied": charter_context.get("applied", False),
    }

    # Build summary log lines
    summary_lines: List[str] = []
    for a in issue_actions:
        act = a["action"]
        title = a["gap_title"]
        if act == "created":
            summary_lines.append(f"created issue #{a['issue_number']} — {title}")
        elif act == "updated":
            summary_lines.append(f"updated existing issue #{a['issue_number']} — {title}")
        elif act == "dry_run":
            summary_lines.append(f"dry-run issue body written to {a.get('dry_run_path')} — {title}")
        else:
            summary_lines.append(f"error synthesizing issue — {title}: {a.get('error')}")

    result: Dict[str, Any] = {
        "status": "issue_cycle_complete",
        "mode": ISSUE_MODE,
        "dry_run": config.dry_run,
        "gaps_detected": len(gaps),
        "gaps_selected": len(selected_gaps),
        "issue_actions": issue_actions,
        "summary": summary_lines,
        "architecture_score": analysis["architecture_score"],
        "requested_model": model_meta.get("requested_model"),
        "actual_model": model_meta.get("actual_model"),
        "primary_model": model_meta.get("primary_model"),
        "fallback_model": model_meta.get("fallback_model"),
        "model_used": model_meta.get("model_used"),
        "fallback_used": model_meta.get("fallback_used", False),
        "fallback_reason": model_meta.get("fallback_reason"),
        "fallback_occurred": model_meta.get("fallback_occurred", False),
        "artifact_files": artifact_files,
        "repo_root": str(config.git_root),
        "analysis_path": str(config.analysis_path),
        "charter": charter_meta,
        "github_models": model_meta,
        # Fields kept for output schema compatibility
        "lane": "none",
        "lanes_active": [],
        "branch": None,
        "changed_files": [],
        "validation": None,
        "pull_request_url": None,
        "no_safe_code_mutation_reason": None,
        "roadmap": analysis.get("roadmap", []),
        "graph_path": str(config.graph_path),
        "roadmap_path": str(config.roadmap_path),
        "metadata": {
            "architecture_score": analysis["architecture_score"],
            "model_meta": model_meta,
            "report_path": str(config.report_path),
        },
    }

    persist_manifest(config, artifact_files)
    write_step_summary(config, result)

    # Record new issues into durable work state (memory lane)
    ingest_issue_actions_to_work_state(config, work_state, issue_actions, run_id)
    save_work_state(config, work_state)

    state["runs"] = int(state.get("runs", 0)) + 1
    state["last_run_epoch"] = int(time.time())
    state["last_outcome"] = result["status"]
    state.setdefault("history", []).append({
        "ts": state["last_run_epoch"],
        "status": result["status"],
        "architecture_score": result["architecture_score"],
        "mode": config.mode,
        "gaps_detected": len(gaps),
        "issue_actions": [{"action": a["action"], "issue_number": a.get("issue_number")} for a in issue_actions],
    })
    state["history"] = state["history"][-100:]
    save_state(config, state)
    return result


def set_branch_protection(config: Config) -> Dict[str, Any]:
    if not config.github_admin_token or not config.github_repo:
        raise RepoArchitectError("Need GITHUB_ADMIN_TOKEN and GITHUB_REPO for branch protection.")
    payload = {
        "required_status_checks": None,
        "enforce_admins": False,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": False,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 1,
        },
        "restrictions": None,
        "required_conversation_resolution": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "lock_branch": False,
    }
    branch = config.github_base_branch or "main"
    return github_request(config.github_admin_token, f"/repos/{config.github_repo}/branches/{branch}/protection", method="PUT", payload=payload)


# -----------------------------
# Source analysis
# -----------------------------

def iter_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORE_DIRS]
        for name in filenames:
            yield pathlib.Path(dirpath) / name


def module_name(root: pathlib.Path, path: pathlib.Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def is_local_import(candidate: str, all_modules: Dict[str, str]) -> bool:
    if candidate in all_modules:
        return True
    prefix = candidate + "."
    return any(m.startswith(prefix) for m in all_modules)


def extract_debug_print_lines(source: str) -> List[int]:
    out: List[int] = []
    for idx, line in enumerate(source.splitlines(), 1):
        if DEBUG_MARKER_RE.search(line) and PRINT_RE.search(line):
            out.append(idx)
    return out


def parse_python_files(root: pathlib.Path) -> Tuple[List[PyFileInfo], List[str]]:
    py_paths = [p for p in iter_files(root) if p.suffix == ".py"]
    module_map = {module_name(root, p): str(p.relative_to(root)) for p in py_paths}
    infos: List[PyFileInfo] = []
    parse_error_paths: List[str] = []
    for path in py_paths:
        rel = str(path.relative_to(root))
        source = path.read_text(encoding="utf-8", errors="replace")
        imports: List[str] = []
        local_imports: List[str] = []
        entrypoint = any(h in source for h in ENTRYPOINT_HINTS)
        debug_lines = extract_debug_print_lines(source)
        parse_error = None
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if node.level and mod:
                        imports.append(mod)
                    elif mod:
                        imports.append(mod)
        except SyntaxError as exc:
            parse_error = f"{exc.msg} (line {exc.lineno})"
            parse_error_paths.append(rel)
        imports = sorted(set(imports))
        local_imports = sorted(i for i in imports if is_local_import(i, module_map))
        infos.append(PyFileInfo(rel, module_name(root, path), imports, local_imports, entrypoint, debug_lines, parse_error))
    return infos, parse_error_paths


def build_import_graph(infos: List[PyFileInfo]) -> Dict[str, List[str]]:
    return {info.module: info.local_imports for info in infos if info.module}


def find_cycles(graph: Dict[str, List[str]]) -> List[List[str]]:
    seen: set[str] = set()
    stack: List[str] = []
    on_stack: set[str] = set()
    cycles: set[Tuple[str, ...]] = set()

    def canonical_cycle(nodes: List[str]) -> Tuple[str, ...]:
        if not nodes:
            return tuple()
        rots = [tuple(nodes[i:] + nodes[:i]) for i in range(len(nodes))]
        return min(rots)

    def dfs(node: str) -> None:
        seen.add(node)
        stack.append(node)
        on_stack.add(node)
        for nxt in graph.get(node, []):
            if nxt not in graph:
                continue
            if nxt not in seen:
                dfs(nxt)
            elif nxt in on_stack:
                idx = stack.index(nxt)
                cycle = stack[idx:]
                cycles.add(canonical_cycle(cycle))
        stack.pop()
        on_stack.remove(node)

    for n in sorted(graph):
        if n not in seen:
            dfs(n)
    return [list(c) + [c[0]] for c in sorted(cycles)]


def cluster_entrypoints(infos: List[PyFileInfo]) -> Dict[str, List[str]]:
    clusters = {
        "backend_servers": [],
        "tests": [],
        "examples": [],
        "scripts": [],
        "other": [],
    }
    for info in infos:
        if not info.entrypoint:
            continue
        path = info.path
        if path.startswith("backend/"):
            clusters["backend_servers"].append(path)
        elif path.startswith("tests/"):
            clusters["tests"].append(path)
        elif path.startswith("examples/"):
            clusters["examples"].append(path)
        elif path.startswith("scripts/"):
            clusters["scripts"].append(path)
        else:
            clusters["other"].append(path)
    return {k: sorted(v) for k, v in clusters.items() if v}


def architecture_score(infos: List[PyFileInfo], cycles: List[List[str]], parse_errors: List[str]) -> Tuple[int, Dict[str, Any]]:
    entrypoints = sum(1 for i in infos if i.entrypoint)
    local_edges = sum(len(i.local_imports) for i in infos)
    score = 100
    score -= min(30, len(cycles) * 8)
    score -= min(20, len(parse_errors) * 5)
    score -= min(20, max(0, entrypoints - 20) // 10)
    score -= min(10, max(0, local_edges - len(infos)) // 30)
    return max(1, score), {
        "python_files": len(infos),
        "local_import_cycles": len(cycles),
        "parse_errors": len(parse_errors),
        "entrypoints": entrypoints,
        "local_import_edges": local_edges,
    }


def top_risks(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    risks: List[Dict[str, Any]] = []
    if analysis["cycles"]:
        risks.append({
            "name": "review_circular_dependencies",
            "priority": 80,
            "actionable": False,
            "summary": f"Review {len(analysis['cycles'])} local import cycle(s).",
            "targets": analysis["cycles"],
        })
    if analysis["parse_error_files"]:
        risks.append({
            "name": "review_parse_errors",
            "priority": 70,
            "actionable": False,
            "summary": f"Review syntax/parse issues in {len(analysis['parse_error_files'])} file(s).",
            "targets": analysis["parse_error_files"],
        })
    entrypoints = analysis["entrypoint_paths"]
    if len(entrypoints) > 30:
        risks.append({
            "name": "review_multiple_entrypoints",
            "priority": 60,
            "actionable": False,
            "summary": f"Review {len(entrypoints)} Python entrypoints for runtime duplication.",
            "targets": entrypoints[:200],
        })
    risks.append({
        "name": "publish_runtime_inventory_report",
        "priority": 50,
        "actionable": True,
        "summary": "Generate or refresh repository architecture inventory documentation.",
        "targets": [str(DEFAULT_REPORT_PATH)],
    })
    return risks


def build_analysis(root: pathlib.Path) -> Dict[str, Any]:
    infos, parse_errors = parse_python_files(root)
    graph = build_import_graph(infos)
    cycles = find_cycles(graph)
    entrypoint_paths = sorted(i.path for i in infos if i.entrypoint)
    score, factors = architecture_score(infos, cycles, parse_errors)
    return {
        "python_files": [dataclasses.asdict(i) for i in infos],
        "local_import_graph": graph,
        "cycles": cycles,
        "parse_error_files": parse_errors,
        "entrypoint_paths": entrypoint_paths,
        "entrypoint_clusters": cluster_entrypoints(infos),
        "debug_print_candidates": sorted(i.path for i in infos if i.debug_print_lines),
        "architecture_score": score,
        "score_factors": factors,
        "roadmap": top_risks({
            "cycles": cycles,
            "parse_error_files": parse_errors,
            "entrypoint_paths": entrypoint_paths,
        }),
    }


# -----------------------------
# Charter context
# -----------------------------

def load_charter_context(git_root: pathlib.Path) -> Dict[str, Any]:
    """Load architectural charter files and companion policy files if present.

    Returns a dict with:
      - loaded_files: list of relative paths that were successfully read
      - content_hash: hex digest of combined content (None if no files loaded)
      - applied: False initially; callers set True when charter was injected
      - content: truncated combined charter text for model injection
      - companion_files: list of §15 companion file paths that exist
    """
    loaded_files: List[str] = []
    contents: List[str] = []
    for rel in CHARTER_PATHS:
        path = git_root / rel
        if path.exists():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                loaded_files.append(rel)
                contents.append(f"### {rel}\n\n{text[:_MAX_CHARTER_CHARS_PER_FILE]}")
            except OSError:
                pass
    # §15 companion files — record existence for diagnostics
    companion_files: List[str] = []
    for rel in CHARTER_COMPANION_FILES:
        if (git_root / rel).exists():
            companion_files.append(rel)
    combined = "\n\n".join(contents)
    content_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16] if combined else None
    return {
        "loaded_files": loaded_files,
        "content_hash": content_hash,
        "applied": False,
        "content": combined,
        "companion_files": companion_files,
    }


# -----------------------------
# Models enrichment
# -----------------------------

def enrich_with_github_models(config: Config, analysis: Dict[str, Any]) -> Dict[str, Any]:
    preferred = config.github_model or config.preferred_model
    fallback = config.github_fallback_model or config.fallback_model
    meta: Dict[str, Any] = {
        "enabled": False,
        "used": False,
        "requested_model": preferred,
        "actual_model": None,
        "model": preferred,  # kept for backward compatibility
        "primary_model": preferred,
        "fallback_model": fallback,
        "model_used": None,
        "fallback_used": False,
        "summary": None,
        "fallback_reason": None,
        "fallback_occurred": False,
    }
    if not config.github_token or not preferred:
        return meta
    meta["enabled"] = True
    charter_context: Dict[str, Any] = analysis.get("charter_context") or {}
    charter_text = charter_context.get("content", "")
    charter_preamble = (
        f"\n\nArchitectural charter guidance (authoritative for this repository):\n{charter_text}\n"
        if charter_text else ""
    )
    prompt = textwrap.dedent(f"""
    You are summarizing repository architecture risk.
    Architecture score: {analysis['architecture_score']}
    Local import cycles: {len(analysis['cycles'])}
    Parse error files: {len(analysis['parse_error_files'])}
    Entrypoints: {len(analysis['entrypoint_paths'])}
    Top roadmap items: {json.dumps(analysis['roadmap'][:5])}

    Return 5 bullet points, compact and concrete, no preamble.
    """).strip()
    system_content = "You produce concise engineering prioritization notes." + charter_preamble
    resp, requested, fallback_reason, fallback_occurred = call_models_with_fallback_or_none(
        config.github_token, preferred, fallback,
        [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ],
    )
    meta["fallback_reason"] = fallback_reason
    meta["fallback_occurred"] = fallback_occurred
    meta["fallback_used"] = fallback_occurred
    if resp is None:
        return meta
    try:
        meta["summary"] = parse_model_text(resp)
        meta["actual_model"] = resp.get("model", fallback if fallback_occurred else preferred)
        meta["model_used"] = meta["actual_model"]
        meta["used"] = True
    except RepoArchitectError as exc:
        meta["fallback_reason"] = (meta.get("fallback_reason") or "") + f"; parse failed: {exc}"
    return meta


# -----------------------------
# Report generation
# -----------------------------

def render_runtime_inventory(analysis: Dict[str, Any], model_meta: Dict[str, Any]) -> str:
    lines = [
        "# Repository Runtime Inventory",
        "",
        f"Architecture score: **{analysis['architecture_score']}**",
        "",
        "## Top priorities",
    ]
    for item in analysis["roadmap"]:
        lines.append(f"- **{item['name']}**: {item['summary']}")
    if model_meta.get("used") and model_meta.get("summary"):
        lines += ["", "## Model-assisted summary", "", model_meta["summary"], ""]
    lines += ["", "## Entrypoint overview", ""]
    clusters = analysis["entrypoint_clusters"]
    for cluster, items in clusters.items():
        lines.append(f"### {cluster}")
        for path in items[:80]:
            lines.append(f"- `{path}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_cycles_report(analysis: Dict[str, Any]) -> str:
    lines = ["# Circular Dependencies", ""]
    if not analysis["cycles"]:
        lines += ["No local import cycles detected.", ""]
    else:
        for idx, cyc in enumerate(analysis["cycles"], 1):
            lines.append(f"## Cycle {idx}")
            lines.append("")
            for node in cyc:
                lines.append(f"- `{node}`")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_parse_errors_report(analysis: Dict[str, Any], py_infos: List[Dict[str, Any]]) -> str:
    by_path = {i['path']: i for i in py_infos}
    lines = ["# Parse Errors", ""]
    if not analysis["parse_error_files"]:
        lines += ["No parse errors detected.", ""]
    else:
        for path in analysis["parse_error_files"]:
            detail = by_path.get(path, {})
            lines.append(f"- `{path}`: {detail.get('parse_error', 'unknown parse error')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_entrypoint_clusters(analysis: Dict[str, Any]) -> str:
    lines = ["# Entrypoint Clusters", ""]
    for cluster, items in analysis["entrypoint_clusters"].items():
        lines.append(f"## {cluster} ({len(items)})")
        lines.append("")
        for path in items:
            lines.append(f"- `{path}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_top_risks(analysis: Dict[str, Any], model_meta: Dict[str, Any]) -> str:
    lines = ["# Top Risks", ""]
    for item in analysis["roadmap"]:
        lines.append(f"## {item['name']}")
        lines.append("")
        lines.append(item['summary'])
        lines.append("")
        if item.get('targets'):
            targets = item['targets']
            if isinstance(targets, list):
                for t in targets[:40]:
                    lines.append(f"- `{t}`" if isinstance(t, str) else f"- `{ ' -> '.join(t) }`")
            lines.append("")
    if model_meta.get("used") and model_meta.get("summary"):
        lines += ["## Model-assisted recommendations", "", model_meta["summary"], ""]
    return "\n".join(lines).rstrip() + "\n"


def build_report_suite(analysis: Dict[str, Any], model_meta: Dict[str, Any]) -> Dict[str, str]:
    py_infos = analysis["python_files"]
    return {
        str(REPORT_SUITE["runtime_inventory"]): render_runtime_inventory(analysis, model_meta),
        str(REPORT_SUITE["circular_dependencies"]): render_cycles_report(analysis),
        str(REPORT_SUITE["parse_errors"]): render_parse_errors_report(analysis, py_infos),
        str(REPORT_SUITE["entrypoint_clusters"]): render_entrypoint_clusters(analysis),
        str(REPORT_SUITE["top_risks"]): render_top_risks(analysis, model_meta),
    }


def write_step_summary(config: Config, result: Dict[str, Any]) -> None:
    if not config.step_summary_path:
        return
    mode = result.get("mode", config.mode)
    summary = [
        f"# {APP_NAME} run summary",
        "",
        f"- mode: `{mode}`",
        f"- status: `{result.get('status')}`",
        f"- architecture score: **{result.get('architecture_score')}**",
    ]

    if mode == ISSUE_MODE:
        summary.append(f"- gaps detected: `{result.get('gaps_detected', 0)}`")
        summary.append(f"- issues processed: `{result.get('gaps_selected', 0)}`")
        if result.get("dry_run"):
            summary.append("- ⚠️ **dry-run mode** — no issues submitted to GitHub")
        for action_d in result.get("issue_actions", []):
            act = action_d.get("action", "?")
            title = action_d.get("gap_title", "unknown")
            num = action_d.get("issue_number")
            url = action_d.get("issue_url")
            dry_path = action_d.get("dry_run_path")
            if act == "created" and url:
                summary.append(f"- ✅ created [#{num}]({url}) — {title}")
            elif act == "updated" and url:
                summary.append(f"- 🔄 updated [#{num}]({url}) — {title}")
            elif act == "dry_run":
                summary.append(f"- 📄 dry-run: `{dry_path}` — {title}")
            elif act == "error":
                summary.append(f"- ❌ error: {action_d.get('error')} — {title}")
    else:
        summary.append(f"- lane: `{result.get('lane', 'none')}`")
        summary.append(f"- changed files: `{len(result.get('changed_files', []))}`")
        if result.get("pull_request_url"):
            summary.append(f"- pull request: {result['pull_request_url']}")
        if result.get("branch"):
            summary.append(f"- branch: `{result['branch']}`")
        if result.get("no_safe_code_mutation_reason"):
            summary.append(f"- no safe mutation: {result['no_safe_code_mutation_reason']}")

    if result.get("requested_model"):
        summary.append(f"- model requested: `{result['requested_model']}`")
    if result.get("actual_model"):
        summary.append(f"- model used: `{result['actual_model']}`")
    if result.get("fallback_occurred"):
        summary.append(f"- ⚠️ fallback occurred: {result.get('fallback_reason', '')}")
    if result.get("github_models", {}).get("used"):
        summary += ["", "## Model summary", "", result["github_models"]["summary"]]
    config.step_summary_path.parent.mkdir(parents=True, exist_ok=True)
    config.step_summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")


# -----------------------------
# Planning / mutation lanes
# -----------------------------

def ensure_agent_dir(path: pathlib.Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_state(config: Config) -> Dict[str, Any]:
    return read_json(config.state_path, {"version": VERSION, "runs": 0, "history": [], "last_report_hash": None, "last_outcome": None})


def save_state(config: Config, state: Dict[str, Any]) -> None:
    atomic_write_json(config.state_path, state)


def _work_state_path(config: Config) -> pathlib.Path:
    """Return the resolved path to the durable work state JSON file."""
    if config.work_state_path is not None:
        return config.work_state_path
    return config.agent_dir / WORK_STATE_FILE


def load_work_state(config: Config) -> Dict[str, Any]:
    """Load the durable work-state artifact (memory lane).

    Returns a dict with schema::

        {
          "version": str,
          "updated_at": str | null,
          "items": [WorkItem-dict, ...]
        }
    """
    return read_json(
        _work_state_path(config),
        {"version": VERSION, "updated_at": None, "items": [], "delegation_events": []},
    )


def save_work_state(config: Config, work_state: Dict[str, Any]) -> None:
    """Persist work state to disk atomically."""
    work_state["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    atomic_write_json(_work_state_path(config), work_state)


def _normalize_work_item_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a persisted work-item dict so it matches the current WorkItem schema.

    - Drops keys not present in the current WorkItem fields.
    - Supplies sensible defaults for any newly-added required fields that are
      missing in older-schema records.

    This ensures ``WorkItem(**_normalize_work_item_dict(d))`` never raises
    ``TypeError`` even when ``.agent/work_state.json`` was written by an older
    version of repo_architect.
    """
    valid_fields: Dict[str, dataclasses.Field] = {  # type: ignore[type-arg]
        f.name: f for f in dataclasses.fields(WorkItem)
    }
    # Defaults for required fields (no dataclass default) when missing from older schema
    _required_defaults: Dict[str, Any] = {
        "fingerprint": "",
        "objective": "",
        "lane": "unknown",
        "issue_number": None,
        "issue_state": "open",
        "delegation_state": "ready-for-delegation",
        "assignee": None,
        "pr_number": None,
        "pr_url": None,
        "pr_state": None,
        "merged": False,
        "closed_unmerged": False,
        "blocked": False,
        "superseded": False,
        "created_at": "",
        "updated_at": "",
        "run_id": "",
        "gap_title": "",
        "gap_subsystem": "runtime",
    }
    result: Dict[str, Any] = {}
    for name, field in valid_fields.items():
        if name in raw:
            result[name] = raw[name]
        elif field.default is not dataclasses.MISSING:
            result[name] = field.default
        elif field.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            result[name] = field.default_factory()  # type: ignore[misc]
        elif name in _required_defaults:
            result[name] = _required_defaults[name]
        else:
            result[name] = None
    return result


def upsert_work_item(work_state: Dict[str, Any], item: WorkItem) -> None:
    """Insert or update a WorkItem in the work state, keyed by fingerprint."""
    items: List[Dict[str, Any]] = work_state.setdefault("items", [])
    item_dict = dataclasses.asdict(item)
    for i, existing in enumerate(items):
        if existing.get("fingerprint") == item.fingerprint:
            items[i] = item_dict
            return
    items.append(item_dict)


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def append_delegation_event(work_state: Dict[str, Any], event: Dict[str, Any]) -> None:
    """Append one delegation event to work state for auditability."""
    events: List[Dict[str, Any]] = work_state.setdefault("delegation_events", [])
    events.append(event)
    # keep bounded history
    if len(events) > 500:
        work_state["delegation_events"] = events[-500:]


def persist_analysis(config: Config, analysis: Dict[str, Any]) -> None:
    atomic_write_json(config.analysis_path, analysis)
    atomic_write_json(config.graph_path, analysis.get("local_import_graph", {}))
    atomic_write_json(config.roadmap_path, {"roadmap": analysis.get("roadmap", [])})


def baseline_dirty_guard(config: Config) -> None:
    if config.allow_dirty:
        return
    if git_is_dirty(config.git_root):
        raise RepoArchitectError("Repository has uncommitted changes. Re-run with --allow-dirty if you really want mutation.")


# ---------------------------------------------------------------------------
# Execution lane: issue selection, Copilot delegation, PR reconciliation
# ---------------------------------------------------------------------------

def _list_github_issues_by_labels(
    config: Config, labels: Sequence[str], state: str = "open"
) -> List[Dict[str, Any]]:
    """List GitHub issues that carry ALL of the given labels.

    The GitHub ``/issues`` endpoint returns both issues and pull requests.
    Pull requests are filtered out so callers only see real issues.
    """
    if not config.github_token or not config.github_repo:
        return []
    try:
        params = urllib.parse.urlencode({
            "labels": ",".join(labels),
            "state": state,
            "per_page": "50",
        })
        result = github_request(config.github_token, f"/repos/{config.github_repo}/issues?{params}")
        if not isinstance(result, list):
            return []
        # GitHub /issues endpoint returns PRs too; filter them out
        return [item for item in result if "pull_request" not in item]
    except RepoArchitectError:
        return []


def _extract_fingerprint_from_body(body: str) -> Optional[str]:
    """Extract the 12-hex arch-gap fingerprint marker from an issue body."""
    m = re.search(r"arch-gap-fingerprint:\s*([0-9a-f]{12})", body)
    return m.group(1) if m else None


def _extract_lane_from_body(body: str) -> Optional[str]:
    """Attempt to extract the charter lane name from an issue body."""
    m = re.search(r"(?i)Lane[:\s]+([A-Za-z][A-Za-z0-9_-]*)", body)
    return m.group(1).lower() if m else None


def select_ready_issue(
    config: Config, work_state: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Select one ready issue for delegation to Copilot.

    Selection rules (all must pass):
    - Issue has labels: arch-gap, copilot-task, needs-implementation
    - Issue does NOT have: blocked, superseded, in-progress, pr-open, merged
    - Not already tracked as delegated/in-progress in work state
    - Fingerprint not already delegated
    - At most one issue per lane at a time
    - Respects MAX_CONCURRENT_DELEGATED
    - Prefers highest priority first (critical > high > medium > low)
    - Respects active_objective and lane_filter preferences if set

    Returns the GitHub issue dict for the selected issue, or None.
    """
    if not config.github_token or not config.github_repo:
        return None

    items: List[Dict[str, Any]] = work_state.get("items", [])

    # Count currently in-flight items (delegation requested/confirmed, not yet done)
    in_flight = [
        it for it in items
        if it.get("delegation_state") in ("delegation-requested", "delegation-confirmed")
        and not it.get("merged")
        and not it.get("closed_unmerged")
    ]
    if len(in_flight) >= config.max_concurrent_delegated:
        return None

    # Build blocked sets from work state
    blocked_fingerprints: Set[str] = set()
    blocked_issue_numbers: Set[int] = set()
    blocked_lanes: Set[str] = set()
    for it in in_flight:
        if it.get("fingerprint"):
            blocked_fingerprints.add(it["fingerprint"])
        if it.get("issue_number"):
            blocked_issue_numbers.add(int(it["issue_number"]))
        if it.get("lane"):
            blocked_lanes.add(it["lane"])

    # Also block superseded/blocked items by fingerprint
    for it in items:
        if it.get("blocked") or it.get("superseded"):
            if it.get("fingerprint"):
                blocked_fingerprints.add(it["fingerprint"])
            if it.get("issue_number"):
                blocked_issue_numbers.add(int(it["issue_number"]))

    # Fetch eligible issues from GitHub
    candidate_issues = _list_github_issues_by_labels(
        config, list(EXECUTION_ELIGIBLE_LABELS), state="open"
    )

    filtered: List[Tuple[Dict[str, Any], Optional[str], Optional[str]]] = []
    blocking_lifecycle = {
        "ready-for-validation",
        "blocked-by-dependency", "superseded-by-issue", "superseded-by-pr",
        "delegation-requested", "in-progress", "pr-open", "pr-draft",
        "merged", "closed-unmerged", "failed-delegation",
    } | set(LEGACY_LIFECYCLE_LABELS)

    for issue in candidate_issues:
        issue_labels: Set[str] = {
            lbl["name"]
            for lbl in issue.get("labels", [])
            if isinstance(lbl, dict)
        }
        # Skip lifecycle-blocked issues
        if issue_labels & blocking_lifecycle:
            continue

        issue_num = issue.get("number")
        if issue_num and int(issue_num) in blocked_issue_numbers:
            continue

        body = issue.get("body") or ""
        fp = _extract_fingerprint_from_body(body)
        if fp and fp in blocked_fingerprints:
            continue

        lane = _extract_lane_from_body(body)

        # One issue per lane at a time
        if lane and lane in blocked_lanes:
            continue

        # Lane filter preference (soft — only skip if we have other options)
        if config.lane_filter and lane and lane != config.lane_filter:
            continue

        filtered.append((issue, fp, lane))

    if not filtered:
        return None

    # Sort by priority
    _prank = {p: i for i, p in enumerate(ISSUE_PRIORITY_LEVELS)}

    def _priority(entry: Tuple[Dict[str, Any], Optional[str], Optional[str]]) -> int:
        issue, _, _ = entry
        lbls = {lbl["name"] for lbl in issue.get("labels", []) if isinstance(lbl, dict)}
        for lbl in lbls:
            if lbl.startswith("priority:"):
                return _prank.get(lbl.split(":", 1)[1], 99)
        return 99

    filtered.sort(key=_priority)
    best_issue, _, _ = filtered[0]
    return best_issue


def delegate_to_copilot(
    config: Config,
    issue: Dict[str, Any],
    work_state: Dict[str, Any],
    run_id: str,
) -> Dict[str, Any]:
    """Delegate an issue to GitHub Copilot coding agent.

    Dry-run mode (config.enable_live_delegation is False):
        - Reports what would happen; no GitHub API side effects.

    Live mode (config.enable_live_delegation is True):
        - Adds 'in-progress' label, removes 'ready-for-delegation'.
        - Posts a pre-assignment audit comment with machine linkage material
          (Copilot receives the issue body + all existing comments at the
          moment of assignment, so the linkage comment must precede it).
        - Assigns the issue to COPILOT_AGENT_ASSIGNEE — this is the sole
          execution trigger for the Copilot coding agent.

    Delegation confirmation is based exclusively on the assignment API
    response.  The audit comment is recorded for traceability but is NOT
    part of the confirmation contract — Copilot does not react to
    post-assignment issue comments.

    Always records the delegation event in work_state.
    """
    dry_run = not config.enable_live_delegation
    issue_number = issue.get("number")
    issue_title = issue.get("title", "")
    issue_url = issue.get("html_url", "")
    body = issue.get("body") or ""

    fp = _extract_fingerprint_from_body(body) or f"unknown-{issue_number}"
    lane = _extract_lane_from_body(body) or "unknown"
    issue_labels: Set[str] = {
        lbl["name"] for lbl in issue.get("labels", []) if isinstance(lbl, dict)
    }
    subsystem = next((s for s in SUBSYSTEM_LABELS if s in issue_labels), "runtime")
    now = _iso_now()
    # Assignment is the sole execution trigger; the comment is audit-only.
    delegation_mechanism = "assignment"

    linkage_block = (
        "<!-- repo-architect-linkage\n"
        f"issue_number: {issue_number}\n"
        f"fingerprint: {fp}\n"
        f"run_id: {run_id}\n"
        f"lane: {lane}\n"
        "-->"
    )

    assignment_evidence: Optional[Dict[str, Any]] = None
    comment_evidence: Optional[Dict[str, Any]] = None
    errors: List[str] = []
    delegation_state = "delegation-requested"
    lifecycle_fact_state = "delegation-requested"
    delegation_confirmed_at: Optional[str] = None
    delegation_confirmation_evidence: Dict[str, Any] = {}

    result: Dict[str, Any] = {
        "action": "dry_run" if dry_run else "delegation_requested",
        "issue_number": issue_number,
        "issue_url": issue_url,
        "issue_title": issue_title,
        "fingerprint": fp,
        "assignee": None,
        "labels_added": ["delegation-requested", "in-progress"],
        "labels_removed": ["ready-for-delegation"],
        "dry_run": dry_run,
        "delegation_mechanism": delegation_mechanism,
        "delegation_assignment_evidence": None,
        "delegation_comment_evidence": None,
        "delegation_confirmation_evidence": None,
    }

    if dry_run:
        log(
            f"[dry-run] Would request delegation for issue #{issue_number} "
            f"to @{COPILOT_AGENT_ASSIGNEE}: {issue_title}",
            json_mode=config.log_json,
        )
    else:
        if not config.github_token or not config.github_repo:
            result["action"] = "delegation_failed"
            result["error"] = "Missing GITHUB_TOKEN or GITHUB_REPO for live delegation."
            errors.append(result["error"])
            delegation_state = "delegation-failed"
            lifecycle_fact_state = "failed-delegation"
        else:
            # 1. Update lifecycle labels
            new_labels = (issue_labels - {"ready-for-delegation"}) | {"delegation-requested", "in-progress"}
            try:
                ensure_github_labels(config, sorted(new_labels))
                set_github_issue_labels(config, issue_number, sorted(new_labels))
            except RepoArchitectError as exc:
                errors.append(f"label update: {exc}")

            # 2. Post pre-assignment audit comment with machine linkage
            #    material.  Copilot receives the issue body + all existing
            #    comments at the moment of assignment, so the linkage
            #    comment must be posted BEFORE the assignment call.
            comment = (
                f"**repo-architect delegation** (run `{run_id}`)\n\n"
                f"- active objective: `{config.active_objective or 'general'}`\n"
                f"- lane: `{lane}`\n"
                f"- issue fingerprint: `{fp}`\n"
                f"- target assignee: `@{COPILOT_AGENT_ASSIGNEE}`\n\n"
                f"{linkage_block}\n\n"
                "When opening a PR, include this exact linkage block (or the fingerprint marker) "
                "in the PR body so reconciliation can match with exact confidence.\n\n"
                "_This comment is posted before assignment so the Copilot coding agent "
                "receives it as part of the issue context._"
            )
            try:
                comment_resp = update_github_issue_api(config, issue_number, comment)
                is_dict = isinstance(comment_resp, dict)
                comment_evidence = {
                    "id": comment_resp.get("id") if is_dict else None,
                    "url": comment_resp.get("html_url") if is_dict else None,
                    "posted": is_dict and bool(comment_resp.get("id")),
                    "role": "pre-assignment-audit",
                }
            except RepoArchitectError as exc:
                errors.append(f"audit comment: {exc}")

            # 3. Assign to Copilot agent — this is the sole execution trigger.
            #    Confirmation is based exclusively on whether the assignment
            #    API response lists the target assignee.
            try:
                assign_resp = github_request(
                    config.github_token,
                    f"/repos/{config.github_repo}/issues/{issue_number}/assignees",
                    method="POST",
                    payload={"assignees": [COPILOT_AGENT_ASSIGNEE]},
                )
                assignees = assign_resp.get("assignees", []) if isinstance(assign_resp, dict) else []
                assignment_confirmed = any(
                    isinstance(a, dict) and a.get("login") == COPILOT_AGENT_ASSIGNEE
                    for a in assignees
                )
                assignment_evidence = {
                    "confirmed": assignment_confirmed,
                    "assignees": [a.get("login") for a in assignees if isinstance(a, dict)],
                }
                if assignment_confirmed:
                    delegation_confirmation_evidence["assignment"] = assignment_evidence
            except RepoArchitectError as exc:
                errors.append(f"assignment: {exc}")

            # Delegation confirmation is based solely on assignment evidence.
            # The audit comment is NOT part of the confirmation contract.
            if assignment_evidence and assignment_evidence.get("confirmed"):
                delegation_state = "delegation-confirmed"
                lifecycle_fact_state = "in-progress"
                delegation_confirmed_at = now
                result["action"] = "delegation_confirmed"
                result["assignee"] = COPILOT_AGENT_ASSIGNEE
            elif errors and not assignment_evidence:
                delegation_state = "delegation-failed"
                lifecycle_fact_state = "failed-delegation"
                result["action"] = "delegation_failed"
            else:
                delegation_state = "delegation-unconfirmed"
                lifecycle_fact_state = "delegation-requested"
                result["action"] = "delegation_unconfirmed"
            if errors:
                result["errors"] = errors
    result["delegation_assignment_evidence"] = assignment_evidence
    result["delegation_comment_evidence"] = comment_evidence
    result["delegation_confirmation_evidence"] = delegation_confirmation_evidence or None

    if dry_run:
        delegation_state = "delegation-requested"
        lifecycle_fact_state = "delegation-requested"

    # Record a top-level delegation event for auditability.
    append_delegation_event(
        work_state,
        {
            "ts": now,
            "run_id": run_id,
            "issue_number": issue_number,
            "issue_url": issue_url,
            "fingerprint": fp,
            "mechanism": delegation_mechanism,
            "outcome": delegation_state,
            "dry_run": dry_run,
            "assignment_evidence": assignment_evidence,
            "comment_evidence": comment_evidence,
            "errors": errors or None,
        },
    )

    # Record/update work item
    existing_item_dict: Optional[Dict[str, Any]] = None
    for it in work_state.get("items", []):
        if it.get("fingerprint") == fp:
            existing_item_dict = it
            break

    existing_requested_at = existing_item_dict.get("delegation_requested_at") if existing_item_dict else None
    work_item = WorkItem(
        fingerprint=fp,
        objective=(existing_item_dict.get("objective") if existing_item_dict else None) or config.active_objective or "",
        lane=(existing_item_dict.get("lane") if existing_item_dict else None) or lane,
        issue_number=issue_number,
        issue_state=(existing_item_dict.get("issue_state") if existing_item_dict else None) or "open",
        delegation_state=delegation_state,
        assignee=COPILOT_AGENT_ASSIGNEE if not dry_run else (existing_item_dict.get("assignee") if existing_item_dict else None),
        pr_number=existing_item_dict.get("pr_number") if existing_item_dict else None,
        pr_url=existing_item_dict.get("pr_url") if existing_item_dict else None,
        pr_state=existing_item_dict.get("pr_state") if existing_item_dict else None,
        merged=bool(existing_item_dict.get("merged")) if existing_item_dict else False,
        closed_unmerged=bool(existing_item_dict.get("closed_unmerged")) if existing_item_dict else False,
        blocked=bool(existing_item_dict.get("blocked")) if existing_item_dict else False,
        superseded=bool(existing_item_dict.get("superseded")) if existing_item_dict else False,
        created_at=(existing_item_dict.get("created_at") if existing_item_dict else None) or now,
        updated_at=now,
        run_id=run_id,
        gap_title=issue_title,
        gap_subsystem=subsystem,
        delegation_mechanism=delegation_mechanism,
        delegation_requested_at=existing_requested_at or now,
        delegation_confirmed_at=delegation_confirmed_at,
        delegation_confirmation_evidence=delegation_confirmation_evidence or None,
        delegation_comment_url=(comment_evidence or {}).get("url"),
        delegation_comment_id=(comment_evidence or {}).get("id"),
        delegation_assignment_evidence=assignment_evidence,
        pr_match_method=existing_item_dict.get("pr_match_method") if existing_item_dict else None,
        pr_match_confidence=existing_item_dict.get("pr_match_confidence") if existing_item_dict else None,
        pr_match_evidence=existing_item_dict.get("pr_match_evidence") if existing_item_dict else None,
        lifecycle_fact_state=lifecycle_fact_state,
        lifecycle_inferred_state=("execution-in-progress" if delegation_state == "delegation-confirmed" else None),
    )
    upsert_work_item(work_state, work_item)
    return result


def _list_prs_for_repo(
    config: Config, state: str = "all", per_page: int = 50
) -> List[Dict[str, Any]]:
    """List pull requests from the repository."""
    if not config.github_token or not config.github_repo:
        return []
    try:
        params = urllib.parse.urlencode({"state": state, "per_page": str(per_page)})
        result = github_request(
            config.github_token,
            f"/repos/{config.github_repo}/pulls?{params}",
        )
        return result if isinstance(result, list) else []
    except RepoArchitectError:
        return []


def _classify_pr(pr: Dict[str, Any]) -> str:
    """Classify a PR into a lifecycle state string."""
    if pr.get("merged_at"):
        return "merged"
    state = pr.get("state", "open")
    if state == "closed":
        return "closed_unmerged"
    if pr.get("draft"):
        return "draft"
    return "open"


def _extract_fingerprint_from_pr(pr: Dict[str, Any]) -> Optional[str]:
    """Extract arch-gap fingerprint marker from PR body."""
    body = pr.get("body") or ""
    return _extract_fingerprint_from_body(body)


def _extract_linkage_block(pr: Dict[str, Any]) -> Dict[str, str]:
    """Parse repo-architect linkage block from PR body, if present."""
    body = pr.get("body") or ""
    m = re.search(r"<!--\s*repo-architect-linkage(.*?)-->", body, re.DOTALL | re.IGNORECASE)
    if not m:
        return {}
    block = m.group(1)
    pairs: Dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        pairs[k.strip().lower()] = v.strip()
    return pairs


def _pr_mentions_issue(pr: Dict[str, Any], issue_number: int) -> bool:
    """Return True if the PR body/title references the given issue number."""
    body = (pr.get("body") or "").lower()
    title = (pr.get("title") or "").lower()
    needle = f"#{issue_number}"
    if needle in body or needle in title:
        return True
    # Also check for "closes/fixes/resolves NNN" patterns without #
    for pat in (f"closes {issue_number}", f"fixes {issue_number}", f"resolves {issue_number}"):
        if pat in body:
            return True
    return False


def _pr_branch_matches_issue(pr: Dict[str, Any], issue_number: int, fingerprint: str) -> bool:
    """Return True if PR head branch suggests linkage to issue/fingerprint."""
    head = pr.get("head", {}) if isinstance(pr.get("head"), dict) else {}
    ref = (head.get("ref") or "").lower()
    return (
        f"issue-{issue_number}" in ref
        or f"/{issue_number}" in ref
        or fingerprint in ref
    )


def _evaluate_pr_linkage(pr: Dict[str, Any], issue_number: int, fingerprint: str) -> Optional[Dict[str, Any]]:
    """Evaluate PR linkage evidence in priority order.

    Returns an evidence dict with fields:
    - method: one of PR_MATCH_METHOD_PRIORITY
    - confidence: exact|strong|weak
    - evidence: machine-readable details
    """
    # 1) explicit fingerprint marker in PR body
    pr_fp = _extract_fingerprint_from_pr(pr)
    if pr_fp and pr_fp == fingerprint:
        return {
            "method": "fingerprint_marker",
            "confidence": "exact",
            "evidence": {"fingerprint": pr_fp},
        }

    # 2) explicit linkage block metadata in PR body
    linkage = _extract_linkage_block(pr)
    if linkage:
        linkage_issue = linkage.get("issue_number")
        linkage_fp = linkage.get("fingerprint")
        if (linkage_issue and linkage_issue == str(issue_number)) or (linkage_fp and linkage_fp == fingerprint):
            return {
                "method": "linkage_block",
                "confidence": "exact",
                "evidence": linkage,
            }

    # 3) branch naming convention linked to issue/fingerprint
    if _pr_branch_matches_issue(pr, issue_number, fingerprint):
        head = pr.get("head", {}) if isinstance(pr.get("head"), dict) else {}
        return {
            "method": "branch_convention",
            "confidence": "strong",
            "evidence": {"branch": head.get("ref")},
        }

    # 4) closing keywords / linked issue references
    body = (pr.get("body") or "").lower()
    closing_patterns = (
        f"closes #{issue_number}", f"fixes #{issue_number}", f"resolves #{issue_number}",
        f"closes {issue_number}", f"fixes {issue_number}", f"resolves {issue_number}",
    )
    for pat in closing_patterns:
        if pat in body:
            return {
                "method": "closing_reference",
                "confidence": "strong",
                "evidence": {"pattern": pat},
            }

    # 5) fallback text mention of #issue_number in title/body
    if _pr_mentions_issue(pr, issue_number):
        return {
            "method": "issue_reference",
            "confidence": "weak",
            "evidence": {"issue_number": issue_number},
        }
    return None


def _best_pr_match(prs: List[Dict[str, Any]], issue_number: int, fingerprint: str) -> Optional[Dict[str, Any]]:
    """Select strongest PR match and keep ambiguity evidence."""
    candidates: List[Dict[str, Any]] = []
    state_rank = {"merged": 4, "open": 3, "draft": 2, "closed_unmerged": 1}
    method_rank = {m: i for i, m in enumerate(PR_MATCH_METHOD_PRIORITY[::-1], start=1)}
    for pr in prs:
        linkage = _evaluate_pr_linkage(pr, issue_number, fingerprint)
        if not linkage:
            continue
        pr_state = _classify_pr(pr)
        confidence = linkage["confidence"]
        candidates.append({
            "pr": pr,
            "method": linkage["method"],
            "confidence": confidence,
            "evidence": linkage["evidence"],
            "confidence_rank": MATCH_CONFIDENCE_RANK.get(confidence, 0),
            "method_rank": method_rank.get(linkage["method"], 0),
            "state_rank": state_rank.get(pr_state, 0),
            "pr_state": pr_state,
            "updated_at": pr.get("updated_at") or "",
        })
    if not candidates:
        return None

    candidates.sort(
        key=lambda c: (
            c["confidence_rank"],
            c["method_rank"],
            c["state_rank"],
            c["updated_at"],
        ),
        reverse=True,
    )
    best = candidates[0]
    best["ambiguous_matches"] = [
        {
            "pr_number": c["pr"].get("number"),
            "method": c["method"],
            "confidence": c["confidence"],
        }
        for c in candidates[1:]
        if c["confidence_rank"] == best["confidence_rank"] and c["method_rank"] == best["method_rank"]
    ]
    return best


def _update_issue_lifecycle_labels_for_pr(
    config: Config, issue_number: int, pr_class: str
) -> None:
    """Transition lifecycle labels on an issue based on the detected PR state."""
    if not config.github_token or not config.github_repo:
        return
    try:
        issue_data = github_request(
            config.github_token,
            f"/repos/{config.github_repo}/issues/{issue_number}",
        )
    except RepoArchitectError:
        return
    current = {lbl["name"] for lbl in issue_data.get("labels", []) if isinstance(lbl, dict)}
    new_labels = current - set(LIFECYCLE_LABELS) - set(LEGACY_LIFECYCLE_LABELS)
    if pr_class == "merged":
        new_labels.add("merged")
    elif pr_class == "closed_unmerged":
        new_labels.add("closed-unmerged")
    elif pr_class == "draft":
        new_labels.add("pr-draft")
    elif pr_class == "open":
        new_labels.add("pr-open")
    elif pr_class == "stale":
        new_labels.add("stale")
    try:
        ensure_github_labels(config, sorted(new_labels))
        set_github_issue_labels(config, issue_number, sorted(new_labels))
    except RepoArchitectError:
        pass


def reconcile_pr_state(
    config: Config, work_state: Dict[str, Any]
) -> Dict[str, Any]:
    """Ingest PR state back into work state for all tracked work items.

    For each tracked item that is not yet finished (merged / closed_unmerged),
    detect linked PRs and update item state + lifecycle labels accordingly.

    Returns a summary dict with ``status``, ``updated``, ``prs_found``, and ``details``.
    """
    items: List[Dict[str, Any]] = work_state.get("items", [])
    if not items:
        return {"status": "reconcile_complete", "updated": 0, "prs_found": 0, "details": []}

    # Fetch enough PRs to cover the reconciliation window (100 = GitHub API max per page)
    recent_prs = _list_prs_for_repo(config, state="all", per_page=100)
    stale_cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=config.stale_timeout_days)
    window_cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=config.reconciliation_window_days)
    # Filter PRs to the reconciliation window
    filtered_prs: List[Dict[str, Any]] = []
    for pr in recent_prs:
        created = pr.get("created_at") or ""
        try:
            pr_created = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
            if pr_created >= window_cutoff:
                filtered_prs.append(pr)
        except (ValueError, TypeError):
            filtered_prs.append(pr)  # keep PRs with unparseable dates
    recent_prs = filtered_prs
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    updated = 0
    prs_found = 0
    details: List[Dict[str, Any]] = []

    for i, item in enumerate(items):
        issue_number = item.get("issue_number")
        if not issue_number:
            continue
        # Already finished
        if item.get("merged") or item.get("closed_unmerged"):
            continue

        fingerprint = item.get("fingerprint") or ""
        best_match = _best_pr_match(recent_prs, int(issue_number), fingerprint)
        if not best_match:
            # Check for stale (delegated with no PR for too long)
            updated_str = item.get("updated_at")
            if item.get("delegation_state") in ("delegation-requested", "delegation-confirmed", "delegation-unconfirmed") and updated_str:
                try:
                    updated_at = dt.datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    if updated_at < stale_cutoff and item.get("pr_state") != "stale":
                        new_item = dict(item)
                        new_item["pr_state"] = "stale"
                        new_item["lifecycle_fact_state"] = "stale"
                        new_item["lifecycle_inferred_state"] = "needs-attention"
                        new_item["updated_at"] = now
                        items[i] = new_item
                        updated += 1
                        details.append({
                            "issue": issue_number,
                            "pr_state": "stale",
                            "pr_match_method": None,
                            "pr_match_confidence": None,
                            "pr_match_evidence": {"reason": "no_pr_match_within_window"},
                        })
                        if not config.dry_run:
                            _update_issue_lifecycle_labels_for_pr(
                                config, int(issue_number), "stale"
                            )
                except (ValueError, TypeError):
                    pass
            continue

        best_pr = best_match["pr"]
        pr_class = best_match["pr_state"]
        prs_found += 1

        new_item = dict(item)
        existing_conf = MATCH_CONFIDENCE_RANK.get(str(item.get("pr_match_confidence") or "").lower(), 0)
        new_conf = MATCH_CONFIDENCE_RANK.get(best_match["confidence"], 0)
        # Never overwrite a stronger existing match with weaker evidence.
        if existing_conf > new_conf and item.get("pr_number"):
            continue
        new_item["pr_number"] = best_pr.get("number")
        new_item["pr_url"] = best_pr.get("html_url")
        new_item["pr_state"] = pr_class
        new_item["pr_match_method"] = best_match["method"]
        new_item["pr_match_confidence"] = best_match["confidence"]
        new_item["pr_match_evidence"] = {
            "selected_pr_number": best_pr.get("number"),
            "method": best_match["method"],
            "confidence": best_match["confidence"],
            "evidence": best_match["evidence"],
            "ambiguous_matches": best_match.get("ambiguous_matches", []),
        }
        new_item["updated_at"] = now
        if pr_class == "merged":
            new_item["merged"] = True
            new_item["delegation_state"] = "delegation-confirmed"
            new_item["lifecycle_fact_state"] = "merged"
            new_item["lifecycle_inferred_state"] = "completed"
        elif pr_class == "closed_unmerged":
            new_item["closed_unmerged"] = True
            new_item["lifecycle_fact_state"] = "closed-unmerged"
            new_item["lifecycle_inferred_state"] = "needs-replanning"
        elif pr_class == "draft":
            new_item["delegation_state"] = "delegation-confirmed"
            new_item["lifecycle_fact_state"] = "pr-draft"
            new_item["lifecycle_inferred_state"] = "in-progress"
        elif pr_class == "open":
            new_item["delegation_state"] = "delegation-confirmed"
            new_item["lifecycle_fact_state"] = "pr-open"
            new_item["lifecycle_inferred_state"] = "in-progress"

        if new_item != item:
            items[i] = new_item
            updated += 1
            details.append({
                "issue": issue_number,
                "pr_number": best_pr.get("number"),
                "pr_state": pr_class,
                "old_delegation": item.get("delegation_state"),
                "new_delegation": new_item.get("delegation_state"),
                "pr_match_method": best_match["method"],
                "pr_match_confidence": best_match["confidence"],
                "pr_match_evidence": best_match["evidence"],
                "ambiguous_matches": best_match.get("ambiguous_matches", []),
            })
            if not config.dry_run:
                _update_issue_lifecycle_labels_for_pr(config, int(issue_number), pr_class)

    work_state["items"] = items
    return {
        "status": "reconcile_complete",
        "updated": updated,
        "prs_found": prs_found,
        "details": details,
    }


def ingest_issue_actions_to_work_state(
    config: Config,
    work_state: Dict[str, Any],
    issue_actions: List[Dict[str, Any]],
    run_id: str,
) -> None:
    """Record newly created/updated issues into the work state (memory lane).

    Called at the end of run_issue_cycle() so future planning passes can see
    what has already been submitted.
    """
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for action in issue_actions:
        if action.get("action") not in ("created", "updated", "dry_run"):
            continue
        fp = action.get("fingerprint")
        if not fp:
            continue
        issue_number = action.get("issue_number")
        gap_title = action.get("gap_title") or ""
        gap_subsystem = action.get("gap_subsystem") or "runtime"

        # Find existing item or create new
        existing: Optional[Dict[str, Any]] = None
        for it in work_state.get("items", []):
            if it.get("fingerprint") == fp:
                existing = it
                break

        if existing:
            # Refresh issue_number if it was just created
            new_it = dict(existing)
            if issue_number and not existing.get("issue_number"):
                new_it["issue_number"] = issue_number
            new_it["issue_state"] = "open"
            new_it["updated_at"] = now
            new_it["run_id"] = run_id
            new_it.setdefault("lifecycle_fact_state", "ready-for-delegation")
            upsert_work_item(work_state, WorkItem(**_normalize_work_item_dict(new_it)))
        else:
            work_item = WorkItem(
                fingerprint=fp,
                objective=config.active_objective or "",
                lane="unknown",
                issue_number=issue_number,
                issue_state="open",
                delegation_state="ready-for-delegation",
                assignee=None,
                pr_number=None,
                pr_url=None,
                pr_state=None,
                merged=False,
                closed_unmerged=False,
                blocked=False,
                superseded=False,
                created_at=now,
                updated_at=now,
                run_id=run_id,
                gap_title=gap_title,
                gap_subsystem=gap_subsystem,
                lifecycle_fact_state="ready-for-delegation",
            )
            upsert_work_item(work_state, work_item)


def _active_fingerprints_in_work_state(work_state: Dict[str, Any]) -> Set[str]:
    """Return fingerprints of issues that are currently in-progress or delegated.

    Used by the planner to avoid re-raising the same issue when one is already active.
    """
    return {
        it["fingerprint"]
        for it in work_state.get("items", [])
        if it.get("fingerprint")
        and it.get("delegation_state") in (
            "delegation-requested", "delegation-confirmed", "delegation-unconfirmed"
        )
        and not it.get("merged")
        and not it.get("closed_unmerged")
    }


def run_execution_cycle(config: Config) -> Dict[str, Any]:
    """Execute one execution-lane pass: select + delegate one ready issue.

    Steps:
    1. Load work state.
    2. Reconcile PR state (so selection sees current issue states).
    3. Select one ready issue.
    4. Delegate it (dry-run or live depending on config.enable_live_delegation).
    5. Save updated work state.
    6. Return structured result.
    """
    ensure_agent_dir(config.agent_dir)
    work_state = load_work_state(config)

    # Run lightweight reconciliation first so selection state is fresh
    reconcile_result = reconcile_pr_state(config, work_state)

    run_id = (
        os.environ.get("REPO_ARCHITECT_BRANCH_SUFFIX")
        or os.environ.get("GITHUB_RUN_ID")
        or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    )

    selected = select_ready_issue(config, work_state)
    if selected is None:
        save_work_state(config, work_state)
        return {
            "status": "execution_cycle_complete",
            "mode": EXECUTION_MODE,
            "dry_run": not config.enable_live_delegation,
            "selected_issue": None,
            "delegation": None,
            "reconcile": reconcile_result,
            "message": "No ready issues available for delegation.",
        }

    delegation_result = delegate_to_copilot(config, selected, work_state, run_id)
    save_work_state(config, work_state)

    if not config.enable_live_delegation:
        summary_line = (
            f"[dry-run] delegation requested for issue #{selected.get('number')} "
            f"— {selected.get('title', '')}"
        )
    else:
        summary_line = (
            f"{delegation_result.get('action', 'delegation_requested')} issue "
            f"#{selected.get('number')} — {selected.get('title', '')}"
        )
    log(summary_line, json_mode=config.log_json)

    result: Dict[str, Any] = {
        "status": "execution_cycle_complete",
        "mode": EXECUTION_MODE,
        "dry_run": not config.enable_live_delegation,
        "selected_issue": {
            "number": selected.get("number"),
            "title": selected.get("title"),
            "url": selected.get("html_url"),
        },
        "delegation": delegation_result,
        "reconcile": reconcile_result,
        "summary": [summary_line],
    }
    write_step_summary(config, result)
    return result


def run_reconciliation_cycle(config: Config) -> Dict[str, Any]:
    """Execute one reconciliation-lane pass: ingest PR outcomes into work state.

    Steps:
    1. Load work state.
    2. Fetch all recent PRs.
    3. Update item states and lifecycle labels.
    4. Save updated work state.
    5. Return structured result.
    """
    ensure_agent_dir(config.agent_dir)
    work_state = load_work_state(config)
    reconcile_result = reconcile_pr_state(config, work_state)
    save_work_state(config, work_state)

    summary = (
        f"reconcile: {reconcile_result['updated']} items updated, "
        f"{reconcile_result['prs_found']} PRs found"
    )
    log(summary, json_mode=config.log_json)

    result: Dict[str, Any] = {
        "status": "reconcile_cycle_complete",
        "mode": RECONCILE_MODE,
        "dry_run": config.dry_run,
        "updated": reconcile_result.get("updated", 0),
        "prs_found": reconcile_result.get("prs_found", 0),
        "details": reconcile_result.get("details", []),
        "summary": [summary],
    }
    write_step_summary(config, result)
    return result


def remove_marked_debug_prints(root: pathlib.Path, analysis: Dict[str, Any], budget: int) -> Optional[PatchPlan]:
    if budget <= 0:
        return None
    file_changes: Dict[str, str] = {}
    touched: List[str] = []
    for info in analysis["python_files"]:
        if not info["debug_print_lines"]:
            continue
        path = root / info["path"]
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines(True)
        new_lines: List[str] = []
        changed = False
        for line in lines:
            if DEBUG_MARKER_RE.search(line) and PRINT_RE.search(line):
                changed = True
                continue
            new_lines.append(line)
        if changed:
            file_changes[info["path"]] = "".join(new_lines)
            touched.append(info["path"])
        if len(touched) >= budget:
            break
    if not file_changes:
        return None
    reason = f"remove-{len(touched)}-marked-debug-print-sites"
    return PatchPlan(
        task="remove_marked_debug_prints",
        reason=reason,
        file_changes=file_changes,
        metadata={"lane": "hygiene", "touched": touched},
        pr_title="agent: remove marked debug prints",
        pr_body="Automated hygiene PR removing explicitly marked debug print statements.",
        stable_branch_hint="agent/hygiene/remove-marked-debug-prints",
    )


def _charter_system_prefix(analysis: Dict[str, Any]) -> str:
    """Return a brief charter-guidance preamble to prepend to model system messages.

    Returns an empty string when no charter is loaded, so callers do not need
    to guard against it.
    """
    charter_context = analysis.get("charter_context") or {}
    text = charter_context.get("content", "")
    if not text:
        return ""
    return (
        "\n\nAuthoritative architectural charter for this repository "
        "(obey its engineering direction when producing code mutations):\n"
        + text
        + "\n"
    )


def build_report_plan(config: Config, analysis: Dict[str, Any], model_meta: Dict[str, Any], state: Dict[str, Any]) -> Optional[PatchPlan]:
    suite = build_report_suite(analysis, model_meta)
    bundle_hash = sha256_text("\n".join([k + "\n" + v for k, v in sorted(suite.items())]))
    if state.get("last_report_hash") == bundle_hash and config.mode == "report":
        return None
    file_changes = suite
    evidence = [
        f"Architecture score: {analysis['architecture_score']}",
        f"Local import cycles: {len(analysis['cycles'])}",
        f"Parse-error files: {len(analysis['parse_error_files'])}",
        f"Entrypoints: {len(analysis['entrypoint_paths'])}",
    ]
    if model_meta.get("used") and model_meta.get("summary"):
        evidence.append("Model-assisted prioritization included.")
    body = textwrap.dedent(f"""
    Automated documentation refresh from {APP_NAME}.

    Why it acted:
    - report mode requested or stale report suite detected
    - repository state changed enough to justify refreshed architecture docs

    Evidence:
    {chr(10).join(f'- {x}' for x in evidence)}

    Validation:
    - documentation-only mutation
    - no Python files changed
    - artifact suite uploaded by workflow
    """).strip()
    return PatchPlan(
        task="publish_runtime_inventory_report",
        reason="refresh-runtime-inventory-and-risk-packet",
        file_changes=file_changes,
        metadata={"lane": "report", "report_hash": bundle_hash, "report_files": sorted(file_changes)},
        pr_title="agent: refresh runtime inventory and architecture packet",
        pr_body=body,
        stable_branch_hint="agent/report/runtime-inventory-packet",
    )


def build_parse_errors_plan(config: Config, analysis: Dict[str, Any]) -> Optional[PatchPlan]:
    """Use the preferred/fallback model to fix one or more Python parse errors."""
    errors = analysis.get("parse_error_files", [])
    if not errors:
        return None
    preferred = config.github_model or config.preferred_model
    if not config.github_token or not preferred:
        return None
    fallback = config.fallback_model
    py_infos_by_path = {i["path"]: i for i in analysis["python_files"]}
    targets = errors[:3]
    snippets: List[str] = []
    for rel in targets:
        abs_path = config.git_root / rel
        if not abs_path.exists():
            continue
        source = abs_path.read_text(encoding="utf-8", errors="replace")[:_MAX_SOURCE_SNIPPET_CHARS]
        err_detail = py_infos_by_path.get(rel, {}).get("parse_error", "syntax error")
        snippets.append(f"File: {rel}\nError: {err_detail}\n```python\n{source}\n```")
    if not snippets:
        return None
    prompt = textwrap.dedent(f"""
    Fix the Python syntax/parse errors in the following file(s).
    Return ONLY a JSON object with this exact structure (no markdown, no explanation):
    {{"files": {{"<relative_path>": "<corrected_full_file_content>"}}}}

    Files to fix:
    {chr(10).join(snippets)}
    """).strip()
    resp, _req, fallback_reason, _fell = call_models_with_fallback_or_none(
        config.github_token, preferred, fallback,
        [
            {"role": "system", "content": "You fix Python syntax errors. Return only valid JSON with corrected file contents." + _charter_system_prefix(analysis)},
            {"role": "user", "content": prompt},
        ],
    )
    if resp is None:
        return None
    try:
        text = parse_model_text(resp)
        data = extract_json_from_model_text(text)
        raw_files: Dict[str, str] = data.get("files", {})
    except (RepoArchitectError, KeyError, TypeError):
        return None
    valid_changes: Dict[str, str] = {}
    for rel, content in raw_files.items():
        rel_norm = rel.lstrip("/")
        if rel_norm not in targets:
            continue
        try:
            ast.parse(content)
            valid_changes[rel_norm] = content
        except SyntaxError:
            pass  # Model's fix still has errors; skip this file
    if not valid_changes:
        return None
    return PatchPlan(
        task="fix_parse_errors",
        reason=f"model-assisted fix for {len(valid_changes)} parse error(s)",
        file_changes=valid_changes,
        metadata={"lane": "parse_errors", "fixed_files": sorted(valid_changes), "fallback_reason": fallback_reason},
        pr_title="agent: fix Python parse errors",
        pr_body=f"Automated fix for {len(valid_changes)} Python parse error(s) using model-assisted repair.",
        stable_branch_hint="agent/fix/parse-errors",
    )


def build_import_cycles_plan(config: Config, analysis: Dict[str, Any]) -> Optional[PatchPlan]:
    """Use the preferred/fallback model to break one import cycle via TYPE_CHECKING guards or lazy imports."""
    cycles = analysis.get("cycles", [])
    if not cycles:
        return None
    preferred = config.github_model or config.preferred_model
    if not config.github_token or not preferred:
        return None
    fallback = config.fallback_model
    cycle = min(cycles, key=len)
    cycle_modules = [m for m in cycle if m != cycle[-1]]
    py_infos_by_module = {i["module"]: i for i in analysis["python_files"]}
    snippets: List[str] = []
    module_to_path: Dict[str, str] = {}
    for mod in cycle_modules[:4]:
        info = py_infos_by_module.get(mod, {})
        rel = info.get("path", "")
        if not rel:
            continue
        abs_path = config.git_root / rel
        if not abs_path.exists():
            continue
        module_to_path[mod] = rel
        source = abs_path.read_text(encoding="utf-8", errors="replace")[:_MAX_CYCLE_SNIPPET_CHARS]
        snippets.append(f"Module: {mod}\nFile: {rel}\n```python\n{source}\n```")
    if not snippets:
        return None
    cycle_str = " -> ".join(cycle)
    prompt = textwrap.dedent(f"""
    Break this Python import cycle by modifying the minimal number of files.
    Prefer TYPE_CHECKING guards or lazy imports to avoid behavioral changes.
    Import cycle: {cycle_str}

    Return ONLY a JSON object (no markdown, no explanation):
    {{"files": {{"<relative_path>": "<corrected_full_file_content>"}}}}

    Files in cycle:
    {chr(10).join(snippets)}
    """).strip()
    resp, _req, fallback_reason, _fell = call_models_with_fallback_or_none(
        config.github_token, preferred, fallback,
        [
            {"role": "system", "content": "You fix Python import cycles. Return only valid JSON with corrected file contents." + _charter_system_prefix(analysis)},
            {"role": "user", "content": prompt},
        ],
    )
    if resp is None:
        return None
    try:
        text = parse_model_text(resp)
        data = extract_json_from_model_text(text)
        raw_files: Dict[str, str] = data.get("files", {})
    except (RepoArchitectError, KeyError, TypeError):
        return None
    all_cycle_paths = set(module_to_path.values())
    valid_changes: Dict[str, str] = {}
    for rel, content in raw_files.items():
        rel_norm = rel.lstrip("/")
        if rel_norm not in all_cycle_paths:
            continue
        try:
            ast.parse(content)
            valid_changes[rel_norm] = content
        except SyntaxError:
            pass
    if not valid_changes:
        return None
    return PatchPlan(
        task="break_import_cycle",
        reason=f"model-assisted cycle break: {cycle_str}",
        file_changes=valid_changes,
        metadata={"lane": "import_cycles", "cycle": cycle, "fallback_reason": fallback_reason},
        pr_title="agent: break import cycle",
        pr_body=f"Automated fix to break import cycle: `{cycle_str}`.",
        stable_branch_hint="agent/fix/import-cycle",
    )


def build_entrypoint_consolidation_plan(config: Config, analysis: Dict[str, Any]) -> Optional[PatchPlan]:
    """Use the preferred/fallback model to consolidate redundant backend server entrypoints.

    Only activates when the number of backend_servers entrypoints exceeds
    _ENTRYPOINT_CONSOLIDATION_THRESHOLD.  The model is asked to add a single
    ``# DEPRECATED: prefer <canonical>`` comment to the least-canonical duplicate
    so the runtime intent is preserved while the codebase signals what to migrate
    toward.  All generated changes are validated with ast.parse before use.
    """
    clusters = analysis.get("entrypoint_clusters", {})
    backend_eps = clusters.get("backend_servers", [])
    if len(backend_eps) < _ENTRYPOINT_CONSOLIDATION_THRESHOLD:
        return None
    preferred = config.github_model or config.preferred_model
    if not config.github_token or not preferred:
        return None
    fallback = config.fallback_model
    # Collect up to _ENTRYPOINT_CONSOLIDATION_CANDIDATES by path length (shortest = likely wrappers)
    # then send at most _ENTRYPOINT_CONSOLIDATION_SNIPPETS to the model
    snippets: List[str] = []
    candidate_paths: List[str] = []
    for rel in sorted(backend_eps[:_ENTRYPOINT_CONSOLIDATION_CANDIDATES], key=lambda p: len(p)):
        abs_path = config.git_root / rel
        if not abs_path.exists():
            continue
        source = abs_path.read_text(encoding="utf-8", errors="replace")[:_MAX_SOURCE_SNIPPET_CHARS]
        snippets.append(f"File: {rel}\n```python\n{source}\n```")
        candidate_paths.append(rel)
        if len(snippets) >= _ENTRYPOINT_CONSOLIDATION_SNIPPETS:
            break
    if len(candidate_paths) < 2:
        return None
    prompt = textwrap.dedent(f"""
    This repository has {len(backend_eps)} backend server entrypoints, suggesting runtime duplication.
    Identify exactly ONE file that is clearly a redundant wrapper or legacy entrypoint.
    Add ONLY a single comment line at the top of that file:
      # DEPRECATED: prefer <canonical_entrypoint_path> - this file may be removed in a future cleanup

    Do NOT make any other changes.
    Return ONLY a JSON object (no markdown, no explanation):
    {{"files": {{"<relative_path>": "<full_file_content_with_deprecation_comment>"}}}}

    Entrypoints to consider:
    {chr(10).join(snippets)}
    """).strip()
    resp, _req, fallback_reason, _fell = call_models_with_fallback_or_none(
        config.github_token, preferred, fallback,
        [
            {"role": "system", "content": "You annotate redundant Python entrypoints with deprecation comments. Return only valid JSON." + _charter_system_prefix(analysis)},
            {"role": "user", "content": prompt},
        ],
    )
    if resp is None:
        return None
    try:
        text = parse_model_text(resp)
        data = extract_json_from_model_text(text)
        raw_files: Dict[str, str] = data.get("files", {})
    except (RepoArchitectError, KeyError, TypeError):
        return None
    all_ep_paths = set(candidate_paths)
    valid_changes: Dict[str, str] = {}
    for rel, content in raw_files.items():
        rel_norm = rel.lstrip("/")
        if rel_norm not in all_ep_paths:
            continue
        try:
            ast.parse(content)
            valid_changes[rel_norm] = content
        except SyntaxError:
            pass
    if not valid_changes:
        return None
    # Use sorted order to make target selection deterministic across runs
    target = sorted(valid_changes.keys())[0]
    return PatchPlan(
        task="annotate_deprecated_entrypoint",
        reason=f"deprecation comment on redundant entrypoint: {target}",
        file_changes=valid_changes,
        metadata={"lane": "entrypoint_consolidation", "annotated": sorted(valid_changes), "fallback_reason": fallback_reason, "total_backend_entrypoints": len(backend_eps)},
        pr_title="agent: annotate redundant server entrypoint as deprecated",
        pr_body=textwrap.dedent(f"""
        Automated entrypoint consolidation step.

        This repository has **{len(backend_eps)} backend server entrypoints** — above the
        consolidation threshold of {_ENTRYPOINT_CONSOLIDATION_THRESHOLD}. This PR adds a
        `# DEPRECATED` comment to one identified redundant wrapper, making migration intent
        explicit without changing any runtime behaviour.

        Annotated file(s): {', '.join(f'`{p}`' for p in sorted(valid_changes))}

        Validation: `ast.parse` passed on all changed files.
        """).strip(),
        stable_branch_hint="agent/fix/entrypoint-consolidation",
    )


def build_patch_plan(
    config: Config, analysis: Dict[str, Any], model_meta: Dict[str, Any], state: Dict[str, Any],
) -> Tuple[Optional[PatchPlan], str, Optional[str]]:
    """Return (plan, selected_lane, no_safe_code_mutation_reason).

    Lane priority order (mutate / campaign):
      1. parse_errors              – model-assisted syntax fix
      2. import_cycles             – model-assisted cycle break
      3. entrypoint_consolidation  – deprecate redundant server entrypoints
      4. hygiene                   – remove marked debug prints
      5. report                    – refresh architecture documentation

    A report-only mutation is never produced when parse errors exist unless no
    safe code mutation can be made (reason is then surfaced explicitly).

    Charter alignment: ``mutate`` and ``campaign`` modes implement the narrow,
    validated self-modification lanes defined in GODELOS_REPO_IMPLEMENTATION_CHARTER
    §9–§10.  They are retained as charter-sanctioned secondary modes.  The default
    safe operating mode is ``issue`` (architectural governance via GitHub Issues).
    """
    if config.mode == "analyze":
        return None, "none", None

    if config.mode in CHARTER_MUTATION_MODES:
        log(
            f"ℹ️  mode '{config.mode}' performs direct code mutation via charter-validated lanes "
            "(§9–§10 GODELOS_REPO_IMPLEMENTATION_CHARTER).  "
            "The default safe operating mode is --mode issue (architectural governance via GitHub Issues).",
            json_mode=config.log_json,
        )

    lanes = config.campaign_lanes if config.campaign_lanes else MUTATION_LANE_ORDER
    skipped_reasons: List[str] = []

    if config.mode in ("mutate", "campaign"):
        for lane in lanes:
            if lane == "parse_errors":
                if analysis.get("parse_error_files"):
                    plan = build_parse_errors_plan(config, analysis)
                    if plan:
                        return plan, "parse_errors", None
                    skipped_reasons.append("parse_errors: model unavailable or returned no valid fix")
            elif lane == "import_cycles":
                if analysis.get("cycles"):
                    plan = build_import_cycles_plan(config, analysis)
                    if plan:
                        return plan, "import_cycles", None
                    skipped_reasons.append("import_cycles: model unavailable or returned no valid fix")
            elif lane == "entrypoint_consolidation":
                plan = build_entrypoint_consolidation_plan(config, analysis)
                if plan:
                    return plan, "entrypoint_consolidation", None
                # Not an error to skip - threshold may not be met
            elif lane == "hygiene":
                plan = remove_marked_debug_prints(config.git_root, analysis, config.mutation_budget)
                if plan:
                    return plan, "hygiene", None
            elif lane == "report":
                # Suppress report-only if parse errors exist and a code fix was attempted
                if analysis.get("parse_error_files") and skipped_reasons:
                    skipped_reasons.append("report: suppressed because parse errors exist and code fix was attempted")
                    continue
                plan = build_report_plan(config, analysis, model_meta, state)
                if plan:
                    return plan, "report", None
        no_reason = "; ".join(skipped_reasons) if skipped_reasons else "no actionable mutation found for any lane"
        return None, "none", no_reason

    # report mode
    plan = build_report_plan(config, analysis, model_meta, state)
    return plan, "report", None


# -----------------------------
# Validation / execution
# -----------------------------

def validate_change(config: Config, changed_files: Sequence[str], lane: Optional[str] = None) -> Tuple[bool, str]:
    """Validate changed files.  py_compile is always run for Python files.
    If *lane* is ``import_cycles``, an additional import smoke test is attempted."""
    py_files = [p for p in changed_files if p.endswith('.py')]
    if not py_files:
        return True, 'No Python files changed.'
    # Syntax check (fast; catches typos and broken edits)
    proc = run_cmd([sys.executable, '-m', 'py_compile', *py_files], cwd=config.git_root, check=False)
    syntax_out = (proc.stdout or '') + (proc.stderr or '')
    if proc.returncode != 0:
        return False, syntax_out.strip() or 'py_compile failed'

    # Extended validation for import-cycle lane: attempt "import <module>" for changed files.
    # This is a best-effort smoke test — import failures are common in partial repos so
    # results are warnings only (they never block the mutation).
    if lane == "import_cycles":
        smoke_results: List[str] = []
        for pf in py_files:
            mod = pf.replace("/", ".").replace("\\", ".").removesuffix(".py")
            # Skip hidden files / relative-path artefacts (e.g. ".tmp/foo.py" → ".tmp.foo")
            if mod.startswith("."):
                continue
            smoke = run_cmd(
                [sys.executable, "-c", f"import importlib; importlib.import_module({mod!r})"],
                cwd=config.git_root, check=False,
            )
            if smoke.returncode != 0:
                err = (smoke.stdout or '') + (smoke.stderr or '')
                truncated = err.strip()[:200]
                if len(err.strip()) > 200:
                    truncated += " [truncated]"
                smoke_results.append(f"import {mod}: warning: {truncated}")
        if smoke_results:
            return True, "py_compile passed; import smoke warnings: " + "; ".join(smoke_results)

    return True, syntax_out.strip() or 'py_compile passed'


def apply_patch_plan(config: Config, plan: PatchPlan, state: Dict[str, Any]) -> Dict[str, Any]:
    baseline_dirty_guard(config)
    if not git_identity_present(config.git_root):
        raise RepoArchitectError('Git identity is not configured. Set git user.name and user.email before mutation.')

    start_branch = git_current_branch(config.git_root)
    branch = with_unique_branch_suffix(safe_branch_name(plan.stable_branch_hint))
    backups: Dict[str, str] = {}
    changed_files = list(plan.file_changes.keys())
    git_checkout_branch(config.git_root, branch)

    try:
        for rel, content in plan.file_changes.items():
            abs_path = config.git_root / rel
            if abs_path.exists():
                backups[rel] = abs_path.read_text(encoding='utf-8', errors='replace')
            atomic_write_text(abs_path, content)

        if not git_is_dirty(config.git_root):
            git_checkout(config.git_root, start_branch)
            return {"status": "no_meaningful_delta", "branch": branch, "changed_files": []}

        ok, validation = validate_change(config, changed_files, lane=plan.metadata.get("lane"))
        if not ok:
            raise RepoArchitectError(f'Validation failed.\n{validation}')

        commit_message = f"agent: {plan.task}"
        git_stage_and_commit(config.git_root, changed_files, commit_message)
        pushed = False
        pr_url = None
        pr_number = None
        if config.github_token and config.github_repo and git_has_remote_origin(config.git_root):
            # Pre-check: if remote branch already exists (from a prior run), generate a fresh name.
            # Use a timestamp-based suffix so retries within the same run are also distinct.
            for retry_n in range(1, 4):
                if not git_remote_branch_exists(config.git_root, branch):
                    break
                branch = with_unique_branch_suffix(
                    safe_branch_name(f"{plan.stable_branch_hint}-retry{retry_n}")
                )
                git_checkout_branch(config.git_root, branch)
            try:
                git_push_branch(config.git_root, branch)
            except RepoArchitectError as push_exc:
                # One retry on non-fast-forward / rejected push
                err_lower = str(push_exc).lower()
                if "non-fast-forward" in err_lower or "rejected" in err_lower or "failed to push" in err_lower:
                    branch = with_unique_branch_suffix(
                        safe_branch_name(f"{plan.stable_branch_hint}-retry{retry_n + 1}")
                    )
                    git_checkout_branch(config.git_root, branch)
                    git_push_branch(config.git_root, branch)
                else:
                    raise
            pushed = True
            pr = create_or_update_pull_request(config, branch, plan.pr_title, plan.pr_body)
            pr_url = pr.get('html_url')
            pr_number = pr.get('number')

        if plan.metadata.get('report_hash'):
            state['last_report_hash'] = plan.metadata['report_hash']

        return {
            "status": "mutated",
            "branch": branch,
            "base_branch": start_branch,
            "changed_files": changed_files,
            "validation": validation,
            "pushed": pushed,
            "pull_request_url": pr_url,
            "pull_request_number": pr_number,
            "metadata": plan.metadata,
        }
    except Exception:
        for rel, old_text in backups.items():
            atomic_write_text(config.git_root / rel, old_text)
        try:
            git_checkout(config.git_root, start_branch)
        except Exception:
            pass
        raise


# -----------------------------
# Workflow / summary
# -----------------------------

def workflow_yaml(secret_env_names: Sequence[str], cron: str, github_model: Optional[str]) -> str:
    extra_env = "".join(f"          {name}: ${{{{ secrets.{name} }}}}\n" for name in secret_env_names)
    return f"""name: repo-architect

on:
  workflow_dispatch:
    inputs:
      mode:
        description: 'Execution mode'
        required: true
        default: 'report'
        type: choice
        options:
          - analyze
          - report
          - mutate
          - campaign
      github_model:
        description: 'GitHub Models model id (overrides preferred model; leave blank to use catalog resolution)'
        required: false
        default: ''
        type: string
      github_fallback_model:
        description: 'GitHub Models fallback model id (used if primary model fails)'
        required: false
        default: ''
        type: string
      report_path:
        description: 'Primary report path'
        required: true
        default: '{DEFAULT_REPORT_PATH.as_posix()}'
        type: string
      mutation_budget:
        description: 'Maximum automatic mutations in a single run'
        required: true
        default: '1'
        type: choice
        options:
          - '1'
          - '2'
          - '3'
      max_slices:
        description: 'Campaign max slices (campaign mode only)'
        required: false
        default: '3'
        type: string
      lanes:
        description: 'Comma-separated lane order (mutate and campaign modes)'
        required: false
        default: 'parse_errors,import_cycles,entrypoint_consolidation,hygiene,report'
        type: string
  schedule:
    - cron: '{cron}'

concurrency:
  group: repo-architect-${{{{ github.ref }}}}
  cancel-in-progress: true

permissions:
  contents: write
  pull-requests: write
  models: read

jobs:
  repo-architect:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.x'

      - name: Configure git identity
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

      - name: Ensure artifact directories exist
        run: |
          mkdir -p .agent docs/repo_architect

      - name: Resolve GitHub Models configuration
        env:
          GITHUB_TOKEN: ${{{{ github.token }}}}
          GITHUB_MODEL: ${{{{ github.event.inputs.github_model }}}}
          GITHUB_FALLBACK_MODEL: ${{{{ github.event.inputs.github_fallback_model }}}}
        run: |
          python - <<'PY'
          import json
          import os
          import urllib.request

          env_github_model = os.environ.get("GITHUB_MODEL", "").strip()
          env_github_fallback_model = os.environ.get("GITHUB_FALLBACK_MODEL", "").strip()
          order = [
              "openai/gpt-5",
              "openai/o3",
          ]
          available = set()
          catalog_ok = False
          try:
              req = urllib.request.Request(
                  "https://models.github.ai/catalog/models",
                  headers={{
                      "Authorization": f"Bearer {{os.environ['GITHUB_TOKEN']}}",
                      "Accept": "application/json",
                      "User-Agent": "repo-architect-workflow",
                  }},
              )
              with urllib.request.urlopen(req, timeout=30) as resp:
                  payload = json.loads(resp.read().decode("utf-8"))
              models = payload.get("data", payload) if isinstance(payload, dict) else payload
              if isinstance(models, list):
                  catalog_ok = True
                  for item in models:
                      if isinstance(item, dict):
                          model_id = item.get("id") or item.get("name") or item.get("model")
                          if isinstance(model_id, str) and model_id:
                              available.add(model_id)
          except Exception as exc:
              print(f"warning: GitHub Models catalog lookup failed; using defaults ({{exc}})")

          def first_available(candidates):
              for candidate in candidates:
                  if candidate in available:
                      return candidate
              return None

          def deterministic_available(exclude=None):
              candidates = sorted(m for m in available if m != exclude)
              return candidates[0] if candidates else None

          if env_github_model:
              preferred = env_github_model
          elif catalog_ok and available:
              preferred = first_available(order) or deterministic_available() or order[0]
          else:
              preferred = order[0]

          if env_github_fallback_model:
              fallback = env_github_fallback_model
          elif catalog_ok and available:
              fallback = (
                  first_available([c for c in order if c != preferred])
                  or deterministic_available(exclude=preferred)
                  or preferred
              )
          else:
              fallback = order[1] if len(order) > 1 and order[1] != preferred else order[0]

          if not isinstance(preferred, str) or not preferred:
              preferred = order[0]
          if not isinstance(fallback, str) or not fallback:
              fallback = order[1] if len(order) > 1 and order[1] != preferred else order[0]

          env_file = os.environ.get("GITHUB_ENV")
          if not env_file:
              raise RuntimeError("GITHUB_ENV is not set; this internal workflow step must run inside GitHub Actions with environment-file support.")
          with open(env_file, "a", encoding="utf-8") as fh:
              fh.write(f"REPO_ARCHITECT_PREFERRED_MODEL={{preferred}}\\n")
              fh.write(f"REPO_ARCHITECT_FALLBACK_MODEL={{fallback}}\\n")
          print(f"selected preferred={{preferred}} fallback={{fallback}}")
          PY

      - name: Run repo architect
        env:
          GITHUB_TOKEN: ${{{{ github.token }}}}
          GITHUB_REPO: ${{{{ github.repository }}}}
          GITHUB_BASE_BRANCH: ${{{{ github.event.repository.default_branch }}}}
          REPO_ARCHITECT_BRANCH_SUFFIX: ${{{{ github.run_id }}}}-${{{{ github.run_attempt }}}}
          GITHUB_MODEL: ${{{{ github.event.inputs.github_model }}}}
          GITHUB_FALLBACK_MODEL: ${{{{ github.event.inputs.github_fallback_model }}}}
{extra_env}        run: |
          MODE="${{{{ github.event.inputs.mode }}}}"
          MODEL="${{{{ github.event.inputs.github_model }}}}"
          REPORT_PATH="${{{{ github.event.inputs.report_path }}}}"
          MUTATION_BUDGET="${{{{ github.event.inputs.mutation_budget }}}}"
          MAX_SLICES="${{{{ github.event.inputs.max_slices }}}}"
          LANES="${{{{ github.event.inputs.lanes }}}}"
          if [ -z "$MODE" ]; then MODE="report"; fi
          if [ -z "$REPORT_PATH" ]; then REPORT_PATH="{DEFAULT_REPORT_PATH.as_posix()}"; fi
          if [ -z "$MUTATION_BUDGET" ]; then MUTATION_BUDGET="1"; fi
          if [ -z "$MAX_SLICES" ]; then MAX_SLICES="3"; fi
          if [ -z "$LANES" ]; then LANES="parse_errors,import_cycles,entrypoint_consolidation,hygiene,report"; fi
          EXTRA_ARGS=""
          if [ -n "$MODEL" ]; then EXTRA_ARGS="$EXTRA_ARGS --github-model $MODEL"; fi
          if [ "$MODE" = "campaign" ]; then
            EXTRA_ARGS="$EXTRA_ARGS --max-slices $MAX_SLICES --lanes $LANES"
          elif [ "$MODE" = "mutate" ]; then
            EXTRA_ARGS="$EXTRA_ARGS --lanes $LANES"
          fi
          python repo_architect.py --allow-dirty --mode "$MODE" --report-path "$REPORT_PATH" --mutation-budget "$MUTATION_BUDGET" $EXTRA_ARGS

      - name: Upload repo architect artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: repo-architect-${{{{ github.run_id }}}}
          path: |
            .agent
            docs/repo_architect
          if-no-files-found: warn
          retention-days: 7
"""


def install_workflow(config: Config, secret_env_names: Sequence[str], cron: str) -> pathlib.Path:
    config.workflow_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(config.workflow_path, workflow_yaml(secret_env_names, cron, config.github_model))
    return config.workflow_path


# -----------------------------
# Orchestrator
# -----------------------------

def persist_manifest(config: Config, artifact_files: List[str]) -> None:
    atomic_write_json(config.artifact_manifest_path, {"artifact_files": artifact_files, "generated_at": int(time.time())})


def run_cycle(config: Config) -> Dict[str, Any]:
    # Route modes to dedicated cycle functions
    if config.mode == ISSUE_MODE:
        return run_issue_cycle(config)
    if config.mode == EXECUTION_MODE:
        return run_execution_cycle(config)
    if config.mode == RECONCILE_MODE:
        return run_reconciliation_cycle(config)

    ensure_agent_dir(config.agent_dir)
    state = load_state(config)
    analysis = build_analysis(config.git_root)
    charter_context = load_charter_context(config.git_root)
    analysis["charter_context"] = charter_context
    model_meta = enrich_with_github_models(config, analysis)
    # Mark charter as applied if the model was actually used
    if model_meta.get("used") or model_meta.get("enabled"):
        charter_context["applied"] = bool(charter_context.get("loaded_files"))
    analysis["model_meta"] = model_meta
    persist_analysis(config, analysis)

    artifact_files = [
        str(config.analysis_path.relative_to(config.git_root)),
        str(config.graph_path.relative_to(config.git_root)),
        str(config.roadmap_path.relative_to(config.git_root)),
    ]
    # Charter metadata exposed at top level for easy inspection
    charter_meta = {
        "loaded_files": charter_context.get("loaded_files", []),
        "content_hash": charter_context.get("content_hash"),
        "applied": charter_context.get("applied", False),
    }
    result: Dict[str, Any] = {
        "status": "analyzed",
        "mode": config.mode,
        "lane": "none",
        "lanes_active": list(config.campaign_lanes) if config.campaign_lanes else list(MUTATION_LANE_ORDER),
        "architecture_score": analysis["architecture_score"],
        "requested_model": model_meta.get("requested_model"),
        "actual_model": model_meta.get("actual_model"),
        "primary_model": model_meta.get("primary_model"),
        "fallback_model": model_meta.get("fallback_model"),
        "model_used": model_meta.get("model_used"),
        "fallback_used": model_meta.get("fallback_used", False),
        "fallback_reason": model_meta.get("fallback_reason"),
        "fallback_occurred": model_meta.get("fallback_occurred", False),
        "no_safe_code_mutation_reason": None,
        "branch": None,
        "changed_files": [],
        "validation": None,
        "pull_request_url": None,
        "artifact_files": artifact_files,
        "repo_root": str(config.git_root),
        "analysis_path": str(config.analysis_path),
        "graph_path": str(config.graph_path),
        "roadmap_path": str(config.roadmap_path),
        "roadmap": analysis["roadmap"],
        "github_models": model_meta,
        "charter": charter_meta,
        "metadata": {"architecture_score": analysis["architecture_score"], "model_meta": model_meta, "report_path": str(config.report_path)},
    }

    plan, lane, no_reason = build_patch_plan(config, analysis, model_meta, state)
    result["lane"] = lane
    result["no_safe_code_mutation_reason"] = no_reason
    if plan is not None:
        apply_result = apply_patch_plan(config, plan, state)
        result.update(apply_result)
        result["lane"] = lane
        result["no_safe_code_mutation_reason"] = no_reason
        artifact_files.extend(sorted(plan.file_changes.keys()))
    else:
        if config.mode == "analyze":
            result["status"] = "analysis_only"
        else:
            result["status"] = "no_safe_mutation_available"

    persist_manifest(config, artifact_files)
    result["artifact_files"] = artifact_files
    write_step_summary(config, result)

    state["runs"] = int(state.get("runs", 0)) + 1
    state["last_run_epoch"] = int(time.time())
    state["last_outcome"] = result["status"]
    state.setdefault("history", []).append({
        "ts": state["last_run_epoch"],
        "status": result["status"],
        "architecture_score": result["architecture_score"],
        "lane": result.get("lane"),
        "branch": result.get("branch"),
        "pull_request_url": result.get("pull_request_url"),
        "mode": config.mode,
    })
    state["history"] = state["history"][-100:]
    save_state(config, state)
    return result


# -----------------------------
# Campaign mode
# -----------------------------

def run_campaign(
    config: Config,
    lanes: Sequence[str],
    max_slices: int,
    stop_on_failure: bool,
) -> Dict[str, Any]:
    """Execute up to *max_slices* mutation slices in lane-priority order.

    Steps:
      1. Refresh analysis and model enrichment.
      2. For each lane in *lanes* (up to max_slices), attempt one slice.
      3. Re-analyse after each applied mutation so later lanes see current state.
      4. Emit a campaign summary artifact under .agent/campaign_summary.json.
    """
    ensure_agent_dir(config.agent_dir)
    state = load_state(config)
    analysis = build_analysis(config.git_root)
    charter_context = load_charter_context(config.git_root)
    analysis["charter_context"] = charter_context
    model_meta = enrich_with_github_models(config, analysis)
    if model_meta.get("used") or model_meta.get("enabled"):
        charter_context["applied"] = bool(charter_context.get("loaded_files"))
    analysis["model_meta"] = model_meta
    persist_analysis(config, analysis)

    slice_results: List[Dict[str, Any]] = []
    slices_applied = 0

    for lane in lanes:
        if slices_applied >= max_slices:
            break
        lane_config = dataclasses.replace(config, mode="mutate", campaign_lanes=(lane,))
        plan, selected_lane, no_reason = build_patch_plan(lane_config, analysis, model_meta, state)
        if plan is None:
            slice_results.append({"lane": lane, "status": "no_safe_mutation", "no_safe_code_mutation_reason": no_reason})
            continue
        try:
            apply_result = apply_patch_plan(lane_config, plan, state)
            apply_result["lane"] = selected_lane
            apply_result.setdefault("requested_model", model_meta.get("requested_model"))
            apply_result.setdefault("actual_model", model_meta.get("actual_model"))
            apply_result.setdefault("fallback_reason", model_meta.get("fallback_reason"))
            slice_results.append(apply_result)
            slices_applied += 1
            # Re-analyse so the next lane sees an up-to-date repo state
            analysis = build_analysis(config.git_root)
            analysis["charter_context"] = charter_context
            model_meta = enrich_with_github_models(config, analysis)
            analysis["model_meta"] = model_meta
        except RepoArchitectError as exc:
            slice_results.append({"lane": lane, "status": "failed", "error": str(exc)})
            if stop_on_failure:
                break

    charter_meta = {
        "loaded_files": charter_context.get("loaded_files", []),
        "content_hash": charter_context.get("content_hash"),
        "applied": charter_context.get("applied", False),
    }
    summary: Dict[str, Any] = {
        "mode": "campaign",
        "status": "campaign_complete",
        "slices_attempted": len(slice_results),
        "slices_applied": slices_applied,
        "lanes_requested": list(lanes),
        "lanes_executed": [r.get("lane") for r in slice_results],
        "architecture_score": analysis["architecture_score"],
        "requested_model": model_meta.get("requested_model"),
        "actual_model": model_meta.get("actual_model"),
        "primary_model": model_meta.get("primary_model"),
        "fallback_model": model_meta.get("fallback_model"),
        "model_used": model_meta.get("model_used"),
        "fallback_used": model_meta.get("fallback_used", False),
        "fallback_reason": model_meta.get("fallback_reason"),
        "charter": charter_meta,
        "results": slice_results,
    }

    campaign_summary_path = config.agent_dir / "campaign_summary.json"
    atomic_write_json(campaign_summary_path, summary)

    # Emit human-readable campaign report alongside the JSON artifact
    campaign_report_path = DEFAULT_REPORT_DIR / "campaign_report.md"
    atomic_write_text(config.git_root / campaign_report_path, _render_campaign_report(summary))

    state["runs"] = int(state.get("runs", 0)) + 1
    state["last_run_epoch"] = int(time.time())
    state["last_outcome"] = "campaign_complete"
    save_state(config, state)
    return summary


def _render_campaign_report(summary: Dict[str, Any]) -> str:
    """Render a human-readable markdown summary of a campaign run."""
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# repo-architect campaign report",
        "",
        f"Generated: {ts}",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Status | `{summary.get('status')}` |",
        f"| Architecture score | {summary.get('architecture_score')} |",
        f"| Slices attempted | {summary.get('slices_attempted')} |",
        f"| Slices applied | {summary.get('slices_applied')} |",
        f"| Lanes requested | {', '.join(summary.get('lanes_requested', []))} |",
        f"| Model requested | `{summary.get('requested_model') or 'n/a'}` |",
        f"| Model used | `{summary.get('actual_model') or 'n/a'}` |",
    ]
    if summary.get("fallback_reason"):
        lines.append(f"| Fallback reason | {summary['fallback_reason']} |")
    lines += ["", "## Slice results", ""]
    for idx, r in enumerate(summary.get("results", []), 1):
        status = r.get("status", "unknown")
        lane = r.get("lane", "?")
        branch = r.get("branch")
        pr = r.get("pull_request_url")
        err = r.get("error") or r.get("no_safe_code_mutation_reason")
        lines.append(f"### Slice {idx}: `{lane}` — {status}")
        lines.append("")
        if branch:
            lines.append(f"- Branch: `{branch}`")
        if pr:
            lines.append(f"- PR: {pr}")
        changed = r.get("changed_files", [])
        if changed:
            shown = changed[:10]
            truncated = len(changed) - len(shown)
            display = ', '.join(f'`{f}`' for f in shown)
            if truncated:
                display += f" … and {truncated} more"
            lines.append(f"- Changed: {display}")
        if err:
            lines.append(f"- Reason: {err}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# -----------------------------
# MCP server
# -----------------------------

def mcp_tool_schema() -> List[Dict[str, Any]]:
    return [
        {"name": "analyze_repo", "description": "Analyze repository structure and write reports under .agent/.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
        {"name": "build_code_graph", "description": "Return the local Python import graph.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
        {"name": "architecture_score", "description": "Return architecture score and factors.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
        {"name": "run_agent_cycle", "description": "Run one full slice.", "inputSchema": {"type": "object", "properties": {"mode": {"type": "string"}, "allow_dirty": {"type": "boolean"}}, "additionalProperties": False}},
    ]


def mcp_response(idv: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": idv, "result": result}


def mcp_error(idv: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": idv, "error": {"code": code, "message": message}}


def mcp_tool_result(payload: Any) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, sort_keys=True)}], "structuredContent": payload, "isError": False}


def run_mcp_server(config: Config) -> None:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        req = json.loads(line)
        rid = req.get("id")
        try:
            method = req.get("method")
            if method == "initialize":
                out = mcp_response(rid, {"protocolVersion": "2025-06-18", "serverInfo": {"name": APP_NAME, "version": VERSION}, "capabilities": {"tools": {"listChanged": False}}})
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                out = mcp_response(rid, {"tools": mcp_tool_schema()})
            elif method == "tools/call":
                params = req.get("params", {})
                name = params.get("name")
                args = params.get("arguments") or {}
                if name == "analyze_repo":
                    payload = build_analysis(config.git_root)
                elif name == "build_code_graph":
                    payload = build_analysis(config.git_root)["local_import_graph"]
                elif name == "architecture_score":
                    a = build_analysis(config.git_root)
                    payload = {"architecture_score": a["architecture_score"], "score_factors": a["score_factors"]}
                elif name == "run_agent_cycle":
                    local = dataclasses.replace(config, mode=args.get("mode", config.mode), allow_dirty=bool(args.get("allow_dirty", config.allow_dirty)))
                    payload = run_cycle(local)
                else:
                    raise RepoArchitectError(f"Unknown tool: {name}")
                out = mcp_response(rid, mcp_tool_result(payload))
            else:
                out = mcp_error(rid, -32601, f"Method not found: {method}")
        except Exception as exc:
            out = mcp_error(rid, -32000, str(exc))
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()


# -----------------------------
# CLI
# -----------------------------

def build_config(args: argparse.Namespace) -> Config:
    git_root = discover_git_root()
    agent_dir = git_root / AGENT_DIRNAME
    preferred = (
        args.preferred_model
        or os.environ.get("REPO_ARCHITECT_PREFERRED_MODEL")
        or DEFAULT_PREFERRED_MODEL
    )
    fallback = (
        args.fallback_model
        or os.environ.get("REPO_ARCHITECT_FALLBACK_MODEL")
        or DEFAULT_FALLBACK_MODEL
    )
    # Resolve lane order from --lane / --lanes / REPO_ARCHITECT_LANE / REPO_ARCHITECT_LANES env vars.
    # --lane (singular) is a convenience shortcut; --lanes takes comma-separated list.
    # Works for both mutate and campaign modes.
    lanes_raw = (
        args.lanes
        or (args.lane if getattr(args, "lane", None) else None)
        or os.environ.get("REPO_ARCHITECT_LANES")
        or os.environ.get("REPO_ARCHITECT_LANE")
    )
    campaign_lanes: Optional[Tuple[str, ...]] = None
    if lanes_raw:
        campaign_lanes = tuple(l.strip() for l in lanes_raw.split(",") if l.strip())
    issue_subsystem = args.issue_subsystem or os.environ.get("REPO_ARCHITECT_SUBSYSTEM")
    if issue_subsystem and issue_subsystem not in SUBSYSTEM_LABELS:
        raise RepoArchitectError(
            f"Invalid REPO_ARCHITECT_SUBSYSTEM={issue_subsystem!r}. "
            f"Expected one of: {', '.join(SUBSYSTEM_LABELS)}"
        )
    # Closed-loop execution / reconciliation options
    active_objective = (
        getattr(args, "active_objective", None)
        or os.environ.get("ACTIVE_OBJECTIVE")
        or os.environ.get("REPO_ARCHITECT_ACTIVE_OBJECTIVE")
    )
    if active_objective and active_objective not in OBJECTIVE_LABELS:
        raise RepoArchitectError(
            f"Invalid active_objective={active_objective!r}. "
            f"Expected one of: {', '.join(OBJECTIVE_LABELS)}"
        )
    lane_filter = (
        getattr(args, "lane_filter", None)
        or os.environ.get("LANE_FILTER")
        or os.environ.get("REPO_ARCHITECT_LANE_FILTER")
    )
    # ENABLE_LIVE_DELEGATION accepts "true"/"false" (canonical from workflow) or "1"/"0"/"yes"/"no"
    # for shell/env compatibility. Only "true"/"1"/"yes" enables live delegation.
    enable_live_delegation_raw = (
        os.environ.get("ENABLE_LIVE_DELEGATION", "").strip().lower()
        or ("true" if getattr(args, "enable_live_delegation", False) else "false")
    )
    _delegation_truthy = frozenset({"true", "1", "yes"})
    _delegation_falsy = frozenset({"false", "0", "no", ""})
    if enable_live_delegation_raw not in _delegation_truthy | _delegation_falsy:
        raise RepoArchitectError(
            f"Invalid ENABLE_LIVE_DELEGATION={enable_live_delegation_raw!r}. "
            f"Expected true or false."
        )
    enable_live_delegation = enable_live_delegation_raw in _delegation_truthy

    max_concurrent_raw = (
        os.environ.get("MAX_CONCURRENT_DELEGATED", "")
        or str(getattr(args, "max_concurrent_delegated", 1) or 1)
    )
    try:
        max_concurrent_delegated = int(max_concurrent_raw)
        if max_concurrent_delegated < 1:
            raise ValueError("must be >= 1")
    except (ValueError, TypeError):
        raise RepoArchitectError(
            f"Invalid MAX_CONCURRENT_DELEGATED={max_concurrent_raw!r}. Expected positive integer."
        )

    stale_raw = (
        os.environ.get("STALE_TIMEOUT_DAYS", "")
        or str(getattr(args, "stale_timeout_days", 14) or 14)
    )
    try:
        stale_timeout_days = int(stale_raw)
        if stale_timeout_days < 1:
            raise ValueError("must be >= 1")
    except (ValueError, TypeError):
        raise RepoArchitectError(
            f"Invalid STALE_TIMEOUT_DAYS={stale_raw!r}. Expected positive integer."
        )

    reconciliation_raw = (
        os.environ.get("RECONCILIATION_WINDOW_DAYS", "")
        or str(getattr(args, "reconciliation_window_days", 30) or 30)
    )
    try:
        reconciliation_window_days = int(reconciliation_raw)
        if reconciliation_window_days < 1:
            raise ValueError("must be >= 1")
    except (ValueError, TypeError):
        raise RepoArchitectError(
            f"Invalid RECONCILIATION_WINDOW_DAYS={reconciliation_raw!r}. Expected positive integer."
        )

    return Config(
        git_root=git_root,
        agent_dir=agent_dir,
        state_path=agent_dir / STATE_FILE,
        analysis_path=agent_dir / ANALYSIS_FILE,
        graph_path=agent_dir / GRAPH_FILE,
        roadmap_path=agent_dir / ROADMAP_FILE,
        artifact_manifest_path=agent_dir / ARTIFACT_MANIFEST_FILE,
        workflow_path=git_root / WORKFLOW_PATH,
        step_summary_path=pathlib.Path(os.environ["GITHUB_STEP_SUMMARY"]) if os.environ.get("GITHUB_STEP_SUMMARY") else None,
        github_token=os.environ.get("GITHUB_TOKEN"),
        github_repo=os.environ.get("GITHUB_REPO"),
        github_base_branch=os.environ.get("GITHUB_BASE_BRANCH"),
        github_admin_token=os.environ.get("GITHUB_ADMIN_TOKEN"),
        github_model=args.github_model or os.environ.get("GITHUB_MODEL"),
        allow_dirty=args.allow_dirty,
        mode=args.mode,
        interval=args.interval,
        log_json=args.log_json,
        report_path=git_root / args.report_path,
        mutation_budget=args.mutation_budget,
        configure_branch_protection=args.configure_branch_protection,
        preferred_model=preferred,
        fallback_model=fallback,
        github_fallback_model=os.environ.get("GITHUB_FALLBACK_MODEL"),
        campaign_lanes=campaign_lanes,
        dry_run=args.dry_run,
        max_issues=args.max_issues,
        issue_subsystem=issue_subsystem,
        enable_live_delegation=enable_live_delegation,
        max_concurrent_delegated=max_concurrent_delegated,
        active_objective=active_objective,
        lane_filter=lane_filter,
        stale_timeout_days=stale_timeout_days,
        reconciliation_window_days=reconciliation_window_days,
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="repo-architect: architectural governance via GitHub Issues. "
        "Inspects the repository, diagnoses gaps, and opens structured GitHub Issues "
        "with Copilot-ready implementation prompts.",
    )
    p.add_argument(
        "--mode",
        choices=["analyze", "report", "issue", "mutate", "campaign", "execution", "reconcile"],
        default="issue",
        help=(
            "Operating mode. 'issue' (default) is the safe governance mode: detects architectural gaps and "
            "opens/updates GitHub Issues. 'execution' selects one ready issue and delegates it to Copilot. "
            "'reconcile' ingests PR outcomes back into work state. "
            "'analyze'/'report' are read-only. "
            "'mutate'/'campaign' are charter-validated secondary modes that perform "
            "narrow, validated code mutations per GODELOS_REPO_IMPLEMENTATION_CHARTER §9–§10."
        ),
    )
    p.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    p.add_argument("--mutation-budget", type=int, default=1)
    p.add_argument("--allow-dirty", action="store_true")
    p.add_argument("--mcp", action="store_true")
    p.add_argument("--daemon", action="store_true")
    p.add_argument("--interval", type=int, default=3600)
    p.add_argument("--install-gh-workflow", action="store_true")
    p.add_argument("--workflow-cron", default="17 * * * *")
    p.add_argument("--workflow-secret-env", nargs="*", default=[])
    p.add_argument("--configure-branch-protection", action="store_true")
    p.add_argument("--github-model", default=None, help="Override active model (backward compat)")
    p.add_argument("--preferred-model", default=None, help="Preferred GitHub Models model id")
    p.add_argument("--fallback-model", default=None, help="Fallback model if preferred is unavailable")
    p.add_argument("--log-json", action="store_true")
    # Lane / campaign args (charter-validated secondary modes §9–§10)
    p.add_argument("--lane", default=None, help="Single lane to run in mutate mode (convenience alias for --lanes)")
    p.add_argument("--max-slices", type=int, default=3, help="Campaign: max mutation slices to attempt")
    p.add_argument("--lanes", default=None, help="Comma-separated lane order for mutate/campaign modes")
    p.add_argument("--stop-on-failure", action="store_true", help="Campaign: stop on first slice failure")
    # Issue-first mode args
    p.add_argument("--dry-run", action="store_true",
                   help="Issue mode: write issue bodies to disk but do not call the GitHub Issues API.")
    p.add_argument("--max-issues", type=int, default=1,
                   help="Issue mode: maximum number of issues to open/update per run (default: 1).")
    p.add_argument("--issue-subsystem", default=None,
                   choices=SUBSYSTEM_LABELS,
                   help="Issue mode: restrict gap detection to a specific subsystem.")
    # Closed-loop execution / reconciliation operator controls
    p.add_argument("--enable-live-delegation", action="store_true",
                   help="Execution mode: actually delegate to Copilot via GitHub API (default: dry-run only).")
    p.add_argument("--max-concurrent-delegated", type=int, default=1,
                   help="Execution mode: max number of issues simultaneously in-flight (default: 1).")
    p.add_argument("--active-objective", default=None,
                   help=f"Execution mode: restrict selection to a specific objective. "
                        f"Valid values: {', '.join(OBJECTIVE_LABELS)}.")
    p.add_argument("--lane-filter", default=None,
                   help="Execution mode: restrict issue selection to a specific charter lane name.")
    p.add_argument("--stale-timeout-days", type=int, default=14,
                   help="Reconciliation: days before a delegated-but-PR-less item is marked stale (default: 14).")
    p.add_argument("--reconciliation-window-days", type=int, default=30,
                   help="Reconciliation: days of PRs to consider during reconciliation (default: 30).")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        config = build_config(args)
        os.chdir(config.git_root)

        if args.install_gh_workflow:
            path = install_workflow(config, args.workflow_secret_env, args.workflow_cron)
            log("Installed GitHub Actions workflow", data={
                "workflow_path": str(path),
                "runner": "GitHub-hosted runner via runs-on: ubuntu-latest",
                "mode": "scheduled + workflow_dispatch",
                "extra_secret_env": args.workflow_secret_env,
                "github_model_env": config.github_model,
                "github_models_permissions": "models: read",
            }, json_mode=config.log_json)
            return 0

        if config.configure_branch_protection:
            payload = set_branch_protection(config)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0

        if args.mcp:
            run_mcp_server(config)
            return 0

        if args.daemon:
            log(
                "Starting daemon mode",
                data={"where": str(config.git_root), "host": "current machine or CI runner process", "interval_seconds": config.interval, "mode": config.mode},
                json_mode=config.log_json,
            )
            while True:
                try:
                    if config.mode == ISSUE_MODE:
                        res = run_issue_cycle(config)
                    else:
                        res = run_cycle(config)
                    log("Cycle complete", data=res, json_mode=config.log_json)
                except Exception as exc:
                    log("Cycle failed", data={"error": str(exc), "trace": traceback.format_exc()}, json_mode=config.log_json)
                time.sleep(config.interval)
            return 0

        # Issue-first mode (new primary mode)
        if config.mode == ISSUE_MODE:
            result = run_issue_cycle(config)
            # Emit human-readable summary to stderr
            for line in result.get("summary", []):
                log(line, json_mode=config.log_json)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        # Execution lane — select one ready issue and delegate to Copilot
        if config.mode == EXECUTION_MODE:
            result = run_execution_cycle(config)
            for line in result.get("summary", []):
                log(line, json_mode=config.log_json)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        # Reconciliation lane — ingest PR outcomes back into work state
        if config.mode == RECONCILE_MODE:
            result = run_reconciliation_cycle(config)
            for line in result.get("summary", []):
                log(line, json_mode=config.log_json)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        # Charter-validated campaign mode (secondary — requires explicit opt-in)
        if config.mode == "campaign":
            log(
                "ℹ️  'campaign' mode performs direct code mutation via charter-validated lanes "
                "(§9–§10 GODELOS_REPO_IMPLEMENTATION_CHARTER).  "
                "The default safe operating mode is --mode issue.",
                json_mode=config.log_json,
            )
            lanes_arg = list(config.campaign_lanes) if config.campaign_lanes else list(MUTATION_LANE_ORDER)
            result = run_campaign(config, lanes_arg, args.max_slices, args.stop_on_failure)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        result = run_cycle(config)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except RepoArchitectError as exc:
        log("Fatal error", data={"error": str(exc)}, json_mode=args.log_json)
        return 2
    except Exception as exc:
        log("Unhandled error", data={"error": str(exc), "trace": traceback.format_exc()}, json_mode=args.log_json)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
