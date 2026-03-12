#!/usr/bin/env python3
"""
repo_architect.py

Single-file, standard-library-only repository architect, safe PR generator,
and stdio MCP server.

Operational posture:
- Default mode performs a deterministic analysis pass, writes .agent artifacts,
  and then attempts one conservative change in this order:
    1. remove explicitly marked Python debug prints (# DEBUG / # DBG)
    2. generate / refresh a documentation report PR under docs/repo_architect/
- Optional GitHub Models enrichment uses GitHub credentials and gracefully
  falls back to static mode on policy, catalog, or inference errors.
- Optional GitHub Actions workflow generation targets GitHub-hosted runners,
  uploads artifacts, supports workflow_dispatch inputs, and uses concurrency.
- Optional branch-protection bootstrap exists, but requires admin-level token.

Modes:
    python repo_architect.py
    python repo_architect.py --mode analyze
    python repo_architect.py --mode report
    python repo_architect.py --mode mutate
    python repo_architect.py --mcp
    python repo_architect.py --install-gh-workflow
    python repo_architect.py --configure-branch-protection
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
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


VERSION = "1.2.0"
APP_NAME = "repo-architect"
AGENT_DIRNAME = ".agent"
STATE_FILE = "repo_architect_state.json"
ANALYSIS_FILE = "latest_analysis.json"
GRAPH_FILE = "code_graph.json"
ROADMAP_FILE = "roadmap.json"
ARTIFACT_MANIFEST_FILE = "artifacts_manifest.json"
WORKFLOW_PATH = pathlib.Path(".github/workflows/repo-architect.yml")
DEFAULT_REPORT_PATH = "docs/repo_architect/runtime_inventory.md"
DEFAULT_IGNORE_DIRS = {
    ".git",
    AGENT_DIRNAME,
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".next",
    ".turbo",
    ".idea",
    ".vscode",
}
DEBUG_MARKER_RE = re.compile(r"#\s*(DEBUG|debug|DBG)\b")
PRINT_RE = re.compile(r"\bprint\s*\(")
GITHUB_API_VERSION = "2026-03-10"
GITHUB_MODELS_CATALOG = "https://models.github.ai/catalog/models"
GITHUB_MODELS_GLOBAL_CHAT = "https://models.github.ai/inference/chat/completions"


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
    github_token: Optional[str]
    github_repo: Optional[str]
    github_base_branch: Optional[str]
    github_admin_token: Optional[str]
    allow_dirty: bool
    mode: str
    interval: int
    log_json: bool
    validate_cmd: Optional[str]
    github_model: Optional[str]
    report_path: pathlib.Path
    mutation_budget: int


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


# -----------------------------
# Generic helpers
# -----------------------------

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


def atomic_write_json(path: pathlib.Path, payload: Dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def read_json(path: pathlib.Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def run_cmd(
    cmd: Sequence[str],
    *,
    cwd: pathlib.Path,
    check: bool = True,
    capture: bool = True,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        list(cmd),
        cwd=str(cwd),
        env=merged_env,
        check=check,
        text=True,
        capture_output=capture,
    )


def run_shell(cmd: str, *, cwd: pathlib.Path, check: bool = True, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        shell=True,
        text=True,
        capture_output=True,
        check=check,
        env=merged_env,
    )


def discover_git_root() -> pathlib.Path:
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], text=True, capture_output=True)
    if proc.returncode != 0:
        raise RepoArchitectError("Not inside a git repository.")
    return pathlib.Path(proc.stdout.strip()).resolve()


def parse_owner_repo(github_repo: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not github_repo or "/" not in github_repo:
        return None, None
    owner, repo = github_repo.split("/", 1)
    return owner, repo


# -----------------------------
# Git helpers
# -----------------------------

def git_current_branch(root: pathlib.Path) -> str:
    proc = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    return proc.stdout.strip()


def git_head_sha(root: pathlib.Path) -> str:
    proc = run_cmd(["git", "rev-parse", "HEAD"], cwd=root)
    return proc.stdout.strip()


def git_is_dirty(root: pathlib.Path) -> bool:
    proc = run_cmd(["git", "status", "--porcelain"], cwd=root)
    return bool(proc.stdout.strip())


def git_has_remote_origin(root: pathlib.Path) -> bool:
    proc = subprocess.run(["git", "remote", "get-url", "origin"], cwd=str(root), text=True, capture_output=True)
    return proc.returncode == 0 and bool(proc.stdout.strip())


def git_checkout_new_branch(root: pathlib.Path, branch: str) -> None:
    run_cmd(["git", "checkout", "-b", branch], cwd=root)


def git_checkout(root: pathlib.Path, branch: str) -> None:
    run_cmd(["git", "checkout", branch], cwd=root)


def git_delete_branch(root: pathlib.Path, branch: str) -> None:
    subprocess.run(["git", "branch", "-D", branch], cwd=str(root), text=True, capture_output=True)


def git_stage_and_commit(root: pathlib.Path, paths: Sequence[str], message: str) -> None:
    run_cmd(["git", "add", *paths], cwd=root)
    run_cmd(["git", "commit", "-m", message], cwd=root)


def git_push_branch(root: pathlib.Path, branch: str) -> None:
    run_cmd(["git", "push", "-u", "origin", branch], cwd=root)


def safe_branch_name(task: str, reason: str) -> str:
    core = re.sub(r"[^a-zA-Z0-9._-]+", "-", f"{task}-{reason}".lower()).strip("-")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return f"agent/{stamp}/{core[:48]}"


# -----------------------------
# Python repo analysis
# -----------------------------

def iter_python_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        current = pathlib.Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORE_DIRS]
        for filename in filenames:
            if filename.endswith(".py"):
                yield current / filename


def to_posix_relative(root: pathlib.Path, path: pathlib.Path) -> str:
    return path.relative_to(root).as_posix()


def module_name_for_path(root: pathlib.Path, path: pathlib.Path) -> str:
    rel = path.relative_to(root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join([p for p in parts if p])


def build_module_maps(root: pathlib.Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    module_to_file: Dict[str, str] = {}
    file_to_module: Dict[str, str] = {}
    for path in iter_python_files(root):
        rel = to_posix_relative(root, path)
        mod = module_name_for_path(root, path)
        file_to_module[rel] = mod
        if mod:
            module_to_file[mod] = rel
    return module_to_file, file_to_module


def _resolve_relative_module(current_module: str, level: int, module: Optional[str]) -> str:
    base = current_module.split(".") if current_module else []
    if level > len(base):
        base = []
    else:
        base = base[:-level]
    if module:
        base.extend(module.split("."))
    return ".".join([p for p in base if p])


def analyze_python_file(root: pathlib.Path, path: pathlib.Path, module_to_file: Dict[str, str]) -> PyFileInfo:
    rel = to_posix_relative(root, path)
    module = module_name_for_path(root, path)
    text = path.read_text(encoding="utf-8", errors="replace")
    imports: List[str] = []
    local_imports: List[str] = []
    entrypoint = False
    debug_print_lines: List[int] = []

    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        if PRINT_RE.search(line) and DEBUG_MARKER_RE.search(line):
            debug_print_lines.append(idx)

    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        return PyFileInfo(
            path=rel,
            module=module,
            imports=imports,
            local_imports=local_imports,
            entrypoint=entrypoint,
            debug_print_lines=debug_print_lines,
            parse_error=f"{exc.__class__.__name__}: {exc}",
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                imports.append(name)
                if name in module_to_file:
                    local_imports.append(name)
        elif isinstance(node, ast.ImportFrom):
            target_module = _resolve_relative_module(module, node.level, node.module)
            if target_module:
                imports.append(target_module)
                if target_module in module_to_file:
                    local_imports.append(target_module)
            for alias in node.names:
                candidate = f"{target_module}.{alias.name}" if target_module else alias.name
                if candidate in module_to_file and candidate not in local_imports:
                    local_imports.append(candidate)
        elif isinstance(node, ast.If):
            try:
                test = ast.unparse(node.test)
            except Exception:
                test = ""
            compact = test.replace(" ", "")
            if compact == "__name__=='__main__'" or compact == '__name__=="__main__"':
                entrypoint = True

    return PyFileInfo(
        path=rel,
        module=module,
        imports=sorted(set(imports)),
        local_imports=sorted(set(local_imports)),
        entrypoint=entrypoint,
        debug_print_lines=debug_print_lines,
        parse_error=None,
    )


def find_cycles(graph: Dict[str, List[str]]) -> List[List[str]]:
    cycles: List[List[str]] = []
    state: Dict[str, int] = {}
    stack: List[str] = []
    seen: set[Tuple[str, ...]] = set()

    def visit(node: str) -> None:
        mark = state.get(node, 0)
        if mark == 1:
            if node in stack:
                idx = stack.index(node)
                cycle = stack[idx:] + [node]
                key = tuple(cycle)
                if key not in seen:
                    seen.add(key)
                    cycles.append(cycle)
            return
        if mark == 2:
            return
        state[node] = 1
        stack.append(node)
        for nxt in graph.get(node, []):
            visit(nxt)
        stack.pop()
        state[node] = 2

    for node in graph:
        visit(node)
    return cycles


def architecture_score(py_infos: List[PyFileInfo], cycles: List[List[str]]) -> Tuple[int, Dict[str, Any]]:
    py_count = len(py_infos)
    entrypoints = sum(1 for p in py_infos if p.entrypoint)
    debug_prints = sum(len(p.debug_print_lines) for p in py_infos)
    parse_errors = sum(1 for p in py_infos if p.parse_error)
    score = 100
    score -= min(len(cycles) * 8, 40)
    score -= min(max(entrypoints - 1, 0) * 3, 18)
    score -= min(debug_prints * 2, 20)
    score -= min(parse_errors * 4, 12)
    return max(score, 0), {
        "python_files": py_count,
        "cycles": len(cycles),
        "entrypoints": entrypoints,
        "debug_print_markers": debug_prints,
        "parse_errors": parse_errors,
    }


def summarize_entrypoints(py_infos: List[PyFileInfo]) -> List[str]:
    return [p.path for p in py_infos if p.entrypoint]


def synthesize_roadmap(py_infos: List[PyFileInfo], cycles: List[List[str]], score: int) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    debug_targets = [p.path for p in py_infos if p.debug_print_lines]
    if debug_targets:
        tasks.append({
            "name": "remove_marked_debug_prints",
            "priority": 100,
            "actionable": True,
            "summary": f"Remove explicitly marked debug prints from {len(debug_targets)} Python file(s).",
            "targets": debug_targets,
        })
    if cycles:
        tasks.append({
            "name": "review_circular_dependencies",
            "priority": 80,
            "actionable": False,
            "summary": f"Review {len(cycles)} local import cycle(s).",
            "targets": cycles,
        })
    entrypoints = summarize_entrypoints(py_infos)
    if len(entrypoints) > 1:
        tasks.append({
            "name": "review_multiple_entrypoints",
            "priority": 60,
            "actionable": False,
            "summary": f"Review {len(entrypoints)} Python entrypoints for runtime duplication.",
            "targets": entrypoints,
        })
    parse_error_files = [p.path for p in py_infos if p.parse_error]
    if parse_error_files:
        tasks.append({
            "name": "review_parse_errors",
            "priority": 70,
            "actionable": False,
            "summary": f"Review syntax/parse issues in {len(parse_error_files)} file(s).",
            "targets": parse_error_files,
        })
    tasks.append({
        "name": "publish_runtime_inventory_report",
        "priority": 50,
        "actionable": True,
        "summary": "Generate or refresh repository architecture inventory documentation.",
        "targets": [DEFAULT_REPORT_PATH],
    })
    return sorted(tasks, key=lambda t: (-int(t["priority"]), t["name"]))


def build_analysis(root: pathlib.Path) -> Dict[str, Any]:
    module_to_file, _ = build_module_maps(root)
    py_infos = [analyze_python_file(root, p, module_to_file) for p in iter_python_files(root)]
    py_infos.sort(key=lambda p: p.path)
    graph = {info.module: info.local_imports for info in py_infos if info.module}
    cycles = find_cycles(graph)
    score, factors = architecture_score(py_infos, cycles)
    roadmap = synthesize_roadmap(py_infos, cycles, score)
    entrypoints = summarize_entrypoints(py_infos)
    parse_errors = {p.path: p.parse_error for p in py_infos if p.parse_error}
    debug_files = {p.path: p.debug_print_lines for p in py_infos if p.debug_print_lines}
    return {
        "version": VERSION,
        "generated_at_epoch": int(time.time()),
        "repo_root": str(root),
        "architecture_score": score,
        "score_factors": factors,
        "entrypoints": entrypoints,
        "parse_errors": parse_errors,
        "debug_print_targets": debug_files,
        "python_files": [dataclasses.asdict(info) for info in py_infos],
        "local_import_graph": graph,
        "cycles": cycles,
        "roadmap": roadmap,
    }


# -----------------------------
# GitHub Models helpers
# -----------------------------

def github_request_raw(url: str, token: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Tuple[int, str]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        method=method,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": APP_NAME,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.getcode(), resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body


def github_api_request(token: str, path: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    code, body = github_request_raw(f"https://api.github.com{path}", token, method=method, payload=payload)
    if 200 <= code < 300:
        return json.loads(body) if body else {}
    raise RepoArchitectError(f"GitHub API {method} {path} failed: {code} {body}")


def github_models_catalog(token: str) -> Tuple[List[str], Optional[str]]:
    code, body = github_request_raw(GITHUB_MODELS_CATALOG, token, method="GET")
    if code != 200:
        return [], f"catalog_request_failed:{code}"
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return [], "catalog_decode_failed"
    models: List[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                mid = item.get("id") or item.get("model") or item.get("name")
                if isinstance(mid, str):
                    models.append(mid)
    elif isinstance(data, dict):
        items = data.get("models") or data.get("data") or []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    mid = item.get("id") or item.get("model") or item.get("name")
                    if isinstance(mid, str):
                        models.append(mid)
    return sorted(set(models)), None


def github_models_chat_endpoint(config: Config) -> str:
    owner, _ = parse_owner_repo(config.github_repo)
    if owner:
        return f"https://models.github.ai/orgs/{urllib.parse.quote(owner)}/inference/chat/completions"
    return GITHUB_MODELS_GLOBAL_CHAT


def maybe_github_models_summary(config: Config, analysis: Dict[str, Any]) -> Dict[str, Any]:
    model = config.github_model
    token = config.github_token
    if not model or not token:
        return {"enabled": False, "used": False, "reason": "no_model_or_token"}

    catalog, catalog_error = github_models_catalog(token)
    if catalog_error:
        return {"enabled": True, "used": False, "reason": catalog_error}
    if model not in catalog:
        return {
            "enabled": True,
            "used": False,
            "reason": "model_not_in_catalog",
            "requested_model": model,
            "catalog_sample": catalog[:25],
        }

    prompt = textwrap.dedent(
        f"""
        You are assisting with repository triage.
        Summarize the highest-leverage next engineering actions from this analysis in 6 bullet points or fewer.
        Be concrete. Mention only actions supported by the supplied facts.
        Analysis facts:
        - architecture_score: {analysis.get('architecture_score')}
        - cycles: {len(analysis.get('cycles', []))}
        - parse_errors: {len(analysis.get('parse_errors', {}))}
        - entrypoints: {len(analysis.get('entrypoints', []))}
        - top roadmap item: {analysis.get('roadmap', [{}])[0].get('summary', '')}
        """
    ).strip()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You produce terse engineering summaries grounded in provided facts."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    endpoint = github_models_chat_endpoint(config)
    code, body = github_request_raw(endpoint, token, method="POST", payload=payload)
    if code != 200:
        return {
            "enabled": True,
            "used": False,
            "reason": f"inference_failed:{code}",
            "requested_model": model,
            "response_body": body[:1000],
        }
    try:
        data = json.loads(body)
        choices = data.get("choices") or []
        text = ""
        if choices:
            message = choices[0].get("message") or {}
            text = message.get("content") or ""
        return {
            "enabled": True,
            "used": bool(text.strip()),
            "model": model,
            "summary": text.strip(),
        }
    except Exception:
        return {
            "enabled": True,
            "used": False,
            "reason": "inference_decode_failed",
            "requested_model": model,
            "response_body": body[:1000],
        }


# -----------------------------
# Analysis persistence and report generation
# -----------------------------

def ensure_agent_dir(path: pathlib.Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_state(config: Config) -> Dict[str, Any]:
    default = {"version": VERSION, "runs": 0, "last_run_epoch": None, "history": []}
    return read_json(config.state_path, default)


def save_state(config: Config, state: Dict[str, Any]) -> None:
    atomic_write_json(config.state_path, state)


def write_artifact_manifest(config: Config, additional_paths: Optional[Sequence[pathlib.Path]] = None) -> List[str]:
    files = [config.analysis_path, config.graph_path, config.roadmap_path, config.state_path]
    if additional_paths:
        files.extend(additional_paths)
    rels = []
    for path in files:
        if path.exists():
            rels.append(to_posix_relative(config.git_root, path))
    atomic_write_json(config.artifact_manifest_path, {"artifacts": rels})
    return rels


def persist_analysis(config: Config, analysis: Dict[str, Any]) -> None:
    atomic_write_json(config.analysis_path, analysis)
    atomic_write_json(config.graph_path, analysis.get("local_import_graph", {}))
    atomic_write_json(config.roadmap_path, {"roadmap": analysis.get("roadmap", [])})


def render_runtime_inventory(config: Config, analysis: Dict[str, Any], ai_meta: Dict[str, Any]) -> str:
    entrypoints = analysis.get("entrypoints", [])
    cycles = analysis.get("cycles", [])
    parse_errors = analysis.get("parse_errors", {})
    roadmap = analysis.get("roadmap", [])
    factors = analysis.get("score_factors", {})
    debug_targets = analysis.get("debug_print_targets", {})
    commit = git_head_sha(config.git_root)

    def bullet_list(items: Sequence[str], limit: int = 40) -> str:
        if not items:
            return "- None\n"
        rows = [f"- `{item}`" for item in list(items)[:limit]]
        if len(items) > limit:
            rows.append(f"- ... and {len(items) - limit} more")
        return "\n".join(rows) + "\n"

    cycle_lines: List[str] = []
    for cycle in cycles[:20]:
        if isinstance(cycle, list):
            cycle_lines.append("- `" + " -> ".join(cycle) + "`")
    if len(cycles) > 20:
        cycle_lines.append(f"- ... and {len(cycles) - 20} more")
    cycles_section = "\n".join(cycle_lines) + ("\n" if cycle_lines else "- None\n")

    parse_lines = [f"- `{path}`: {msg}" for path, msg in list(parse_errors.items())[:20]]
    if len(parse_errors) > 20:
        parse_lines.append(f"- ... and {len(parse_errors) - 20} more")
    parse_section = "\n".join(parse_lines) + ("\n" if parse_lines else "- None\n")

    roadmap_lines = [f"- **{item['name']}** ({item['priority']}): {item['summary']}" for item in roadmap[:10]]
    roadmap_section = "\n".join(roadmap_lines) + ("\n" if roadmap_lines else "- None\n")

    ai_section = ""
    if ai_meta.get("used") and ai_meta.get("summary"):
        ai_section = f"## AI triage summary\n\n{ai_meta['summary']}\n\n"
    elif ai_meta.get("enabled"):
        ai_section = (
            "## AI triage summary\n\n"
            f"Unavailable in this run. Reason: `{ai_meta.get('reason', 'unknown')}`.\n\n"
        )

    text = f"""# Runtime inventory\n\n"""
    text += f"Generated from commit `{commit}`. This file is intended to be deterministic and safe for review.\n\n"
    text += "## Architecture score\n\n"
    text += f"- Score: **{analysis.get('architecture_score')}**\n"
    text += f"- Python files: **{factors.get('python_files', 0)}**\n"
    text += f"- Entry points: **{factors.get('entrypoints', 0)}**\n"
    text += f"- Local import cycles: **{factors.get('cycles', 0)}**\n"
    text += f"- Parse errors: **{factors.get('parse_errors', 0)}**\n"
    text += f"- Marked debug print groups: **{factors.get('debug_print_markers', 0)}**\n\n"
    text += ai_section
    text += "## Highest-priority roadmap items\n\n" + roadmap_section + "\n"
    text += "## Entry points\n\n" + bullet_list(entrypoints, limit=120) + "\n"
    text += "## Local import cycles\n\n" + cycles_section + "\n"
    text += "## Parse errors\n\n" + parse_section + "\n"
    if debug_targets:
        debug_rows = [f"- `{path}` lines {', '.join(str(x) for x in lines)}" for path, lines in list(debug_targets.items())[:30]]
        if len(debug_targets) > 30:
            debug_rows.append(f"- ... and {len(debug_targets) - 30} more")
        text += "## Marked debug prints\n\n" + "\n".join(debug_rows) + "\n\n"
    text += "## Artifact paths\n\n"
    text += f"- `{to_posix_relative(config.git_root, config.analysis_path)}`\n"
    text += f"- `{to_posix_relative(config.git_root, config.graph_path)}`\n"
    text += f"- `{to_posix_relative(config.git_root, config.roadmap_path)}`\n"
    return text


# -----------------------------
# Patch planning
# -----------------------------

def build_debug_print_patch_plan(config: Config, analysis: Dict[str, Any]) -> Optional[PatchPlan]:
    roadmap = analysis.get("roadmap", [])
    if not roadmap:
        return None
    actionable = next((item for item in roadmap if item.get("name") == "remove_marked_debug_prints" and item.get("actionable")), None)
    if not actionable:
        return None

    file_changes: Dict[str, str] = {}
    removed_count = 0
    for file_info in analysis.get("python_files", []):
        lines = file_info.get("debug_print_lines") or []
        if not lines:
            continue
        abs_path = config.git_root / file_info["path"]
        original = abs_path.read_text(encoding="utf-8", errors="replace")
        new_lines: List[str] = []
        for idx, line in enumerate(original.splitlines(keepends=True), start=1):
            if idx in lines and PRINT_RE.search(line) and DEBUG_MARKER_RE.search(line):
                removed_count += 1
                continue
            new_lines.append(line)
        new_text = "".join(new_lines)
        if new_text != original:
            file_changes[file_info["path"]] = new_text

    if not file_changes:
        return None

    changed_files = sorted(file_changes)
    return PatchPlan(
        task="remove_marked_debug_prints",
        reason=f"remove-{removed_count}-marked-debug-print-lines",
        file_changes=file_changes,
        metadata={"removed_lines": removed_count, "changed_files": changed_files},
        pr_title="agent: remove marked debug prints",
        pr_body=(
            "Automated conservative patch from repo-architect.\n\n"
            f"Task: remove_marked_debug_prints\n"
            f"Reason: remove-{removed_count}-marked-debug-print-lines\n"
            f"Changed files: {', '.join(changed_files)}\n"
        ),
    )


def build_report_patch_plan(config: Config, analysis: Dict[str, Any], ai_meta: Dict[str, Any]) -> Optional[PatchPlan]:
    report_rel = to_posix_relative(config.git_root, config.report_path)
    report_text = render_runtime_inventory(config, analysis, ai_meta)
    existing = config.report_path.read_text(encoding="utf-8", errors="replace") if config.report_path.exists() else None
    if existing == report_text:
        return None

    file_changes = {report_rel: report_text}
    model_line = ai_meta.get("model") if ai_meta.get("used") else "static-only"
    pr_body = (
        "Automated repository inventory report from repo-architect.\n\n"
        f"Task: publish_runtime_inventory_report\n"
        f"Report path: {report_rel}\n"
        f"Architecture score: {analysis.get('architecture_score')}\n"
        f"Model enrichment: {model_line}\n"
    )
    return PatchPlan(
        task="publish_runtime_inventory_report",
        reason="refresh-runtime-inventory-report",
        file_changes=file_changes,
        metadata={"report_path": report_rel, "architecture_score": analysis.get("architecture_score"), "model_meta": ai_meta},
        pr_title="agent: refresh runtime inventory report",
        pr_body=pr_body,
    )


def validate_change(config: Config, changed_files: Sequence[str]) -> Tuple[bool, str]:
    if config.validate_cmd:
        proc = run_shell(config.validate_cmd, cwd=config.git_root, check=False)
        ok = proc.returncode == 0
        output = (proc.stdout or "") + (proc.stderr or "")
        return ok, output.strip()

    py_files = [f for f in changed_files if f.endswith(".py")]
    if not py_files:
        return True, "No Python files changed."

    proc = run_cmd([sys.executable, "-m", "py_compile", *py_files], cwd=config.git_root, check=False)
    ok = proc.returncode == 0
    output = (proc.stdout or "") + (proc.stderr or "")
    return ok, output.strip() or "py_compile passed"


def create_pull_request(config: Config, branch: str, title: str, body: str) -> Dict[str, Any]:
    if not config.github_token or not config.github_repo:
        raise RepoArchitectError("Missing GITHUB_TOKEN or GITHUB_REPO for PR creation.")
    base = config.github_base_branch or git_current_branch(config.git_root)
    payload = {
        "title": title,
        "head": branch,
        "base": base,
        "body": body,
        "maintainer_can_modify": True,
    }
    return github_api_request(config.github_token, f"/repos/{config.github_repo}/pulls", method="POST", payload=payload)


def apply_patch_plan(config: Config, plan: PatchPlan) -> Dict[str, Any]:
    if not config.allow_dirty and git_is_dirty(config.git_root):
        raise RepoArchitectError("Repository has uncommitted changes. Re-run with --allow-dirty if you really want mutation.")

    start_branch = git_current_branch(config.git_root)
    branch = safe_branch_name(plan.task, plan.reason)
    backups: Dict[str, Optional[str]] = {}
    changed_files = list(plan.file_changes.keys())
    created_branch = False

    try:
        git_checkout_new_branch(config.git_root, branch)
        created_branch = True

        for rel_path, new_text in plan.file_changes.items():
            abs_path = config.git_root / rel_path
            backups[rel_path] = abs_path.read_text(encoding="utf-8", errors="replace") if abs_path.exists() else None
            atomic_write_text(abs_path, new_text)

        ok, validation_output = validate_change(config, changed_files)
        if not ok:
            raise RepoArchitectError(f"Validation failed.\n{validation_output}")

        git_stage_and_commit(config.git_root, changed_files, f"agent: {plan.task}")

        pushed = False
        pr_url = None
        pr_number = None
        if config.github_token and config.github_repo and git_has_remote_origin(config.git_root):
            git_push_branch(config.git_root, branch)
            pushed = True
            pr = create_pull_request(config, branch, plan.pr_title, plan.pr_body)
            pr_url = pr.get("html_url")
            pr_number = pr.get("number")

        return {
            "status": "mutated",
            "branch": branch,
            "base_branch": start_branch,
            "changed_files": changed_files,
            "validation": validation_output,
            "pushed": pushed,
            "pull_request_url": pr_url,
            "pull_request_number": pr_number,
            "metadata": plan.metadata,
        }
    except Exception:
        for rel_path, old_text in backups.items():
            abs_path = config.git_root / rel_path
            if old_text is None:
                if abs_path.exists():
                    abs_path.unlink()
            else:
                atomic_write_text(abs_path, old_text)
        if created_branch:
            try:
                git_checkout(config.git_root, start_branch)
            except Exception:
                pass
            try:
                git_delete_branch(config.git_root, branch)
            except Exception:
                pass
        raise


# -----------------------------
# Workflow installation and branch protection
# -----------------------------

def build_workflow_yaml(secret_env_names: Sequence[str], interval_cron: str, default_model: Optional[str], default_report_path: str, default_mode: str) -> str:
    extra_env = "".join([f"          {name}: ${{{{ secrets.{name} }}}}\n" for name in secret_env_names])
    model_default = default_model or "openai/gpt-4.1"
    mode_default = default_mode or "report"
    return f"""name: repo-architect

on:
  workflow_dispatch:
    inputs:
      mode:
        description: 'Execution mode'
        required: true
        default: '{mode_default}'
        type: choice
        options:
          - analyze
          - report
          - mutate
      github_model:
        description: 'GitHub Models model id'
        required: true
        default: '{model_default}'
        type: string
      report_path:
        description: 'Path for generated report documentation'
        required: true
        default: '{default_report_path}'
        type: string
      mutation_budget:
        description: 'Maximum automatic mutations in a single run'
        required: true
        default: '1'
        type: choice
        options:
          - '1'

  schedule:
    - cron: '{interval_cron}'

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

      - name: Run repo architect
        env:
          GITHUB_TOKEN: ${{{{ github.token }}}}
          GITHUB_REPO: ${{{{ github.repository }}}}
          GITHUB_BASE_BRANCH: ${{{{ github.event.repository.default_branch }}}}
{extra_env}        run: |
          MODE="${{{{ github.event.inputs.mode }}}}"
          MODEL="${{{{ github.event.inputs.github_model }}}}"
          REPORT_PATH="${{{{ github.event.inputs.report_path }}}}"
          MUTATION_BUDGET="${{{{ github.event.inputs.mutation_budget }}}}"
          if [ -z "$MODE" ]; then MODE="{mode_default}"; fi
          if [ -z "$MODEL" ]; then MODEL="{model_default}"; fi
          if [ -z "$REPORT_PATH" ]; then REPORT_PATH="{default_report_path}"; fi
          if [ -z "$MUTATION_BUDGET" ]; then MUTATION_BUDGET="1"; fi
          export GITHUB_MODEL="$MODEL"
          python repo_architect.py --mode "$MODE" --report-path "$REPORT_PATH" --mutation-budget "$MUTATION_BUDGET"

      - name: Upload repo architect artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: repo-architect-${{{{ github.run_id }}}}
          path: |
            .agent
            {default_report_path}
          if-no-files-found: warn
          retention-days: 7
"""


def install_workflow(config: Config, secret_env_names: Sequence[str], cron: str, default_model: Optional[str], default_mode: str) -> pathlib.Path:
    path = config.workflow_path
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, build_workflow_yaml(secret_env_names, cron, default_model, to_posix_relative(config.git_root, config.report_path), default_mode))
    return path


def configure_branch_protection(config: Config) -> Dict[str, Any]:
    token = config.github_admin_token or config.github_token
    if not token or not config.github_repo:
        raise RepoArchitectError("Branch protection requires GITHUB_ADMIN_TOKEN or admin-capable GITHUB_TOKEN, plus GITHUB_REPO.")
    owner, repo = parse_owner_repo(config.github_repo)
    if not owner or not repo:
        raise RepoArchitectError("GITHUB_REPO must be in owner/repo format.")
    branch = config.github_base_branch or "main"
    payload = {
        "required_status_checks": None,
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 1,
            "require_last_push_approval": False,
        },
        "restrictions": None,
        "required_linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": False,
        "required_conversation_resolution": True,
        "lock_branch": False,
        "allow_fork_syncing": True,
    }
    result = github_api_request(token, f"/repos/{owner}/{repo}/branches/{branch}/protection", method="PUT", payload=payload)
    return {
        "configured": True,
        "branch": branch,
        "required_pr_reviews": True,
        "required_linear_history": True,
        "required_conversation_resolution": True,
        "enforce_admins": True,
        "api_result": result,
    }


# -----------------------------
# Main cycle
# -----------------------------

def run_cycle(config: Config) -> Dict[str, Any]:
    ensure_agent_dir(config.agent_dir)
    state = load_state(config)
    analysis = build_analysis(config.git_root)
    ai_meta = maybe_github_models_summary(config, analysis)
    analysis["github_models"] = ai_meta
    persist_analysis(config, analysis)

    additional_artifacts: List[pathlib.Path] = []
    report_text_preview = None
    report_path_rel = to_posix_relative(config.git_root, config.report_path)

    result: Dict[str, Any] = {
        "status": "analyzed",
        "mode": config.mode,
        "architecture_score": analysis["architecture_score"],
        "roadmap": analysis["roadmap"],
        "analysis_path": str(config.analysis_path),
        "graph_path": str(config.graph_path),
        "roadmap_path": str(config.roadmap_path),
        "repo_root": str(config.git_root),
        "github_models": ai_meta,
    }

    if config.mode == "analyze":
        result["status"] = "analysis_only"
    else:
        remaining = max(config.mutation_budget, 1)
        plan: Optional[PatchPlan] = None

        if config.mode == "mutate" and remaining > 0:
            plan = build_debug_print_patch_plan(config, analysis)
            if plan is not None:
                remaining -= 1

        if plan is None and config.mode in {"report", "mutate"} and remaining > 0:
            plan = build_report_patch_plan(config, analysis, ai_meta)
            if plan is not None:
                remaining -= 1
                additional_artifacts.append(config.report_path)
                report_text_preview = report_path_rel

        if plan is not None:
            result.update(apply_patch_plan(config, plan))
        else:
            result["status"] = "no_safe_mutation_available"
            if config.mode in {"report", "mutate"}:
                # Persist deterministic report even when unchanged, so artifacts exist.
                rendered = render_runtime_inventory(config, analysis, ai_meta)
                atomic_write_text(config.report_path, rendered)
                additional_artifacts.append(config.report_path)
                report_text_preview = report_path_rel

    result["artifact_files"] = write_artifact_manifest(config, additional_artifacts)
    if report_text_preview:
        result["report_path"] = report_text_preview

    state["runs"] = int(state.get("runs", 0)) + 1
    state["last_run_epoch"] = int(time.time())
    state.setdefault("history", []).append({
        "ts": state["last_run_epoch"],
        "status": result["status"],
        "mode": config.mode,
        "architecture_score": result["architecture_score"],
        "branch": result.get("branch"),
        "pull_request_url": result.get("pull_request_url"),
        "github_models": ai_meta,
    })
    state["history"] = state["history"][-100:]
    save_state(config, state)
    return result


# -----------------------------
# MCP
# -----------------------------

def mcp_tool_schema() -> List[Dict[str, Any]]:
    return [
        {
            "name": "analyze_repo",
            "description": "Analyze repository structure and write reports under .agent/.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "build_code_graph",
            "description": "Return the local Python import graph.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "architecture_score",
            "description": "Return the repository architecture score and factors.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "plan_next_task",
            "description": "Return the highest priority roadmap item.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "render_runtime_inventory",
            "description": "Render the deterministic runtime inventory markdown report.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "run_agent_cycle",
            "description": "Run one conservative cycle.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["analyze", "report", "mutate"]},
                    "allow_dirty": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        },
    ]


def mcp_response(id_value: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_value, "result": result}


def mcp_error(id_value: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_value, "error": {"code": code, "message": message}}


def mcp_tool_result(payload: Any) -> Dict[str, Any]:
    text = json.dumps(payload, indent=2, sort_keys=True)
    return {"content": [{"type": "text", "text": text}], "structuredContent": payload, "isError": False}


def handle_mcp_call(config: Config, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool_name == "analyze_repo":
        analysis = build_analysis(config.git_root)
        ai_meta = maybe_github_models_summary(config, analysis)
        analysis["github_models"] = ai_meta
        persist_analysis(config, analysis)
        write_artifact_manifest(config)
        return mcp_tool_result(analysis)
    if tool_name == "build_code_graph":
        analysis = build_analysis(config.git_root)
        return mcp_tool_result(analysis["local_import_graph"])
    if tool_name == "architecture_score":
        analysis = build_analysis(config.git_root)
        return mcp_tool_result({"architecture_score": analysis["architecture_score"], "score_factors": analysis["score_factors"]})
    if tool_name == "plan_next_task":
        analysis = build_analysis(config.git_root)
        roadmap = analysis.get("roadmap", [])
        return mcp_tool_result(roadmap[0] if roadmap else {})
    if tool_name == "render_runtime_inventory":
        analysis = build_analysis(config.git_root)
        ai_meta = maybe_github_models_summary(config, analysis)
        return mcp_tool_result({"path": to_posix_relative(config.git_root, config.report_path), "markdown": render_runtime_inventory(config, analysis, ai_meta)})
    if tool_name == "run_agent_cycle":
        local_config = dataclasses.replace(
            config,
            mode=str(arguments.get("mode", config.mode)),
            allow_dirty=bool(arguments.get("allow_dirty", config.allow_dirty)),
        )
        return mcp_tool_result(run_cycle(local_config))
    raise RepoArchitectError(f"Unknown tool: {tool_name}")


def run_mcp_server(config: Config) -> None:
    log("Starting MCP stdio server", json_mode=config.log_json)
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        msg: Dict[str, Any] = {}
        try:
            msg = json.loads(line)
            request_id = msg.get("id")
            method = msg.get("method")
            params = msg.get("params", {})
            if method == "initialize":
                response = mcp_response(request_id, {
                    "protocolVersion": "2025-06-18",
                    "serverInfo": {"name": APP_NAME, "version": VERSION},
                    "capabilities": {"tools": {"listChanged": False}},
                })
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                response = mcp_response(request_id, {"tools": mcp_tool_schema()})
            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments") or {}
                response = mcp_response(request_id, handle_mcp_call(config, name, arguments))
            else:
                response = mcp_error(request_id, -32601, f"Method not found: {method}")
        except Exception as exc:
            response = mcp_error(msg.get("id"), -32000, str(exc))
            log("MCP error", data={"error": str(exc), "trace": traceback.format_exc()}, json_mode=config.log_json)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


# -----------------------------
# CLI
# -----------------------------

def build_config(args: argparse.Namespace) -> Config:
    git_root = discover_git_root()
    agent_dir = git_root / AGENT_DIRNAME
    mode = args.mode
    if args.analyze_only:
        mode = "analyze"
    return Config(
        git_root=git_root,
        agent_dir=agent_dir,
        state_path=agent_dir / STATE_FILE,
        analysis_path=agent_dir / ANALYSIS_FILE,
        graph_path=agent_dir / GRAPH_FILE,
        roadmap_path=agent_dir / ROADMAP_FILE,
        artifact_manifest_path=agent_dir / ARTIFACT_MANIFEST_FILE,
        workflow_path=git_root / WORKFLOW_PATH,
        github_token=os.environ.get("GITHUB_TOKEN"),
        github_repo=os.environ.get("GITHUB_REPO"),
        github_base_branch=os.environ.get("GITHUB_BASE_BRANCH"),
        github_admin_token=os.environ.get("GITHUB_ADMIN_TOKEN"),
        allow_dirty=args.allow_dirty,
        mode=mode,
        interval=args.interval,
        log_json=args.log_json,
        validate_cmd=os.environ.get("REPO_ARCHITECT_TEST_CMD"),
        github_model=args.github_model or os.environ.get("GITHUB_MODEL"),
        report_path=(git_root / args.report_path).resolve(),
        mutation_budget=max(int(args.mutation_budget), 1),
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single-file repo architect and MCP server.")
    parser.add_argument("--mode", choices=["analyze", "report", "mutate"], default="mutate", help="Execution mode. Default: mutate")
    parser.add_argument("--analyze-only", action="store_true", help="Deprecated alias for --mode analyze.")
    parser.add_argument("--daemon", action="store_true", help="Run continuously on the current host.")
    parser.add_argument("--interval", type=int, default=3600, help="Seconds between daemon cycles. Default: 3600.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow mutation even if the repository has uncommitted changes.")
    parser.add_argument("--mcp", action="store_true", help="Start stdio MCP server instead of running a cycle.")
    parser.add_argument("--github-model", default=None, help="GitHub Models model id, e.g. openai/gpt-4.1")
    parser.add_argument("--report-path", default=DEFAULT_REPORT_PATH, help=f"Path for generated report docs. Default: {DEFAULT_REPORT_PATH}")
    parser.add_argument("--mutation-budget", type=int, default=1, help="Maximum automatic mutations in a single run. Default: 1")

    parser.add_argument("--install-gh-workflow", action="store_true", help="Write a GitHub Actions workflow for continuous execution on GitHub-hosted runners.")
    parser.add_argument("--workflow-cron", default="17 * * * *", help="Cron for generated workflow. Default: 17 * * * *")
    parser.add_argument("--workflow-secret-env", nargs="*", default=[], help="Extra GitHub Actions secrets to expose as env vars in the generated workflow.")
    parser.add_argument("--workflow-default-mode", choices=["analyze", "report", "mutate"], default="report", help="Default mode for workflow_dispatch empty inputs.")

    parser.add_argument("--configure-branch-protection", action="store_true", help="Configure conservative branch protection on the base branch. Requires admin token.")
    parser.add_argument("--log-json", action="store_true", help="Emit stderr logs as JSON.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        config = build_config(args)
        os.chdir(config.git_root)

        if args.install_gh_workflow:
            workflow_path = install_workflow(config, args.workflow_secret_env, args.workflow_cron, config.github_model, args.workflow_default_mode)
            log(
                "Installed GitHub Actions workflow",
                data={
                    "workflow_path": str(workflow_path),
                    "runner": "GitHub-hosted runner via runs-on: ubuntu-latest",
                    "mode": "scheduled + workflow_dispatch",
                    "extra_secret_env": args.workflow_secret_env,
                    "github_model_env": config.github_model,
                    "github_models_permissions": "models: read",
                },
                json_mode=config.log_json,
            )
            return 0

        if args.configure_branch_protection:
            result = configure_branch_protection(config)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        if args.mcp:
            run_mcp_server(config)
            return 0

        if args.daemon:
            log(
                "Starting daemon mode",
                data={
                    "runs_where": str(config.git_root),
                    "host": "current machine or CI runner process that started this script",
                    "interval_seconds": config.interval,
                    "mode": config.mode,
                },
                json_mode=config.log_json,
            )
            while True:
                try:
                    result = run_cycle(config)
                    log("Cycle complete", data=result, json_mode=config.log_json)
                except Exception as exc:
                    log("Cycle failed", data={"error": str(exc), "trace": traceback.format_exc()}, json_mode=config.log_json)
                time.sleep(config.interval)
            return 0

        result = run_cycle(config)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except RepoArchitectError as exc:
        log("Fatal error", data={"error": str(exc)}, json_mode=args.log_json if args else False)
        return 2
    except Exception as exc:
        log("Unhandled error", data={"error": str(exc), "trace": traceback.format_exc()}, json_mode=args.log_json if args else False)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
