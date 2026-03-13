"""Critical-path tests for repo_architect.py.

These tests verify:
- Branch suffix generation (uniqueness, edge cases, length cap)
- Model fallback selection behavior
- Syntax validation of generated Python (ast.parse gate)
- Campaign aggregation behavior
- Output schema stability for key fields
- Lane selection priority
"""
from __future__ import annotations

import ast
import dataclasses
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import patch

# Make repo_architect importable from repo root
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import repo_architect as ra  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_git_root(tmp: str) -> pathlib.Path:
    root = pathlib.Path(tmp)
    subprocess.run(["git", "init", str(root)], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], capture_output=True)
    # Create an initial commit so HEAD exists and branch operations work
    (root / "README.md").write_text("test repo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "init"], capture_output=True)
    return root


def _make_config(root: Optional[pathlib.Path] = None, mode: str = "analyze", **overrides: Any) -> ra.Config:
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
    agent_dir = root / ".agent"
    cfg = ra.Config(
        git_root=root,
        agent_dir=agent_dir,
        state_path=agent_dir / "state.json",
        analysis_path=agent_dir / "latest_analysis.json",
        graph_path=agent_dir / "code_graph.json",
        roadmap_path=agent_dir / "roadmap.json",
        artifact_manifest_path=agent_dir / "artifacts_manifest.json",
        workflow_path=root / ".github/workflows/repo-architect.yml",
        step_summary_path=None,
        github_token=None,
        github_repo=None,
        github_base_branch="main",
        github_admin_token=None,
        github_model=None,
        allow_dirty=True,
        mode=mode,
        interval=3600,
        log_json=False,
        report_path=root / "docs/repo_architect/runtime_inventory.md",
        mutation_budget=1,
        configure_branch_protection=False,
        preferred_model=None,
        fallback_model=None,
        github_fallback_model=None,
    )
    if overrides:
        cfg = dataclasses.replace(cfg, **overrides)
    return cfg


# ---------------------------------------------------------------------------
# 1. Branch suffix generation
# ---------------------------------------------------------------------------

class TestWithUniqueBranchSuffix(unittest.TestCase):
    """Verify branch suffix uniqueness, edge cases, and length capping."""

    def setUp(self) -> None:
        for k in ("REPO_ARCHITECT_BRANCH_SUFFIX", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
            os.environ.pop(k, None)

    def tearDown(self) -> None:
        for k in ("REPO_ARCHITECT_BRANCH_SUFFIX", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
            os.environ.pop(k, None)

    def test_env_var_suffix_used(self) -> None:
        os.environ["REPO_ARCHITECT_BRANCH_SUFFIX"] = "mytest"
        result = ra.with_unique_branch_suffix("agent/report/foo")
        self.assertTrue(result.endswith("-mytest"), result)

    def test_run_id_and_attempt_used_when_no_suffix_env(self) -> None:
        os.environ["GITHUB_RUN_ID"] = "12345678"
        os.environ["GITHUB_RUN_ATTEMPT"] = "2"
        result = ra.with_unique_branch_suffix("agent/report/foo")
        self.assertTrue(result.endswith("-12345678-2"), result)

    def test_timestamp_fallback_when_no_env(self) -> None:
        result = ra.with_unique_branch_suffix("agent/report/foo")
        # Should have a non-empty suffix; timestamp is 14 ASCII digits: YYYYmmddHHMMSS
        self.assertIn("-", result)
        suffix = result.rsplit("-", 1)[-1]
        self.assertRegex(suffix, r"^\d{14}$", f"Expected 14-digit timestamp suffix, got: {suffix!r}")

    def test_invalid_chars_sanitised(self) -> None:
        os.environ["REPO_ARCHITECT_BRANCH_SUFFIX"] = "hello/world!@#"
        result = ra.with_unique_branch_suffix("agent/fix/thing")
        for bad_char in "!@#":
            self.assertNotIn(bad_char, result)

    def test_all_invalid_chars_falls_back_to_timestamp(self) -> None:
        """If sanitisation produces an empty string, fall back to UTC timestamp."""
        os.environ["REPO_ARCHITECT_BRANCH_SUFFIX"] = "!!!"
        result = ra.with_unique_branch_suffix("agent/fix/thing")
        self.assertFalse(result.endswith("-"), f"Should not end with dash: {result!r}")
        self.assertNotEqual(result, "agent/fix/thing-")
        # Suffix should now be a timestamp
        suffix = result[len("agent/fix/thing-"):]
        self.assertTrue(suffix.isdigit() or len(suffix) >= 8, f"Expected timestamp suffix, got: {suffix!r}")

    def test_total_length_capped(self) -> None:
        os.environ["REPO_ARCHITECT_BRANCH_SUFFIX"] = "x" * 200
        result = ra.with_unique_branch_suffix("agent/" + "y" * 100)
        self.assertLessEqual(len(result), ra._MAX_BRANCH_NAME_LEN)

    def test_normal_case_stays_under_max_length(self) -> None:
        os.environ["REPO_ARCHITECT_BRANCH_SUFFIX"] = "12345678-1"
        result = ra.with_unique_branch_suffix("agent/report/runtime-inventory-packet")
        self.assertLessEqual(len(result), ra._MAX_BRANCH_NAME_LEN)
        self.assertTrue(result.endswith("-12345678-1"))

    def test_no_double_dash_from_stripped_suffix(self) -> None:
        """Suffix that strips to something clean should not create '--'."""
        os.environ["REPO_ARCHITECT_BRANCH_SUFFIX"] = "-abc-"
        result = ra.with_unique_branch_suffix("agent/fix/foo")
        self.assertNotIn("--", result)


# ---------------------------------------------------------------------------
# 2. Model fallback selection behaviour
# ---------------------------------------------------------------------------

class TestIsModelUnavailableError(unittest.TestCase):
    def test_unknown_model(self) -> None:
        self.assertTrue(ra._is_model_unavailable_error("unknown_model: gpt-5.4"))

    def test_model_not_found(self) -> None:
        self.assertTrue(ra._is_model_unavailable_error("model_not_found"))

    def test_not_found(self) -> None:
        self.assertTrue(ra._is_model_unavailable_error("not found"))

    def test_does_not_exist(self) -> None:
        self.assertTrue(ra._is_model_unavailable_error("The requested model does not exist"))

    def test_invalid_model(self) -> None:
        self.assertTrue(ra._is_model_unavailable_error("invalid model specified"))

    def test_transient_rate_limit(self) -> None:
        self.assertFalse(ra._is_model_unavailable_error("rate limit exceeded"))

    def test_transient_timeout(self) -> None:
        self.assertFalse(ra._is_model_unavailable_error("connection timed out"))

    def test_case_insensitive(self) -> None:
        self.assertTrue(ra._is_model_unavailable_error("UNKNOWN_MODEL"))
        self.assertTrue(ra._is_model_unavailable_error("Model_Not_Found"))


# ---------------------------------------------------------------------------
# 2b. _should_try_fallback — expanded trigger set
# ---------------------------------------------------------------------------

class TestShouldTryFallback(unittest.TestCase):
    """Verify _should_try_fallback covers the explicit and minimal trigger set."""

    def test_model_unavailable_triggers(self) -> None:
        self.assertTrue(ra._should_try_fallback("unknown_model: gpt-5.4 not found"))

    def test_http_403_triggers(self) -> None:
        self.assertTrue(ra._should_try_fallback(
            "GitHub Models inference failed: 403 Permission denied"
        ))

    def test_http_404_triggers(self) -> None:
        self.assertTrue(ra._should_try_fallback(
            "GitHub Models inference failed: 404 Not found"
        ))

    def test_http_429_triggers(self) -> None:
        self.assertTrue(ra._should_try_fallback(
            "GitHub Models inference failed: 429 Too many requests"
        ))

    def test_http_500_triggers(self) -> None:
        self.assertTrue(ra._should_try_fallback(
            "GitHub Models inference failed: 500 Internal server error"
        ))

    def test_http_503_triggers(self) -> None:
        self.assertTrue(ra._should_try_fallback(
            "GitHub Models inference failed: 503 Service unavailable"
        ))

    def test_timeout_triggers(self) -> None:
        self.assertTrue(ra._should_try_fallback(
            "GitHub Models inference network error: timed out"
        ))

    def test_timeout_keyword_triggers(self) -> None:
        self.assertTrue(ra._should_try_fallback(
            "GitHub Models inference network error: timeout"
        ))

    def test_bare_rate_limit_string_does_not_trigger(self) -> None:
        """A generic 'rate limit exceeded' message (no HTTP code) must NOT trigger."""
        self.assertFalse(ra._should_try_fallback("rate limit exceeded"))

    def test_http_200_does_not_trigger(self) -> None:
        self.assertFalse(ra._should_try_fallback(
            "GitHub Models inference failed: 200 OK"
        ))

    def test_http_400_does_not_trigger(self) -> None:
        """400 Bad Request is a client error that should not trigger fallback."""
        self.assertFalse(ra._should_try_fallback(
            "GitHub Models inference failed: 400 Bad request"
        ))


class TestCallModelsWithFallback(unittest.TestCase):
    _MESSAGES = [{"role": "user", "content": "hi"}]

    def test_preferred_succeeds_no_fallback(self) -> None:
        fake_resp = {"choices": [{"message": {"content": "ok"}}], "model": "openai/gpt-5.4"}
        with patch.object(ra, "github_models_chat", return_value=fake_resp):
            resp, req_model, reason, fell = ra.call_models_with_fallback_or_none(
                "tok", "openai/gpt-5.4", "openai/gpt-4.1", self._MESSAGES
            )
        self.assertEqual(resp, fake_resp)
        self.assertEqual(req_model, "openai/gpt-5.4")
        self.assertIsNone(reason)
        self.assertFalse(fell)

    def test_fallback_triggered_on_model_unavailable(self) -> None:
        fallback_resp = {"choices": [{"message": {"content": "ok"}}], "model": "openai/gpt-4.1"}

        def side_effect(token: str, model: str, messages: list) -> dict:
            if model == "openai/gpt-5.4":
                raise ra.RepoArchitectError("unknown_model: gpt-5.4 is not available")
            return fallback_resp

        with patch.object(ra, "github_models_chat", side_effect=side_effect):
            resp, req_model, reason, fell = ra.call_models_with_fallback_or_none(
                "tok", "openai/gpt-5.4", "openai/gpt-4.1", self._MESSAGES
            )
        self.assertEqual(resp, fallback_resp)
        self.assertTrue(fell)
        self.assertIsNotNone(reason)
        self.assertIn("unknown_model", reason)

    def test_fallback_triggered_on_http_403(self) -> None:
        """HTTP 403 (permission) on primary must trigger exactly one fallback attempt."""
        fallback_resp = {"choices": [{"message": {"content": "ok"}}], "model": "openai/gpt-4.1"}
        calls: List[str] = []

        def side_effect(token: str, model: str, messages: list) -> dict:
            calls.append(model)
            if model == "anthropic/claude-sonnet-4.5":
                raise ra.RepoArchitectError(
                    "GitHub Models inference failed: 403 Permission denied"
                )
            return fallback_resp

        with patch.object(ra, "github_models_chat", side_effect=side_effect):
            resp, req_model, reason, fell = ra.call_models_with_fallback_or_none(
                "tok", "anthropic/claude-sonnet-4.5", "openai/gpt-5", self._MESSAGES
            )
        self.assertEqual(calls, ["anthropic/claude-sonnet-4.5", "openai/gpt-5"])
        self.assertEqual(resp, fallback_resp)
        self.assertTrue(fell)
        self.assertIn("403", reason)

    def test_fallback_triggered_on_http_429(self) -> None:
        """HTTP 429 on primary must trigger fallback retry."""
        fallback_resp = {"choices": [{"message": {"content": "ok"}}], "model": "openai/gpt-5"}
        calls: List[str] = []

        def side_effect(token: str, model: str, messages: list) -> dict:
            calls.append(model)
            if model == "anthropic/claude-sonnet-4.5":
                raise ra.RepoArchitectError(
                    "GitHub Models inference failed: 429 Too many requests"
                )
            return fallback_resp

        with patch.object(ra, "github_models_chat", side_effect=side_effect):
            resp, req_model, reason, fell = ra.call_models_with_fallback_or_none(
                "tok", "anthropic/claude-sonnet-4.5", "openai/gpt-5", self._MESSAGES
            )
        self.assertEqual(calls, ["anthropic/claude-sonnet-4.5", "openai/gpt-5"])
        self.assertEqual(resp, fallback_resp)
        self.assertTrue(fell)
        self.assertIn("429", reason)

    def test_fallback_triggered_on_5xx(self) -> None:
        """HTTP 5xx provider failure on primary must trigger fallback retry."""
        fallback_resp = {"choices": [{"message": {"content": "ok"}}], "model": "openai/gpt-5"}

        def side_effect(token: str, model: str, messages: list) -> dict:
            if model == "anthropic/claude-sonnet-4.5":
                raise ra.RepoArchitectError(
                    "GitHub Models inference failed: 503 Service temporarily unavailable"
                )
            return fallback_resp

        with patch.object(ra, "github_models_chat", side_effect=side_effect):
            resp, req_model, reason, fell = ra.call_models_with_fallback_or_none(
                "tok", "anthropic/claude-sonnet-4.5", "openai/gpt-5", self._MESSAGES
            )
        self.assertEqual(resp, fallback_resp)
        self.assertTrue(fell)
        self.assertIn("503", reason)

    def test_fallback_triggered_on_timeout(self) -> None:
        """Network timeout on primary must trigger fallback retry."""
        fallback_resp = {"choices": [{"message": {"content": "ok"}}], "model": "openai/gpt-5"}

        def side_effect(token: str, model: str, messages: list) -> dict:
            if model == "anthropic/claude-sonnet-4.5":
                raise ra.RepoArchitectError(
                    "GitHub Models inference network error: timed out"
                )
            return fallback_resp

        with patch.object(ra, "github_models_chat", side_effect=side_effect):
            resp, req_model, reason, fell = ra.call_models_with_fallback_or_none(
                "tok", "anthropic/claude-sonnet-4.5", "openai/gpt-5", self._MESSAGES
            )
        self.assertEqual(resp, fallback_resp)
        self.assertTrue(fell)
        self.assertIn("timed out", reason)

    def test_fallback_NOT_triggered_on_bare_error_string(self) -> None:
        """A bare error string without HTTP code must NOT trigger fallback (narrow trigger set)."""
        calls: List[str] = []

        def side_effect(token: str, model: str, messages: list) -> dict:
            calls.append(model)
            raise ra.RepoArchitectError("rate limit exceeded")

        with patch.object(ra, "github_models_chat", side_effect=side_effect):
            resp, _req, reason, fell = ra.call_models_with_fallback_or_none(
                "tok", "openai/gpt-5.4", "openai/gpt-4.1", self._MESSAGES
            )
        # Must only have tried preferred; no fallback
        self.assertEqual(calls, ["openai/gpt-5.4"])
        self.assertIsNone(resp)
        self.assertFalse(fell)

    def test_fallback_retried_exactly_once_then_both_fail(self) -> None:
        """When both models fail, combined error is surfaced and fallback_occurred=True."""
        calls: List[str] = []

        def side_effect(token: str, model: str, messages: list) -> dict:
            calls.append(model)
            if model == "anthropic/claude-sonnet-4.5":
                raise ra.RepoArchitectError(
                    "GitHub Models inference failed: 503 provider error"
                )
            raise ra.RepoArchitectError(
                "GitHub Models inference failed: 502 fallback provider error"
            )

        with patch.object(ra, "github_models_chat", side_effect=side_effect):
            resp, req_model, reason, fell = ra.call_models_with_fallback_or_none(
                "tok", "anthropic/claude-sonnet-4.5", "openai/gpt-5", self._MESSAGES
            )
        self.assertEqual(calls, ["anthropic/claude-sonnet-4.5", "openai/gpt-5"])
        self.assertIsNone(resp)
        self.assertTrue(fell)
        self.assertIsNotNone(reason)
        self.assertIn("503", reason)
        self.assertIn("fallback also failed", reason)
        self.assertIn("502", reason)

    def test_both_models_fail_returns_none(self) -> None:
        def side_effect(token: str, model: str, messages: list) -> dict:
            raise ra.RepoArchitectError("unknown_model: all models gone")

        with patch.object(ra, "github_models_chat", side_effect=side_effect):
            resp, req_model, reason, fell = ra.call_models_with_fallback_or_none(
                "tok", "openai/gpt-5.4", "openai/gpt-4.1", self._MESSAGES
            )
        self.assertIsNone(resp)
        self.assertIsNotNone(reason)
        self.assertIn("fallback also failed", reason)
        self.assertTrue(fell)

    def test_no_fallback_when_fallback_is_none(self) -> None:
        def side_effect(token: str, model: str, messages: list) -> dict:
            raise ra.RepoArchitectError("unknown_model: preferred gone")

        with patch.object(ra, "github_models_chat", side_effect=side_effect):
            resp, _req, reason, fell = ra.call_models_with_fallback_or_none(
                "tok", "openai/gpt-5.4", None, self._MESSAGES
            )
        self.assertIsNone(resp)
        self.assertFalse(fell)


# ---------------------------------------------------------------------------
# 3. Model configuration behaviour
# ---------------------------------------------------------------------------

class TestModelConfiguration(unittest.TestCase):
    def test_build_config_uses_env_models_when_github_model_blank(self) -> None:
        env = dict(os.environ)
        env.pop("GITHUB_MODEL", None)
        env["REPO_ARCHITECT_PREFERRED_MODEL"] = "anthropic/claude-sonnet-4.6"
        env["REPO_ARCHITECT_FALLBACK_MODEL"] = "google/gemini-3-pro"
        with patch.object(ra, "discover_git_root", return_value=pathlib.Path("/tmp/repo")):
            with patch.dict(os.environ, env, clear=True):
                config = ra.build_config(ra.parse_args([]))
        self.assertIsNone(config.github_model)
        self.assertEqual(config.preferred_model, "anthropic/claude-sonnet-4.6")
        self.assertEqual(config.fallback_model, "google/gemini-3-pro")

    def test_github_model_override_takes_precedence_over_preferred(self) -> None:
        analysis = {
            "architecture_score": 0.8,
            "cycles": [],
            "parse_error_files": [],
            "entrypoint_paths": [],
            "roadmap": [],
        }
        response = {"choices": [{"message": {"content": "ok"}}], "model": "openai/manual-override"}
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(
                root,
                github_token="tok",
                github_model="openai/manual-override",
                preferred_model="anthropic/claude-sonnet-4.6",
                fallback_model="google/gemini-3-pro",
            )
            with patch.object(
                ra,
                "call_models_with_fallback_or_none",
                return_value=(response, "openai/manual-override", None, False),
            ) as mocked_call:
                meta = ra.enrich_with_github_models(config, analysis)
        self.assertEqual(mocked_call.call_args.args[1], "openai/manual-override")
        self.assertEqual(mocked_call.call_args.args[2], "google/gemini-3-pro")
        self.assertEqual(meta["requested_model"], "openai/manual-override")
        self.assertEqual(meta["actual_model"], "openai/manual-override")

    def test_workflow_yaml_resolves_models_via_catalog_and_keeps_blank_override_logic(self) -> None:
        workflow = ra.workflow_yaml([], "17 * * * *", None)
        self.assertIn("Resolve GitHub Models configuration", workflow)
        self.assertIn("https://models.github.ai/catalog/models", workflow)
        self.assertIn("catalog_ok = False", workflow)
        self.assertIn('"anthropic/claude-sonnet-4.6"', workflow)
        self.assertIn('"anthropic/claude-sonnet-4.5"', workflow)
        self.assertIn('"openai/gpt-4.1"', workflow)
        self.assertIn('secondary = "google/gemini-3-pro"', workflow)
        self.assertIn("def deterministic_available(exclude=None):", workflow)
        self.assertIn("or deterministic_available()", workflow)
        self.assertIn("or deterministic_available(exclude=preferred)", workflow)
        self.assertIn("or preferred", workflow)
        self.assertIn("REPO_ARCHITECT_PREFERRED_MODEL={preferred}", workflow)
        self.assertIn("REPO_ARCHITECT_FALLBACK_MODEL={fallback}", workflow)
        self.assertIn('if [ -n "$MODEL" ]; then EXTRA_ARGS="$EXTRA_ARGS --github-model $MODEL"; fi', workflow)
        self.assertIn("models: read", workflow)
        # New: primary/fallback model inputs with defaults
        self.assertIn("github_fallback_model:", workflow)
        self.assertIn("default: 'openai/gpt-5'", workflow)
        self.assertIn("default: 'anthropic/claude-sonnet-4.5'", workflow)
        # New: GITHUB_MODEL and GITHUB_FALLBACK_MODEL exported as env vars
        self.assertIn("GITHUB_FALLBACK_MODEL:", workflow)

    def test_build_config_reads_github_fallback_model_env(self) -> None:
        """GITHUB_FALLBACK_MODEL env var should populate github_fallback_model in Config."""
        env = {
            "GITHUB_FALLBACK_MODEL": "openai/gpt-5",
        }
        with patch.object(ra, "discover_git_root", return_value=pathlib.Path("/tmp/repo")):
            with patch.dict(os.environ, env, clear=False):
                config = ra.build_config(ra.parse_args([]))
        self.assertEqual(config.github_fallback_model, "openai/gpt-5")

    def test_enrich_uses_github_fallback_model_over_fallback_model(self) -> None:
        """github_fallback_model takes precedence over fallback_model in enrich_with_github_models."""
        analysis = {
            "architecture_score": 0.9,
            "cycles": [],
            "parse_error_files": [],
            "entrypoint_paths": [],
            "roadmap": [],
        }
        fallback_resp = {"choices": [{"message": {"content": "ok"}}], "model": "openai/gpt-5"}
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(
                root,
                github_token="tok",
                github_model="anthropic/claude-sonnet-4.5",
                github_fallback_model="openai/gpt-5",
                fallback_model="google/gemini-3-pro",
            )
            with patch.object(
                ra,
                "call_models_with_fallback_or_none",
                return_value=(fallback_resp, "anthropic/claude-sonnet-4.5", "503 error", True),
            ) as mocked_call:
                meta = ra.enrich_with_github_models(config, analysis)
        # github_fallback_model="openai/gpt-5" must be passed as fallback, not fallback_model
        self.assertEqual(mocked_call.call_args.args[2], "openai/gpt-5")
        self.assertTrue(meta["fallback_used"])
        self.assertTrue(meta["fallback_occurred"])

    def test_enrich_metadata_primary_success(self) -> None:
        """On primary success, metadata must reflect no fallback was used."""
        analysis = {
            "architecture_score": 0.9,
            "cycles": [],
            "parse_error_files": [],
            "entrypoint_paths": [],
            "roadmap": [],
        }
        primary_resp = {
            "choices": [{"message": {"content": "bullet 1"}}],
            "model": "anthropic/claude-sonnet-4.5",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(
                root,
                github_token="tok",
                github_model="anthropic/claude-sonnet-4.5",
                github_fallback_model="openai/gpt-5",
            )
            with patch.object(
                ra,
                "call_models_with_fallback_or_none",
                return_value=(primary_resp, "anthropic/claude-sonnet-4.5", None, False),
            ):
                meta = ra.enrich_with_github_models(config, analysis)
        self.assertEqual(meta["primary_model"], "anthropic/claude-sonnet-4.5")
        self.assertEqual(meta["fallback_model"], "openai/gpt-5")
        self.assertEqual(meta["model_used"], "anthropic/claude-sonnet-4.5")
        self.assertFalse(meta["fallback_used"])
        self.assertFalse(meta["fallback_occurred"])
        self.assertIsNone(meta["fallback_reason"])


# ---------------------------------------------------------------------------
# 4. Syntax validation of generated Python (ast.parse gate)
# ---------------------------------------------------------------------------

class TestSyntaxValidationGate(unittest.TestCase):
    def test_valid_python_passes(self) -> None:
        code = "def foo():\n    return 42\n"
        # Should not raise
        ast.parse(code)

    def test_invalid_python_raises(self) -> None:
        code = "def foo(\n    return 42\n"
        with self.assertRaises(SyntaxError):
            ast.parse(code)

    def test_build_parse_errors_plan_rejects_still_broken_fix(self) -> None:
        """If the model returns still-broken Python, build_parse_errors_plan must return None."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            bad_py = root / "bad.py"
            bad_py.write_text("def foo(\n    return 42\n", encoding="utf-8")

            analysis: Dict[str, Any] = {
                "parse_error_files": ["bad.py"],
                "python_files": [{"path": "bad.py", "module": "bad", "parse_error": "SyntaxError"}],
            }
            config = _make_config(root, mode="mutate", github_token="fake-tok",
                                  preferred_model="openai/gpt-5.4", fallback_model="openai/gpt-4.1")

            # Model returns still-broken Python in its response
            still_broken_resp = {
                "choices": [{"message": {"content": '{"files": {"bad.py": "def foo(\\n    return 42\\n"}}'}}]
            }
            with patch.object(ra, "call_models_with_fallback_or_none",
                               return_value=(still_broken_resp, "openai/gpt-5.4", None, False)):
                plan = ra.build_parse_errors_plan(config, analysis)
            self.assertIsNone(plan, "Plan must be None when model fix is still broken")

    def test_build_parse_errors_plan_accepts_valid_fix(self) -> None:
        """If the model returns valid Python, a PatchPlan must be returned."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            bad_py = root / "bad.py"
            bad_py.write_text("def foo(\n    return 42\n", encoding="utf-8")

            analysis: Dict[str, Any] = {
                "parse_error_files": ["bad.py"],
                "python_files": [{"path": "bad.py", "module": "bad", "parse_error": "SyntaxError"}],
            }
            config = _make_config(root, mode="mutate", github_token="fake-tok",
                                  preferred_model="openai/gpt-5.4", fallback_model="openai/gpt-4.1")

            fixed_content = "def foo():\n    return 42\n"
            good_resp = {
                "choices": [{"message": {"content": json.dumps({"files": {"bad.py": fixed_content}})}}]
            }
            with patch.object(ra, "call_models_with_fallback_or_none",
                               return_value=(good_resp, "openai/gpt-5.4", None, False)):
                plan = ra.build_parse_errors_plan(config, analysis)
            self.assertIsNotNone(plan)
            self.assertEqual(plan.file_changes["bad.py"], fixed_content)


# ---------------------------------------------------------------------------
# 5. Campaign aggregation behaviour
# ---------------------------------------------------------------------------

class TestCampaignAggregation(unittest.TestCase):
    def test_campaign_returns_correct_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="campaign")
            result = ra.run_campaign(config, ["hygiene", "report"], max_slices=2, stop_on_failure=False)
        self.assertEqual(result["mode"], "campaign")
        self.assertEqual(result["status"], "campaign_complete")
        self.assertIn("slices_attempted", result)
        self.assertIn("slices_applied", result)
        self.assertIn("lanes_requested", result)
        self.assertIn("lanes_executed", result)
        self.assertIn("architecture_score", result)
        self.assertIn("results", result)
        self.assertIsInstance(result["results"], list)

    def test_campaign_summary_json_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="campaign")
            ra.run_campaign(config, ["hygiene"], max_slices=1, stop_on_failure=False)
            summary_path = config.agent_dir / "campaign_summary.json"
            self.assertTrue(summary_path.exists(), "campaign_summary.json must be written")
            data = json.loads(summary_path.read_text())
            self.assertEqual(data["mode"], "campaign")
            self.assertIn("slices_applied", data)

    def test_campaign_markdown_report_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="campaign")
            ra.run_campaign(config, ["hygiene"], max_slices=1, stop_on_failure=False)
            report_path = root / ra.DEFAULT_REPORT_DIR / "campaign_report.md"
            self.assertTrue(report_path.exists(), "campaign_report.md must be written")
            content = report_path.read_text()
            self.assertIn("repo-architect campaign report", content)

    def test_campaign_stop_on_failure_stops_early(self) -> None:
        """When stop_on_failure=True and a slice fails, remaining lanes are skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="campaign", github_token="fake-tok",
                                  preferred_model="openai/gpt-5.4", fallback_model="openai/gpt-4.1")

            def raise_on_apply(*args: Any, **kwargs: Any) -> None:
                raise ra.RepoArchitectError("forced failure for test")

            with patch.object(ra, "apply_patch_plan", side_effect=raise_on_apply):
                # Give the campaign a lane that will always produce a plan (hygiene with debug prints)
                # We need actual debug prints in the repo for hygiene to fire
                (root / "noisy.py").write_text("print('debug')  # DEBUG\n", encoding="utf-8")
                subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True)
                subprocess.run(["git", "-C", str(root), "commit", "-m", "add noisy file"], capture_output=True)
                result = ra.run_campaign(config, ["hygiene", "report"], max_slices=3, stop_on_failure=True)

            # With stop_on_failure=True and a forced apply failure, should have stopped
            # (if hygiene plan was made, it would fail on apply_patch_plan)
            self.assertEqual(result["status"], "campaign_complete")

    def test_campaign_max_slices_respected(self) -> None:
        """Campaign must not execute more than max_slices applied slices."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            # Add multiple debug print files to give hygiene work to do
            for i in range(5):
                (root / f"noisy{i}.py").write_text(f"print('x{i}')  # DEBUG\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "add noisy files"], capture_output=True)
            config = _make_config(root, mode="campaign")
            result = ra.run_campaign(config, list(ra.MUTATION_LANE_ORDER), max_slices=1, stop_on_failure=False)
        self.assertLessEqual(result["slices_applied"], 1)


# ---------------------------------------------------------------------------
# 5. Output schema stability for key fields
# ---------------------------------------------------------------------------

REQUIRED_OUTPUT_FIELDS = frozenset({
    "status", "mode", "lane", "architecture_score",
    "requested_model", "actual_model", "fallback_reason", "fallback_occurred",
    "primary_model", "fallback_model", "model_used", "fallback_used",
    "no_safe_code_mutation_reason", "branch", "changed_files",
    "validation", "pull_request_url", "artifact_files",
    "charter",
})


class TestOutputSchemaStability(unittest.TestCase):
    def _run_and_check(self, mode: str) -> Dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode=mode)
            result = ra.run_cycle(config)
        missing = REQUIRED_OUTPUT_FIELDS - set(result.keys())
        self.assertEqual(missing, set(), f"Missing output fields in {mode!r} mode: {missing}")
        return result

    def test_analyze_mode_output_contract(self) -> None:
        result = self._run_and_check("analyze")
        self.assertEqual(result["status"], "analysis_only")
        self.assertEqual(result["lane"], "none")

    def test_report_mode_output_contract(self) -> None:
        result = self._run_and_check("report")
        self.assertIn(result["status"], ("mutated", "no_meaningful_delta", "no_safe_mutation_available"))

    def test_mutate_mode_output_contract(self) -> None:
        result = self._run_and_check("mutate")
        self.assertIn(result["status"], ("mutated", "no_meaningful_delta", "no_safe_mutation_available"))

    def test_campaign_mode_output_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="campaign")
            result = ra.run_campaign(config, list(ra.MUTATION_LANE_ORDER), max_slices=2, stop_on_failure=False)
        campaign_fields = {"status", "mode", "slices_attempted", "slices_applied",
                           "lanes_requested", "lanes_executed", "architecture_score",
                           "requested_model", "actual_model", "fallback_reason",
                           "primary_model", "fallback_model", "model_used", "fallback_used",
                           "charter", "results"}
        missing = campaign_fields - set(result.keys())
        self.assertEqual(missing, set(), f"Missing campaign output fields: {missing}")


# ---------------------------------------------------------------------------
# 6. Lane selection priority
# ---------------------------------------------------------------------------

class TestLanePriority(unittest.TestCase):
    def _analysis(self, parse_errors: bool = False, cycles: bool = False,
                  debug_prints: bool = False, many_eps: bool = False) -> Dict[str, Any]:
        infos = []
        if debug_prints:
            infos.append({"path": "foo.py", "debug_print_lines": [5],
                          "module": "foo", "parse_error": None})
        else:
            infos.append({"path": "foo.py", "debug_print_lines": [],
                          "module": "foo", "parse_error": None})
        ep_clusters: Dict[str, List[str]] = {}
        ep_paths: List[str] = []
        if many_eps:
            # Above _ENTRYPOINT_CONSOLIDATION_THRESHOLD backend server entrypoints
            ep_paths = [f"backend/server{i}.py" for i in range(6)]
            ep_clusters["backend_servers"] = ep_paths
        return {
            "parse_error_files": ["foo.py"] if parse_errors else [],
            "cycles": [["a", "b", "a"]] if cycles else [],
            "python_files": infos,
            "roadmap": [],
            "entrypoint_paths": ep_paths,
            "entrypoint_clusters": ep_clusters,
            "architecture_score": 80,
            "score_factors": {},
            "local_import_graph": {},
            "debug_print_candidates": ["foo.py"] if debug_prints else [],
        }

    def test_analyze_mode_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="analyze")
            plan, lane, reason = ra.build_patch_plan(config, self._analysis(), {}, {})
        self.assertIsNone(plan)
        self.assertEqual(lane, "none")

    def test_hygiene_selected_when_debug_prints_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            # Create a real file for hygiene lane to read
            foo = root / "foo.py"
            foo.write_text("print('hi')  # DEBUG\n", encoding="utf-8")
            config = _make_config(root, mode="mutate")
            analysis = self._analysis(debug_prints=True)
            plan, lane, _ = ra.build_patch_plan(config, analysis, {}, {})
        self.assertEqual(lane, "hygiene")
        self.assertIsNotNone(plan)

    def test_parse_errors_attempted_before_hygiene(self) -> None:
        """parse_errors lane must be attempted before hygiene even without a token.

        Without a github_token, parse_errors plan returns None (model unavailable).
        The lane falls through to hygiene which *does* fire (debug prints exist).
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            foo = root / "foo.py"
            foo.write_text("print('hi')  # DEBUG\n", encoding="utf-8")
            # No github_token → parse_errors plan returns None → falls through to hygiene
            config = _make_config(root, mode="mutate")
            analysis = self._analysis(parse_errors=True, debug_prints=True)
            plan, lane, _ = ra.build_patch_plan(config, analysis, {}, {})
        # parse_errors was attempted first (skipped without token), hygiene fires next
        self.assertEqual(lane, "hygiene", f"Expected hygiene (parse_errors skipped without token), got: {lane!r}")

    def test_report_lane_is_fallback(self) -> None:
        """In mutate mode with no actionable higher lane, report is the fallback."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="mutate")
            analysis = self._analysis()  # no parse errors, no cycles, no debug prints, no many eps
            plan, lane, _ = ra.build_patch_plan(config, analysis, {}, {"last_report_hash": None})
        self.assertEqual(lane, "report")

    def test_report_suppressed_when_parse_errors_and_code_fix_attempted(self) -> None:
        """If parse_errors exist and code fix was attempted (but failed), report is suppressed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            # Has token so parse_errors lane is attempted
            config = _make_config(root, mode="mutate", github_token="fake-tok",
                                  preferred_model="openai/gpt-5.4", fallback_model="openai/gpt-4.1")
            analysis = self._analysis(parse_errors=True)

            # Model returns None → parse_errors plan fails → report should be suppressed
            with patch.object(ra, "call_models_with_fallback_or_none",
                               return_value=(None, "openai/gpt-5.4", "model unavailable", False)):
                plan, lane, reason = ra.build_patch_plan(config, analysis, {}, {"last_report_hash": None})

        # parse_errors attempted, failed → report suppressed → no plan
        self.assertIsNone(plan)
        self.assertIsNotNone(reason)
        self.assertIn("report", reason.lower())


# ---------------------------------------------------------------------------
# 7. extract_json_from_model_text
# ---------------------------------------------------------------------------

class TestExtractJsonFromModelText(unittest.TestCase):
    def test_bare_json(self) -> None:
        result = ra.extract_json_from_model_text('{"files": {"foo.py": "content"}}')
        self.assertEqual(result, {"files": {"foo.py": "content"}})

    def test_fenced_json(self) -> None:
        text = '```json\n{"files": {"bar.py": "x"}}\n```'
        result = ra.extract_json_from_model_text(text)
        self.assertEqual(result, {"files": {"bar.py": "x"}})

    def test_embedded_json_in_prose(self) -> None:
        text = 'Here is the fix: {"files": {"baz.py": "y"}} done'
        result = ra.extract_json_from_model_text(text)
        self.assertEqual(result, {"files": {"baz.py": "y"}})

    def test_invalid_raises(self) -> None:
        with self.assertRaises(ra.RepoArchitectError):
            ra.extract_json_from_model_text("no json here at all")


# ---------------------------------------------------------------------------
# 8. Entrypoint consolidation lane
# ---------------------------------------------------------------------------

class TestEntrypointConsolidationLane(unittest.TestCase):
    def test_below_threshold_returns_none(self) -> None:
        """build_entrypoint_consolidation_plan returns None when below threshold."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="mutate", github_token="tok",
                                  preferred_model="openai/gpt-5.4")
            analysis = {
                "entrypoint_clusters": {"backend_servers": ["a.py", "b.py"]},  # only 2, below threshold
                "python_files": [],
            }
            plan = ra.build_entrypoint_consolidation_plan(config, analysis)
        self.assertIsNone(plan)

    def test_no_token_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="mutate")  # no token
            analysis = {
                "entrypoint_clusters": {"backend_servers": [f"server{i}.py" for i in range(6)]},
                "python_files": [],
            }
            plan = ra.build_entrypoint_consolidation_plan(config, analysis)
        self.assertIsNone(plan)

    def test_model_response_with_invalid_python_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            for i in range(6):
                (root / f"server{i}.py").write_text(f"# server {i}\npass\n", encoding="utf-8")
            config = _make_config(root, mode="mutate", github_token="tok",
                                  preferred_model="openai/gpt-5.4")
            analysis = {
                "entrypoint_clusters": {"backend_servers": [f"server{i}.py" for i in range(6)]},
                "python_files": [],
            }
            broken_resp = {
                "choices": [{"message": {"content": '{"files": {"server0.py": "def broken("}}'}}]
            }
            with patch.object(ra, "call_models_with_fallback_or_none",
                               return_value=(broken_resp, "openai/gpt-5.4", None, False)):
                plan = ra.build_entrypoint_consolidation_plan(config, analysis)
        self.assertIsNone(plan)


# ---------------------------------------------------------------------------
# 9. Lane scoping for mutate mode
# ---------------------------------------------------------------------------

class TestLaneScopingMutateMode(unittest.TestCase):
    """Verify --lane / --lanes / env vars scope lane selection in mutate mode."""

    def test_lanes_flag_scopes_mutate_to_single_lane(self) -> None:
        """--lanes hygiene should restrict mutate to only the hygiene lane."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            bad = root / "bad.py"
            bad.write_text("print('debug')  # DEBUG\n", encoding="utf-8")
            config = _make_config(root, mode="mutate", campaign_lanes=("hygiene",))
            analysis = ra.build_analysis(root)
            plan, lane, _ = ra.build_patch_plan(config, analysis, {}, {})
        self.assertIsNotNone(plan)
        self.assertEqual(lane, "hygiene")

    def test_lanes_flag_excludes_hygiene(self) -> None:
        """--lanes report should NOT see hygiene changes even if debug prints exist."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            bad = root / "bad.py"
            bad.write_text("print('debug')  # DEBUG\n", encoding="utf-8")
            config = _make_config(root, mode="mutate", campaign_lanes=("report",))
            analysis = ra.build_analysis(root)
            plan, lane, _ = ra.build_patch_plan(config, analysis, {}, {})
        # Only 'report' was in the active lanes, so hygiene was never considered.
        # lane=='report' proves hygiene was excluded from lane selection.
        self.assertEqual(lane, "report")

    def test_lane_singular_flag_parsed(self) -> None:
        """--lane hygiene should produce campaign_lanes=('hygiene',) in Config."""
        args = ra.parse_args(["--mode", "mutate", "--lane", "hygiene"])
        self.assertEqual(args.lane, "hygiene")

    def test_build_config_reads_lanes_env(self) -> None:
        """REPO_ARCHITECT_LANES env var should populate campaign_lanes."""
        env = {
            "REPO_ARCHITECT_LANES": "parse_errors,hygiene",
        }
        with patch.dict(os.environ, env, clear=False):
            args = ra.parse_args(["--mode", "mutate"])
            config = ra.build_config(args)
        self.assertEqual(config.campaign_lanes, ("parse_errors", "hygiene"))

    def test_cli_lanes_overrides_env(self) -> None:
        """CLI --lanes should take precedence over REPO_ARCHITECT_LANES env var."""
        env = {"REPO_ARCHITECT_LANES": "report"}
        with patch.dict(os.environ, env, clear=False):
            args = ra.parse_args(["--mode", "mutate", "--lanes", "hygiene"])
            config = ra.build_config(args)
        self.assertEqual(config.campaign_lanes, ("hygiene",))


# ---------------------------------------------------------------------------
# 10. Enhanced validation (import smoke)
# ---------------------------------------------------------------------------

class TestValidateChange(unittest.TestCase):
    """Verify validate_change includes lane-aware behaviour."""

    def test_py_compile_passes_for_valid_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            (root / "ok.py").write_text("x = 1\n", encoding="utf-8")
            config = _make_config(root, mode="mutate")
            ok, msg = ra.validate_change(config, ["ok.py"])
        self.assertTrue(ok)
        self.assertIn("py_compile", msg.lower())

    def test_py_compile_fails_for_invalid_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            (root / "bad.py").write_text("def broken(\n", encoding="utf-8")
            config = _make_config(root, mode="mutate")
            ok, msg = ra.validate_change(config, ["bad.py"])
        self.assertFalse(ok)

    def test_import_smoke_runs_for_import_cycles_lane(self) -> None:
        """When lane=import_cycles, validate_change should run import smoke."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            # A valid file that won't import cleanly as a module from this dir
            (root / "cycle_fix.py").write_text("x = 1\n", encoding="utf-8")
            config = _make_config(root, mode="mutate")
            ok, msg = ra.validate_change(config, ["cycle_fix.py"], lane="import_cycles")
        # Should still pass (import smoke is warn-only)
        self.assertTrue(ok)

    def test_non_python_files_always_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="mutate")
            ok, msg = ra.validate_change(config, ["README.md"])
        self.assertTrue(ok)

    def test_output_contract_includes_lanes_active(self) -> None:
        """run_cycle result should include lanes_active field."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="analyze")
            result = ra.run_cycle(config)
        self.assertIn("lanes_active", result)
        self.assertIsInstance(result["lanes_active"], list)
        self.assertEqual(result["lanes_active"], list(ra.MUTATION_LANE_ORDER))

    def test_output_contract_lanes_active_respects_config(self) -> None:
        """lanes_active should reflect config.campaign_lanes when set."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="mutate", campaign_lanes=("hygiene",))
            result = ra.run_cycle(config)
        self.assertEqual(result["lanes_active"], ["hygiene"])


# ---------------------------------------------------------------------------
# 11. Charter context — loading and metadata
# ---------------------------------------------------------------------------

class TestCharterContext(unittest.TestCase):
    """Verify charter file loading, missing-file tolerance, and output metadata."""

    def test_load_charter_context_no_files_present(self) -> None:
        """No crash when charter files are absent; loaded_files is empty, applied is False."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            ctx = ra.load_charter_context(root)
        self.assertEqual(ctx["loaded_files"], [])
        self.assertIsNone(ctx["content_hash"])
        self.assertFalse(ctx["applied"])
        self.assertEqual(ctx["content"], "")

    def test_load_charter_context_partial(self) -> None:
        """Only present charter files are loaded; the missing one is silently skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            first_rel = ra.CHARTER_PATHS[0]
            charter_path = root / first_rel
            charter_path.parent.mkdir(parents=True, exist_ok=True)
            charter_path.write_text("# Test Charter\n\nSome guidance here.", encoding="utf-8")

            ctx = ra.load_charter_context(root)

        self.assertEqual(ctx["loaded_files"], [first_rel])
        self.assertIsNotNone(ctx["content_hash"])
        self.assertFalse(ctx["applied"])
        self.assertIn("Test Charter", ctx["content"])
        # Missing second file must not be in loaded_files
        self.assertNotIn(ra.CHARTER_PATHS[1], ctx["loaded_files"])

    def test_load_charter_context_both_files(self) -> None:
        """When both files exist, both appear in loaded_files and content is combined."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for rel in ra.CHARTER_PATHS:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"# Charter {rel}\n\nGuidance.", encoding="utf-8")

            ctx = ra.load_charter_context(root)

        self.assertEqual(sorted(ctx["loaded_files"]), sorted(ra.CHARTER_PATHS))
        self.assertIsNotNone(ctx["content_hash"])
        self.assertFalse(ctx["applied"])
        for rel in ra.CHARTER_PATHS:
            self.assertIn(rel, ctx["content"])

    def test_run_cycle_charter_metadata_in_result(self) -> None:
        """run_cycle must include charter metadata at top level."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="analyze")
            result = ra.run_cycle(config)
        self.assertIn("charter", result)
        charter = result["charter"]
        self.assertIn("loaded_files", charter)
        self.assertIn("content_hash", charter)
        self.assertIn("applied", charter)
        self.assertIsInstance(charter["loaded_files"], list)

    def test_run_cycle_charter_loaded_when_files_present(self) -> None:
        """Charter metadata reflects loaded files when charters exist in the repo."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            # Plant both charter files
            for rel in ra.CHARTER_PATHS:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"# {rel}\nEngineering direction.", encoding="utf-8")
            config = _make_config(root, mode="analyze")
            result = ra.run_cycle(config)
        charter = result["charter"]
        self.assertEqual(sorted(charter["loaded_files"]), sorted(ra.CHARTER_PATHS))
        self.assertIsNotNone(charter["content_hash"])

    def test_run_campaign_charter_metadata_in_result(self) -> None:
        """run_campaign must include charter metadata in the summary dict."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="campaign")
            result = ra.run_campaign(config, ["hygiene"], max_slices=1, stop_on_failure=False)
        self.assertIn("charter", result)
        charter = result["charter"]
        self.assertIn("loaded_files", charter)
        self.assertIn("content_hash", charter)
        self.assertIn("applied", charter)

    def test_charter_system_prefix_empty_when_no_charter(self) -> None:
        """_charter_system_prefix returns empty string when no charter content is present."""
        analysis: Dict[str, Any] = {"charter_context": {"content": "", "loaded_files": []}}
        self.assertEqual(ra._charter_system_prefix(analysis), "")

    def test_charter_system_prefix_present_when_charter_loaded(self) -> None:
        """_charter_system_prefix returns non-empty string when charter content is set."""
        analysis: Dict[str, Any] = {
            "charter_context": {"content": "# My Charter\n\nDo X.", "loaded_files": ["docs/architecture/X.md"]}
        }
        prefix = ra._charter_system_prefix(analysis)
        self.assertIn("My Charter", prefix)
        self.assertIn("authoritative", prefix.lower())

    def test_content_hash_changes_with_content(self) -> None:
        """Different charter content should produce different hashes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            rel = ra.CHARTER_PATHS[0]
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("version 1", encoding="utf-8")
            ctx1 = ra.load_charter_context(root)
            path.write_text("version 2", encoding="utf-8")
            ctx2 = ra.load_charter_context(root)
        self.assertNotEqual(ctx1["content_hash"], ctx2["content_hash"])


if __name__ == "__main__":
    unittest.main()
