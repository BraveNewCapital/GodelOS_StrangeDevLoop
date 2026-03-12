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


def safe_branch_name(stable_hint: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._/-]+", "-", stable_hint).strip("-/").lower()
    return slug[:100]


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


def parse_model_text(resp: Dict[str, Any]) -> str:
    try:
        return resp["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        raise RepoArchitectError(f"Could not parse GitHub Models response: {exc}")


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
    meta = {"enabled": False, "used": False, "model": config.github_model, "summary": None, "fallback_reason": None}
    if not config.github_token or not config.github_model:
        return meta
    try:
        catalog = github_models_catalog(config.github_token)
        meta["enabled"] = True
        if not model_available(catalog, config.github_model):
            meta["fallback_reason"] = f"model_not_in_catalog:{config.github_model}"
            return meta
        prompt = textwrap.dedent(f"""
        You are summarizing repository architecture risk.
        Architecture score: {analysis['architecture_score']}
        Local import cycles: {len(analysis['cycles'])}
        Parse error files: {len(analysis['parse_error_files'])}
        Entrypoints: {len(analysis['entrypoint_paths'])}
        Top roadmap items: {json.dumps(analysis['roadmap'][:5])}

        Return 5 bullet points, compact and concrete, no preamble.
        """).strip()
        resp = github_models_chat(config.github_token, config.github_model, [
            {"role": "system", "content": "You produce concise engineering prioritization notes."},
            {"role": "user", "content": prompt},
        ])
        meta["summary"] = parse_model_text(resp)
        meta["used"] = True
        return meta
    except Exception as exc:
        meta["fallback_reason"] = str(exc)
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
        f"- architecture score: **{result.get('architecture_score')}**",
        f"- changed files: `{len(result.get('changed_files', []))}`",
    ]
    if result.get("pull_request_url"):
        summary.append(f"- pull request: {result['pull_request_url']}")
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


def build_patch_plan(config: Config, analysis: Dict[str, Any], model_meta: Dict[str, Any], state: Dict[str, Any]) -> Optional[PatchPlan]:
    if config.mode == "analyze":
        return None
    # self-tuning bias: after repeated no-op or report success, widen one notch in mutate mode.
    if config.mode == "mutate":
        plan = remove_marked_debug_prints(config.git_root, analysis, config.mutation_budget)
        if plan is not None:
            return plan
        return build_report_plan(config, analysis, model_meta, state)
    return build_report_plan(config, analysis, model_meta, state)


# -----------------------------
# Validation / execution
# -----------------------------

def validate_change(config: Config, changed_files: Sequence[str]) -> Tuple[bool, str]:
    py_files = [p for p in changed_files if p.endswith('.py')]
    if not py_files:
        return True, 'No Python files changed.'
    proc = run_cmd([sys.executable, '-m', 'py_compile', *py_files], cwd=config.git_root, check=False)
    out = (proc.stdout or '') + (proc.stderr or '')
    return proc.returncode == 0, out.strip() or 'py_compile passed'


def apply_patch_plan(config: Config, plan: PatchPlan, state: Dict[str, Any]) -> Dict[str, Any]:
    baseline_dirty_guard(config)
    if not git_identity_present(config.git_root):
        raise RepoArchitectError('Git identity is not configured. Set git user.name and user.email before mutation.')

    start_branch = git_current_branch(config.git_root)
    branch = safe_branch_name(plan.stable_branch_hint)
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

        ok, validation = validate_change(config, changed_files)
        if not ok:
            raise RepoArchitectError(f'Validation failed.\n{validation}')

        commit_message = f"agent: {plan.task}"
        git_stage_and_commit(config.git_root, changed_files, commit_message)
        pushed = False
        pr_url = None
        pr_number = None
        if config.github_token and config.github_repo and git_has_remote_origin(config.git_root):
            git_push_branch(config.git_root, branch)
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
    model_default = github_model or "openai/gpt-4.1"
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
      github_model:
        description: 'GitHub Models model id'
        required: true
        default: '{model_default}'
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
          if [ -z "$MODE" ]; then MODE="report"; fi
          if [ -z "$MODEL" ]; then MODEL="{model_default}"; fi
          if [ -z "$REPORT_PATH" ]; then REPORT_PATH="{DEFAULT_REPORT_PATH.as_posix()}"; fi
          if [ -z "$MUTATION_BUDGET" ]; then MUTATION_BUDGET="1"; fi
          export GITHUB_MODEL="$MODEL"
          python repo_architect.py --allow-dirty --mode "$MODE" --report-path "$REPORT_PATH" --mutation-budget "$MUTATION_BUDGET"

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
        "architecture_score": analysis["architecture_score"],
        "repo_root": str(config.git_root),
        "analysis_path": str(config.analysis_path),
        "graph_path": str(config.graph_path),
        "roadmap_path": str(config.roadmap_path),
        "roadmap": analysis["roadmap"],
        "github_models": model_meta,
        "artifact_files": artifact_files,
        "metadata": {"architecture_score": analysis["architecture_score"], "model_meta": model_meta, "report_path": str(config.report_path)},
    }

    plan = build_patch_plan(config, analysis, model_meta, state)
    if plan is not None:
        apply_result = apply_patch_plan(config, plan, state)
        result.update(apply_result)
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
        "branch": result.get("branch"),
        "pull_request_url": result.get("pull_request_url"),
        "mode": config.mode,
    })
    state["history"] = state["history"][-100:]
    save_state(config, state)
    return result


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
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Single-file repo architect, PR bot, and MCP server.")
    p.add_argument("--mode", choices=["analyze", "report", "mutate"], default="report")
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
    p.add_argument("--github-model", default=None)
    p.add_argument("--log-json", action="store_true")
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
