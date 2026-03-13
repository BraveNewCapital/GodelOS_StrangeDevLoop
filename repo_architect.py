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
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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
DEFAULT_PREFERRED_MODEL = "openai/gpt-5.4"
DEFAULT_FALLBACK_MODEL = "openai/gpt-4.1"
# Substrings in HTTP error bodies that indicate the model itself is unavailable (not a transient error)
_MODEL_UNAVAILABLE_SIGNALS = frozenset({
    "unknown_model", "model_not_found", "unsupported_model", "unsupported model",
    "not found", "does not exist", "invalid model", "no such model",
})
# Canonical lane execution order for mutate / campaign modes
MUTATION_LANE_ORDER: Tuple[str, ...] = ("parse_errors", "import_cycles", "entrypoint_consolidation", "hygiene", "report")
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
    # Explicit lane order override (None = use MUTATION_LANE_ORDER)
    campaign_lanes: Optional[Tuple[str, ...]] = None


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
        if fallback and fallback != preferred and _is_model_unavailable_error(reason):
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
# Models enrichment
# -----------------------------

def enrich_with_github_models(config: Config, analysis: Dict[str, Any]) -> Dict[str, Any]:
    preferred = config.preferred_model or config.github_model
    fallback = config.fallback_model
    meta: Dict[str, Any] = {
        "enabled": False,
        "used": False,
        "requested_model": preferred,
        "actual_model": None,
        "model": preferred,  # kept for backward compatibility
        "summary": None,
        "fallback_reason": None,
        "fallback_occurred": False,
    }
    if not config.github_token or not preferred:
        return meta
    meta["enabled"] = True
    prompt = textwrap.dedent(f"""
    You are summarizing repository architecture risk.
    Architecture score: {analysis['architecture_score']}
    Local import cycles: {len(analysis['cycles'])}
    Parse error files: {len(analysis['parse_error_files'])}
    Entrypoints: {len(analysis['entrypoint_paths'])}
    Top roadmap items: {json.dumps(analysis['roadmap'][:5])}

    Return 5 bullet points, compact and concrete, no preamble.
    """).strip()
    resp, requested, fallback_reason, fallback_occurred = call_models_with_fallback_or_none(
        config.github_token, preferred, fallback,
        [
            {"role": "system", "content": "You produce concise engineering prioritization notes."},
            {"role": "user", "content": prompt},
        ],
    )
    meta["fallback_reason"] = fallback_reason
    meta["fallback_occurred"] = fallback_occurred
    if resp is None:
        return meta
    try:
        meta["summary"] = parse_model_text(resp)
        meta["actual_model"] = resp.get("model", fallback if fallback_occurred else preferred)
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
    summary = [
        f"# {APP_NAME} run summary",
        "",
        f"- mode: `{result.get('mode', config.mode)}`",
        f"- status: `{result.get('status')}`",
        f"- lane: `{result.get('lane', 'none')}`",
        f"- architecture score: **{result.get('architecture_score')}**",
        f"- changed files: `{len(result.get('changed_files', []))}`",
    ]
    if result.get("pull_request_url"):
        summary.append(f"- pull request: {result['pull_request_url']}")
    if result.get("branch"):
        summary.append(f"- branch: `{result['branch']}`")
    if result.get("requested_model"):
        summary.append(f"- model requested: `{result['requested_model']}`")
    if result.get("actual_model"):
        summary.append(f"- model used: `{result['actual_model']}`")
    if result.get("fallback_occurred"):
        summary.append(f"- ⚠️ fallback occurred: {result.get('fallback_reason', '')}")
    if result.get("no_safe_code_mutation_reason"):
        summary.append(f"- no safe mutation: {result['no_safe_code_mutation_reason']}")
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


def persist_analysis(config: Config, analysis: Dict[str, Any]) -> None:
    atomic_write_json(config.analysis_path, analysis)
    atomic_write_json(config.graph_path, analysis.get("local_import_graph", {}))
    atomic_write_json(config.roadmap_path, {"roadmap": analysis.get("roadmap", [])})


def baseline_dirty_guard(config: Config) -> None:
    if config.allow_dirty:
        return
    if git_is_dirty(config.git_root):
        raise RepoArchitectError("Repository has uncommitted changes. Re-run with --allow-dirty if you really want mutation.")


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
    preferred = config.preferred_model or config.github_model
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
            {"role": "system", "content": "You fix Python syntax errors. Return only valid JSON with corrected file contents."},
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
    preferred = config.preferred_model or config.github_model
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
            {"role": "system", "content": "You fix Python import cycles. Return only valid JSON with corrected file contents."},
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
    preferred = config.preferred_model or config.github_model
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
            {"role": "system", "content": "You annotate redundant Python entrypoints with deprecation comments. Return only valid JSON."},
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
    """
    if config.mode == "analyze":
        return None, "none", None

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
        description: 'GitHub Models model id (overrides preferred model)'
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

      - name: Run repo architect
        env:
          GITHUB_TOKEN: ${{{{ github.token }}}}
          GITHUB_REPO: ${{{{ github.repository }}}}
          GITHUB_BASE_BRANCH: ${{{{ github.event.repository.default_branch }}}}
          REPO_ARCHITECT_BRANCH_SUFFIX: ${{{{ github.run_id }}}}-${{{{ github.run_attempt }}}}
          REPO_ARCHITECT_PREFERRED_MODEL: openai/gpt-5.4
          REPO_ARCHITECT_FALLBACK_MODEL: openai/gpt-4.1
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
    ensure_agent_dir(config.agent_dir)
    state = load_state(config)
    analysis = build_analysis(config.git_root)
    model_meta = enrich_with_github_models(config, analysis)
    analysis["model_meta"] = model_meta
    persist_analysis(config, analysis)

    artifact_files = [
        str(config.analysis_path.relative_to(config.git_root)),
        str(config.graph_path.relative_to(config.git_root)),
        str(config.roadmap_path.relative_to(config.git_root)),
    ]
    result: Dict[str, Any] = {
        "status": "analyzed",
        "mode": config.mode,
        "lane": "none",
        "lanes_active": list(config.campaign_lanes) if config.campaign_lanes else list(MUTATION_LANE_ORDER),
        "architecture_score": analysis["architecture_score"],
        "requested_model": model_meta.get("requested_model"),
        "actual_model": model_meta.get("actual_model"),
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
    model_meta = enrich_with_github_models(config, analysis)
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
            model_meta = enrich_with_github_models(config, analysis)
            analysis["model_meta"] = model_meta
        except RepoArchitectError as exc:
            slice_results.append({"lane": lane, "status": "failed", "error": str(exc)})
            if stop_on_failure:
                break

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
        "fallback_reason": model_meta.get("fallback_reason"),
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
        campaign_lanes=campaign_lanes,
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Single-file repo architect, PR bot, and MCP server.")
    p.add_argument("--mode", choices=["analyze", "report", "mutate", "campaign"], default="report")
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
    # Lane / campaign args
    p.add_argument("--lane", default=None, help="Single lane to run in mutate mode (convenience alias for --lanes)")
    p.add_argument("--max-slices", type=int, default=3, help="Campaign: max mutation slices to attempt")
    p.add_argument("--lanes", default=None, help="Comma-separated lane order for mutate/campaign modes")
    p.add_argument("--stop-on-failure", action="store_true", help="Campaign: stop on first slice failure")
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
            log("Starting daemon mode", data={"where": str(config.git_root), "host": "current machine or CI runner process", "interval_seconds": config.interval}, json_mode=config.log_json)
            while True:
                try:
                    res = run_cycle(config)
                    log("Cycle complete", data=res, json_mode=config.log_json)
                except Exception as exc:
                    log("Cycle failed", data={"error": str(exc), "trace": traceback.format_exc()}, json_mode=config.log_json)
                time.sleep(config.interval)
            return 0

        if config.mode == "campaign":
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
