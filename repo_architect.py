#!/usr/bin/env python3
"""
repo_architect.py

Single-file, standard-library-only repository architect and MCP server.

Default mode:
    python repo_architect.py

What it does in default mode:
    1. Verifies it is inside a git repository.
    2. Analyzes repository structure and Python import graph.
    3. Synthesizes a roadmap and writes reports to .agent/.
    4. Applies one conservative, auditable improvement if found.
    5. Creates a branch, validates the change, commits it.
    6. Pushes and opens a pull request if GitHub credentials are available.

Other modes:
    python repo_architect.py --analyze-only
    python repo_architect.py --daemon --interval 3600
    python repo_architect.py --mcp
    python repo_architect.py --install-gh-workflow --workflow-secret-env EXTRA_SECRET_NAME OTHER_SECRET

Security / safety posture:
    - Standard library only.
    - Refuses to mutate a dirty repository unless --allow-dirty is used.
    - Conservative patcher only removes Python lines that are explicitly marked as
      debug prints using # DEBUG, # debug, or # DBG.
    - Never auto-merges.
    - Optional AI synthesis uses GitHub Models via GitHub credentials when GITHUB_MODEL is set.
    - MCP mode logs to stderr only. Stdout is reserved for JSON-RPC.
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
import time
import traceback
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


VERSION = "1.0.0"
APP_NAME = "repo-architect"
AGENT_DIRNAME = ".agent"
STATE_FILE = "repo_architect_state.json"
ANALYSIS_FILE = "latest_analysis.json"
GRAPH_FILE = "code_graph.json"
ROADMAP_FILE = "roadmap.json"
WORKFLOW_PATH = pathlib.Path(".github/workflows/repo-architect.yml")
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
GITHUB_MODELS_ENDPOINT = "https://models.github.ai/inference/chat/completions"
GITHUB_API_VERSION = "2022-11-28"


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
    workflow_path: pathlib.Path
    github_token: Optional[str]
    github_repo: Optional[str]
    github_base_branch: Optional[str]
    allow_dirty: bool
    analyze_only: bool
    interval: int
    log_json: bool
    validate_cmd: Optional[str]
    github_model: Optional[str]


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


def run_shell(cmd: str, *, cwd: pathlib.Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        shell=True,
        text=True,
        capture_output=True,
        check=check,
    )


def discover_git_root() -> pathlib.Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RepoArchitectError("Not inside a git repository.")
    return pathlib.Path(proc.stdout.strip()).resolve()


def git_current_branch(root: pathlib.Path) -> str:
    proc = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    return proc.stdout.strip()


def git_is_dirty(root: pathlib.Path) -> bool:
    proc = run_cmd(["git", "status", "--porcelain"], cwd=root)
    return bool(proc.stdout.strip())


def git_has_remote_origin(root: pathlib.Path) -> bool:
    proc = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=str(root),
        text=True,
        capture_output=True,
    )
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
    entrypoints = [p.path for p in py_infos if p.entrypoint]
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
    if not tasks:
        tasks.append({
            "name": "no_safe_mutation_available",
            "priority": 10,
            "actionable": False,
            "summary": f"Architecture score {score}. No conservative automatic patch found.",
            "targets": [],
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
    return {
        "version": VERSION,
        "generated_at_epoch": int(time.time()),
        "repo_root": str(root),
        "architecture_score": score,
        "score_factors": factors,
        "python_files": [dataclasses.asdict(info) for info in py_infos],
        "local_import_graph": graph,
        "cycles": cycles,
        "roadmap": roadmap,
    }


def github_models_chat_completion(
    token: str,
    model: str,
    messages: Sequence[Dict[str, str]],
    *,
    max_tokens: int = 500,
    temperature: float = 0.2,
    response_format: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": list(messages),
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format is not None:
        payload["response_format"] = response_format
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=GITHUB_MODELS_ENDPOINT,
        method="POST",
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RepoArchitectError(f"GitHub Models inference failed: {exc.code} {body}") from exc


def enrich_analysis_with_github_models(config: Config, analysis: Dict[str, Any]) -> Dict[str, Any]:
    if not config.github_model:
        return analysis
    if not config.github_token:
        raise RepoArchitectError("GITHUB_MODEL was set but GITHUB_TOKEN is missing. Local GitHub Models calls require a token with the models scope.")

    compact = {
        "architecture_score": analysis.get("architecture_score"),
        "score_factors": analysis.get("score_factors"),
        "cycles": analysis.get("cycles"),
        "roadmap": analysis.get("roadmap"),
    }
    system_prompt = (
        "You are a repository architecture reviewer. Return strict JSON with keys "
        "summary, primary_risks, and next_actions. Keep next_actions concrete and concise."
    )
    user_prompt = (
        "Review this repository analysis and return a concise JSON assessment.\n\n"
        + json.dumps(compact, sort_keys=True)
    )
    response = github_models_chat_completion(
        config.github_token,
        config.github_model,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=500,
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    content = (((response.get("choices") or [{}])[0].get("message") or {}).get("content", "")).strip()
    try:
        parsed = json.loads(content) if content else {}
    except json.JSONDecodeError:
        parsed = {"summary": content, "primary_risks": [], "next_actions": []}
    analysis = dict(analysis)
    analysis["github_models"] = {
        "model": config.github_model,
        "assessment": parsed,
        "raw_response": response,
    }
    return analysis


def build_patch_plan(config: Config, analysis: Dict[str, Any]) -> Optional[PatchPlan]:
    roadmap = analysis.get("roadmap", [])
    if not roadmap:
        return None
    first = roadmap[0]
    if first.get("name") != "remove_marked_debug_prints" or not first.get("actionable"):
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

    return PatchPlan(
        task="remove_marked_debug_prints",
        reason=f"remove-{removed_count}-marked-debug-print-lines",
        file_changes=file_changes,
        metadata={
            "removed_lines": removed_count,
            "changed_files": sorted(file_changes),
        },
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


def github_request(token: str, path: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=f"https://api.github.com{path}",
        method=method,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": APP_NAME,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RepoArchitectError(f"GitHub API {method} {path} failed: {exc.code} {body}") from exc


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
    return github_request(config.github_token, f"/repos/{config.github_repo}/pulls", method="POST", payload=payload)


def ensure_agent_dir(path: pathlib.Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_state(config: Config) -> Dict[str, Any]:
    default = {"version": VERSION, "runs": 0, "last_run_epoch": None, "history": []}
    return read_json(config.state_path, default)


def save_state(config: Config, state: Dict[str, Any]) -> None:
    atomic_write_json(config.state_path, state)


def persist_analysis(config: Config, analysis: Dict[str, Any]) -> None:
    atomic_write_json(config.analysis_path, analysis)
    atomic_write_json(config.graph_path, analysis.get("local_import_graph", {}))
    atomic_write_json(config.roadmap_path, {"roadmap": analysis.get("roadmap", [])})


def build_workflow_yaml(secret_env_names: Sequence[str], interval_cron: str, github_model: Optional[str]) -> str:
    extra_env = "".join([f"          {name}: ${{{{ secrets.{name} }}}}\n" for name in secret_env_names])
    model_env = f"          GITHUB_MODEL: {github_model}\n" if github_model else ""
    return f"""name: repo-architect

on:
  workflow_dispatch:
  schedule:
    - cron: '{interval_cron}'

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
{model_env}{extra_env}        run: |
          python repo_architect.py
"""


def install_workflow(config: Config, secret_env_names: Sequence[str], cron: str) -> pathlib.Path:
    path = config.workflow_path
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, build_workflow_yaml(secret_env_names, cron, config.github_model))
    return path


def apply_patch_plan(config: Config, plan: PatchPlan) -> Dict[str, Any]:
    if not config.allow_dirty and git_is_dirty(config.git_root):
        raise RepoArchitectError("Repository has uncommitted changes. Re-run with --allow-dirty if you really want mutation.")

    start_branch = git_current_branch(config.git_root)
    branch = safe_branch_name(plan.task, plan.reason)
    backups: Dict[str, str] = {}
    changed_files = list(plan.file_changes.keys())
    created_branch = False

    try:
        git_checkout_new_branch(config.git_root, branch)
        created_branch = True

        for rel_path, new_text in plan.file_changes.items():
            abs_path = config.git_root / rel_path
            backups[rel_path] = abs_path.read_text(encoding="utf-8", errors="replace")
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
            pr = create_pull_request(
                config,
                branch,
                f"agent: {plan.task}",
                (
                    f"Automated conservative patch from {APP_NAME}.\n\n"
                    f"Task: {plan.task}\n"
                    f"Reason: {plan.reason}\n"
                    f"Changed files: {', '.join(changed_files)}\n"
                    f"Validation: OK\n"
                ),
            )
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
            atomic_write_text(config.git_root / rel_path, old_text)
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


def run_cycle(config: Config) -> Dict[str, Any]:
    ensure_agent_dir(config.agent_dir)
    state = load_state(config)
    analysis = build_analysis(config.git_root)
    analysis = enrich_analysis_with_github_models(config, analysis)
    persist_analysis(config, analysis)

    result: Dict[str, Any] = {
        "status": "analyzed",
        "architecture_score": analysis["architecture_score"],
        "roadmap": analysis["roadmap"],
        "analysis_path": str(config.analysis_path),
        "graph_path": str(config.graph_path),
        "roadmap_path": str(config.roadmap_path),
        "repo_root": str(config.git_root),
    }

    if config.analyze_only:
        result["status"] = "analysis_only"
    else:
        plan = build_patch_plan(config, analysis)
        if plan is not None:
            result.update(apply_patch_plan(config, plan))
        else:
            result["status"] = "no_safe_mutation_available"

    state["runs"] = int(state.get("runs", 0)) + 1
    state["last_run_epoch"] = int(time.time())
    state.setdefault("history", []).append({
        "ts": state["last_run_epoch"],
        "status": result["status"],
        "architecture_score": result["architecture_score"],
        "branch": result.get("branch"),
        "pull_request_url": result.get("pull_request_url"),
    })
    state["history"] = state["history"][-100:]
    save_state(config, state)
    return result


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
            "name": "run_agent_cycle",
            "description": "Run one conservative mutation cycle.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "analyze_only": {"type": "boolean"},
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
        analysis = enrich_analysis_with_github_models(config, build_analysis(config.git_root))
        persist_analysis(config, analysis)
        return mcp_tool_result(analysis)
    if tool_name == "build_code_graph":
        analysis = enrich_analysis_with_github_models(config, build_analysis(config.git_root))
        return mcp_tool_result(analysis["local_import_graph"])
    if tool_name == "architecture_score":
        analysis = enrich_analysis_with_github_models(config, build_analysis(config.git_root))
        payload = {"architecture_score": analysis["architecture_score"], "score_factors": analysis["score_factors"]}
        if "github_models" in analysis:
            payload["github_models"] = analysis["github_models"]
        return mcp_tool_result(payload)
    if tool_name == "plan_next_task":
        analysis = enrich_analysis_with_github_models(config, build_analysis(config.git_root))
        roadmap = analysis.get("roadmap", [])
        return mcp_tool_result(roadmap[0] if roadmap else {})
    if tool_name == "run_agent_cycle":
        local_config = dataclasses.replace(
            config,
            analyze_only=bool(arguments.get("analyze_only", False)),
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
        workflow_path=git_root / WORKFLOW_PATH,
        github_token=os.environ.get("GITHUB_TOKEN"),
        github_repo=os.environ.get("GITHUB_REPO"),
        github_base_branch=os.environ.get("GITHUB_BASE_BRANCH"),
        allow_dirty=args.allow_dirty,
        analyze_only=args.analyze_only,
        interval=args.interval,
        log_json=args.log_json,
        validate_cmd=os.environ.get("REPO_ARCHITECT_TEST_CMD"),
        github_model=args.github_model or os.environ.get("GITHUB_MODEL"),
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single-file repo architect and MCP server.")
    parser.add_argument("--analyze-only", action="store_true", help="Do not mutate git state. Only write analysis files.")
    parser.add_argument("--daemon", action="store_true", help="Run continuously on the current host.")
    parser.add_argument("--interval", type=int, default=3600, help="Seconds between daemon cycles. Default: 3600.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow mutation even if the repository has uncommitted changes.")
    parser.add_argument("--mcp", action="store_true", help="Start stdio MCP server instead of running a cycle.")
    parser.add_argument("--install-gh-workflow", action="store_true", help="Write a GitHub Actions workflow for continuous execution on GitHub-hosted runners.")
    parser.add_argument("--github-model", default=None, help="Optional GitHub Models model ID, for example openai/gpt-4.1. If set, analysis is enriched via GitHub Models.")
    parser.add_argument("--workflow-cron", default="17 * * * *", help="Cron for generated workflow. Default: 17 * * * *")
    parser.add_argument("--workflow-secret-env", nargs="*", default=[], help="Extra GitHub Actions secrets to expose as env vars in the generated workflow, for example EXTRA_SECRET_NAME OTHER_SECRET.")
    parser.add_argument("--log-json", action="store_true", help="Emit stderr logs as JSON.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        config = build_config(args)
        os.chdir(config.git_root)

        if (args.github_model or os.environ.get("GITHUB_MODEL")) and not os.environ.get("GITHUB_TOKEN"):
            raise RepoArchitectError("GITHUB_MODEL is set but GITHUB_TOKEN is missing. Local GitHub Models calls require a token with the models scope.")

        if args.install_gh_workflow:
            workflow_path = install_workflow(config, args.workflow_secret_env, args.workflow_cron)
            log(
                "Installed GitHub Actions workflow",
                data={
                    "workflow_path": str(workflow_path),
                    "runner": "GitHub-hosted runner via runs-on: ubuntu-latest",
                    "mode": "scheduled + workflow_dispatch",
                    "extra_secret_env": args.workflow_secret_env,
                    "github_models_permissions": "models: read",
                    "github_model_env": args.github_model or os.environ.get("GITHUB_MODEL"),
                },
                json_mode=config.log_json,
            )
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
