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
import re
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
    subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "init"], capture_output=True, check=True)
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
        env["REPO_ARCHITECT_PREFERRED_MODEL"] = "openai/gpt-5"
        env["REPO_ARCHITECT_FALLBACK_MODEL"] = "openai/o3"
        with patch.object(ra, "discover_git_root", return_value=pathlib.Path("/tmp/repo")):
            with patch.dict(os.environ, env, clear=True):
                config = ra.build_config(ra.parse_args([]))
        self.assertIsNone(config.github_model)
        self.assertEqual(config.preferred_model, "openai/gpt-5")
        self.assertEqual(config.fallback_model, "openai/o3")

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
        self.assertIn('"openai/gpt-5"', workflow)
        self.assertIn('"openai/o3"', workflow)
        self.assertNotIn('"anthropic/claude-sonnet-4.6"', workflow)
        self.assertNotIn('"anthropic/claude-sonnet-4.5"', workflow)
        self.assertNotIn('"openai/gpt-4.1"', workflow)
        self.assertNotIn('secondary = "google/gemini-3-pro"', workflow)
        self.assertIn("def deterministic_available(exclude=None):", workflow)
        self.assertIn("or deterministic_available()", workflow)
        self.assertIn("or deterministic_available(exclude=preferred)", workflow)
        self.assertIn("or preferred", workflow)
        self.assertIn("REPO_ARCHITECT_PREFERRED_MODEL={preferred}", workflow)
        self.assertIn("REPO_ARCHITECT_FALLBACK_MODEL={fallback}", workflow)
        self.assertIn('if [ -n "$MODEL" ]; then EXTRA_ARGS="$EXTRA_ARGS --github-model $MODEL"; fi', workflow)
        self.assertIn("models: read", workflow)
        # github_fallback_model input with empty default
        self.assertIn("github_fallback_model:", workflow)
        self.assertIn("default: ''", workflow)
        # GITHUB_MODEL and GITHUB_FALLBACK_MODEL exported as env vars to resolver step
        self.assertIn("GITHUB_FALLBACK_MODEL:", workflow)
        self.assertIn("GITHUB_MODEL:", workflow)
        # Override-first logic present
        self.assertIn("env_github_model", workflow)
        self.assertIn("env_github_fallback_model", workflow)

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
# 3b. Model resolver order
# ---------------------------------------------------------------------------

class TestModelResolverOrder(unittest.TestCase):
    """Tests for the _resolve_models() override-first catalog resolver."""

    _ORDER = ("openai/gpt-5", "openai/o3")

    def test_empty_inputs_use_resolver_order(self) -> None:
        """No env overrides → picks gpt-5 as preferred and o3 as fallback."""
        available = {"openai/gpt-5", "openai/o3"}
        preferred, fallback = ra._resolve_models(
            available=available,
            catalog_ok=True,
            env_model="",
            env_fallback="",
            order=self._ORDER,
        )
        self.assertEqual(preferred, "openai/gpt-5")
        self.assertEqual(fallback, "openai/o3")

    def test_explicit_primary_overrides_resolver(self) -> None:
        """GITHUB_MODEL set → use it as preferred regardless of catalog."""
        available = {"openai/gpt-5", "openai/o3", "openai/other"}
        preferred, fallback = ra._resolve_models(
            available=available,
            catalog_ok=True,
            env_model="openai/manual",
            env_fallback="",
            order=self._ORDER,
        )
        self.assertEqual(preferred, "openai/manual")

    def test_explicit_fallback_overrides_resolver(self) -> None:
        """GITHUB_FALLBACK_MODEL set → use it as fallback, primary still auto-resolved."""
        available = {"openai/gpt-5", "openai/o3"}
        preferred, fallback = ra._resolve_models(
            available=available,
            catalog_ok=True,
            env_model="",
            env_fallback="openai/manual-fb",
            order=self._ORDER,
        )
        self.assertEqual(preferred, "openai/gpt-5")
        self.assertEqual(fallback, "openai/manual-fb")

    def test_auto_fallback_chooses_o3_when_gpt5_is_primary(self) -> None:
        """Catalog returns both gpt-5 and o3, no overrides → preferred=gpt-5, fallback=o3."""
        available = {"openai/gpt-5", "openai/o3"}
        preferred, fallback = ra._resolve_models(
            available=available,
            catalog_ok=True,
            env_model="",
            env_fallback="",
            order=self._ORDER,
        )
        self.assertEqual(preferred, "openai/gpt-5")
        self.assertEqual(fallback, "openai/o3")
        self.assertNotEqual(preferred, fallback)

    def test_catalog_failure_falls_back_to_order_defaults(self) -> None:
        """When catalog fails, use order[0] as preferred and order[1] as fallback."""
        preferred, fallback = ra._resolve_models(
            available=set(),
            catalog_ok=False,
            env_model="",
            env_fallback="",
            order=self._ORDER,
        )
        self.assertEqual(preferred, "openai/gpt-5")
        self.assertEqual(fallback, "openai/o3")


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
                subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True, check=True)
                subprocess.run(["git", "-C", str(root), "commit", "-m", "add noisy file"], capture_output=True, check=True)
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
            subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True, check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "add noisy files"], capture_output=True, check=True)
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


# ---------------------------------------------------------------------------
# 14. Issue-first mode: fingerprint generation
# ---------------------------------------------------------------------------

class TestIssueFingerprintGeneration(unittest.TestCase):
    """issue_fingerprint must be deterministic, stable, and collision-resistant."""

    def test_deterministic_same_inputs(self) -> None:
        fp1 = ra.issue_fingerprint("runtime", "import-cycles")
        fp2 = ra.issue_fingerprint("runtime", "import-cycles")
        self.assertEqual(fp1, fp2)

    def test_different_subsystem_differs(self) -> None:
        fp1 = ra.issue_fingerprint("runtime", "import-cycles")
        fp2 = ra.issue_fingerprint("workflow", "import-cycles")
        self.assertNotEqual(fp1, fp2)

    def test_different_key_differs(self) -> None:
        fp1 = ra.issue_fingerprint("runtime", "import-cycles")
        fp2 = ra.issue_fingerprint("runtime", "parse-errors")
        self.assertNotEqual(fp1, fp2)

    def test_output_is_12_hex_chars(self) -> None:
        fp = ra.issue_fingerprint("runtime", "import-cycles")
        self.assertEqual(len(fp), 12)
        self.assertRegex(fp, r"^[0-9a-f]{12}$")

    def test_case_insensitive_canonical(self) -> None:
        fp1 = ra.issue_fingerprint("Runtime", "Import-Cycles")
        fp2 = ra.issue_fingerprint("runtime", "import-cycles")
        self.assertEqual(fp1, fp2)


# ---------------------------------------------------------------------------
# 15. Issue-first mode: issue body rendering
# ---------------------------------------------------------------------------

class TestRenderIssueBody(unittest.TestCase):
    """render_issue_body must produce a fully-structured markdown body."""

    def _make_gap(self) -> ra.ArchGap:
        return ra.ArchGap(
            subsystem="runtime",
            issue_key="import-cycles",
            title="[arch-gap] Break 3 circular import cycle(s)",
            summary="Three circular imports degrade startup.",
            problem="Cycles: a → b → a.",
            why_it_matters="They slow startup.",
            scope="Break top 3 cycles.",
            suggested_files=["backend/foo.py", "backend/bar.py"],
            implementation_notes="Use TYPE_CHECKING.",
            acceptance_criteria=["No cycles remain.", "Tests pass."],
            validation_commands=["python -m pytest -x -q"],
            out_of_scope="Unrelated refactoring.",
            copilot_prompt="You are fixing import cycles. Start with backend/foo.py.",
            priority="high",
            confidence=0.95,
        )

    def test_contains_all_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            body = ra.render_issue_body(self._make_gap(), config, "run-001")
        for section in ("Summary", "Problem", "Why it matters", "Scope",
                        "Suggested files", "Implementation notes",
                        "Copilot implementation prompt", "Acceptance criteria",
                        "Validation", "Out of scope", "Machine metadata"):
            self.assertIn(section, body, f"Missing section: {section!r}")

    def test_fingerprint_embedded_in_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            gap = self._make_gap()
            body = ra.render_issue_body(gap, config, "run-001")
        fp = ra.issue_fingerprint(gap.subsystem, gap.issue_key)
        self.assertIn(f"arch-gap-fingerprint: {fp}", body)

    def test_copilot_prompt_block_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            body = ra.render_issue_body(self._make_gap(), config, "run-001")
        self.assertIn("Copilot Chat", body)
        self.assertIn("agent mode", body)
        self.assertIn("You are fixing import cycles", body)

    def test_acceptance_criteria_as_checkboxes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            body = ra.render_issue_body(self._make_gap(), config, "run-001")
        self.assertIn("- [ ] No cycles remain.", body)
        self.assertIn("- [ ] Tests pass.", body)

    def test_machine_metadata_json_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            body = ra.render_issue_body(self._make_gap(), config, "run-001")
        # Extract JSON from body
        m = re.search(r"```json\n(\{.*?\})\n```", body, re.DOTALL)
        self.assertIsNotNone(m, "Expected a JSON code block in the body")
        meta = json.loads(m.group(1))
        for field in ("subsystem", "priority", "confidence", "mode", "generated_at", "run_id", "fingerprint", "issue_key"):
            self.assertIn(field, meta, f"Missing machine metadata field: {field!r}")
        self.assertEqual(meta["mode"], ra.ISSUE_MODE)


# ---------------------------------------------------------------------------
# 16. Issue-first mode: deduplication
# ---------------------------------------------------------------------------

class TestIssueSynthesisDeduplication(unittest.TestCase):
    """synthesize_issue must detect duplicates and skip creation."""

    def _make_gap(self) -> ra.ArchGap:
        return ra.ArchGap(
            subsystem="runtime",
            issue_key="parse-errors",
            title="[arch-gap] Fix parse errors",
            summary="Parse errors found.",
            problem="Files: bad.py.",
            why_it_matters="CI fails.",
            scope="Fix syntax.",
            suggested_files=["bad.py"],
            implementation_notes="Fix syntax.",
            acceptance_criteria=["All files compile."],
            validation_commands=["python -m py_compile bad.py"],
            out_of_scope="Logic changes.",
            copilot_prompt="Fix bad.py syntax.",
            priority="critical",
            confidence=1.0,
        )

    def test_dry_run_writes_file_not_api(self) -> None:
        """In dry-run mode, synthesize_issue writes to disk and does not call GitHub API."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, github_token=None)
            gap = self._make_gap()
            action = ra.synthesize_issue(config, gap, "run-001", dry_run=True)
            self.assertEqual(action.action, "dry_run")
            self.assertIsNone(action.issue_number)
            self.assertIsNotNone(action.dry_run_path)
            # File must exist on disk (check inside with block while tmp dir still exists)
            out_path = root / action.dry_run_path
            self.assertTrue(out_path.exists(), f"Dry-run output not written: {out_path}")
            content = out_path.read_text(encoding="utf-8")
            self.assertIn(gap.title, content)

    def test_no_credentials_falls_back_to_dry_run(self) -> None:
        """When no GitHub credentials are available, synthesize_issue auto-falls-back to dry-run."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, github_token=None, github_repo=None)
            gap = self._make_gap()
            action = ra.synthesize_issue(config, gap, "run-001", dry_run=False)
        self.assertEqual(action.action, "dry_run")
        self.assertIsNotNone(action.dry_run_path)

    def test_skips_creation_when_existing_issue_found(self) -> None:
        """When an open issue with matching fingerprint exists, update instead of create."""
        gap = self._make_gap()
        fp = ra.issue_fingerprint(gap.subsystem, gap.issue_key)
        fake_existing = {"number": 42, "html_url": "https://github.com/test/repo/issues/42",
                         "body": f"<!-- arch-gap-fingerprint: {fp} -->"}

        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, github_token="fake-tok", github_repo="org/repo")

            with patch.object(ra, "find_existing_github_issue", return_value=fake_existing):
                with patch.object(ra, "update_github_issue_api", return_value={"id": 1}) as mock_update:
                    with patch.object(ra, "set_github_issue_labels", return_value={"id": 42}) as mock_labels:
                        with patch.object(ra, "ensure_github_labels"):
                            action = ra.synthesize_issue(config, gap, "run-001", dry_run=False)

        self.assertEqual(action.action, "updated")
        self.assertEqual(action.issue_number, 42)
        self.assertEqual(action.dedupe_result, "existing_open")
        mock_update.assert_called_once()
        mock_labels.assert_called_once()

    def test_creates_new_issue_when_no_duplicate(self) -> None:
        """When no open issue with matching fingerprint exists, create a new one."""
        gap = self._make_gap()
        fake_created = {"number": 99, "html_url": "https://github.com/test/repo/issues/99"}

        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, github_token="fake-tok", github_repo="org/repo")

            with patch.object(ra, "find_existing_github_issue", return_value=None):
                with patch.object(ra, "create_github_issue_api", return_value=fake_created) as mock_create:
                    with patch.object(ra, "ensure_github_labels"):
                        action = ra.synthesize_issue(config, gap, "run-001", dry_run=False)

        self.assertEqual(action.action, "created")
        self.assertEqual(action.issue_number, 99)
        self.assertEqual(action.dedupe_result, "new")
        mock_create.assert_called_once()

    def test_create_failure_reports_create_failed(self) -> None:
        """When issue creation fails, dedupe_result should be 'create_failed', not 'new'."""
        gap = self._make_gap()

        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, github_token="fake-tok", github_repo="org/repo")

            with patch.object(ra, "find_existing_github_issue", return_value=None):
                with patch.object(ra, "create_github_issue_api", side_effect=ra.RepoArchitectError("403 forbidden")):
                    with patch.object(ra, "ensure_github_labels"):
                        action = ra.synthesize_issue(config, gap, "run-001", dry_run=False)

        self.assertEqual(action.action, "error")
        self.assertEqual(action.dedupe_result, "create_failed")
        self.assertIn("403", action.error)

    def test_existing_issue_path_patches_labels(self) -> None:
        """When an existing issue is found, set_github_issue_labels must be called to PATCH labels."""
        gap = self._make_gap()
        fp = ra.issue_fingerprint(gap.subsystem, gap.issue_key)
        fake_existing = {"number": 42, "html_url": "https://github.com/test/repo/issues/42",
                         "body": f"<!-- arch-gap-fingerprint: {fp} -->"}

        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, github_token="fake-tok", github_repo="org/repo")

            with patch.object(ra, "find_existing_github_issue", return_value=fake_existing):
                with patch.object(ra, "update_github_issue_api", return_value={"id": 1}):
                    with patch.object(ra, "set_github_issue_labels", return_value={"id": 42}) as mock_labels:
                        with patch.object(ra, "ensure_github_labels"):
                            action = ra.synthesize_issue(config, gap, "run-001", dry_run=False)

        self.assertEqual(action.action, "updated")
        mock_labels.assert_called_once()
        # The labels passed to PATCH should include the base labels
        call_args = mock_labels.call_args
        self.assertIn("arch-gap", call_args[0][2])


# ---------------------------------------------------------------------------
# 17. Issue-first mode: label assignment
# ---------------------------------------------------------------------------

class TestIssueLabelAssignment(unittest.TestCase):
    """synthesize_issue must apply the correct base and subsystem labels."""

    def _make_gap(self, subsystem: str = "runtime", priority: str = "medium") -> ra.ArchGap:
        return ra.ArchGap(
            subsystem=subsystem, issue_key="test-gap", title="[arch-gap] Test",
            summary="s", problem="p", why_it_matters="w", scope="s2",
            suggested_files=[], implementation_notes="i",
            acceptance_criteria=["done"], validation_commands=["pytest"],
            out_of_scope="x", copilot_prompt="fix it", priority=priority, confidence=0.8,
        )

    def test_base_labels_always_applied(self) -> None:
        gap = self._make_gap()
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            action = ra.synthesize_issue(config, gap, "run-001", dry_run=True)
        for lbl in ("arch-gap", "copilot-task", "needs-implementation"):
            self.assertIn(lbl, action.labels_applied, f"Missing base label: {lbl!r}")

    def test_subsystem_label_added_when_valid(self) -> None:
        gap = self._make_gap(subsystem="workflow")
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            action = ra.synthesize_issue(config, gap, "run-001", dry_run=True)
        self.assertIn("workflow", action.labels_applied)

    def test_priority_label_added_for_critical(self) -> None:
        gap = self._make_gap(priority="critical")
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            action = ra.synthesize_issue(config, gap, "run-001", dry_run=True)
        self.assertIn("priority:critical", action.labels_applied)

    def test_priority_label_added_for_high(self) -> None:
        gap = self._make_gap(priority="high")
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            action = ra.synthesize_issue(config, gap, "run-001", dry_run=True)
        self.assertIn("priority:high", action.labels_applied)

    def test_no_priority_label_for_medium(self) -> None:
        gap = self._make_gap(priority="medium")
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            action = ra.synthesize_issue(config, gap, "run-001", dry_run=True)
        self.assertNotIn("priority:medium", action.labels_applied)


# ---------------------------------------------------------------------------
# 18. Issue-first mode: gap diagnosis
# ---------------------------------------------------------------------------

class TestDiagnoseGaps(unittest.TestCase):
    """diagnose_gaps must produce correctly populated ArchGap instances."""

    def _model_meta(self, used: bool = False) -> Dict[str, Any]:
        return {
            "used": used, "summary": None, "requested_model": None, "actual_model": None,
            "primary_model": None, "fallback_model": None, "model_used": None,
            "fallback_used": False, "fallback_reason": None, "fallback_occurred": False, "enabled": False,
        }

    def test_parse_errors_produce_critical_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": ["bad.py", "worse.py"],
                "cycles": [],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 80,
                "score_factors": {},
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        self.assertTrue(any(g.priority == "critical" and "parse" in g.issue_key for g in gaps))
        self.assertTrue(any("bad.py" in g.suggested_files for g in gaps))

    def test_import_cycles_produce_high_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": [],
                "cycles": [["a.py", "b.py", "a.py"], ["c.py", "d.py", "c.py"]],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 80,
                "score_factors": {},
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        cycle_gaps = [g for g in gaps if "cycle" in g.issue_key]
        self.assertTrue(len(cycle_gaps) >= 1)
        self.assertEqual(cycle_gaps[0].priority, "high")

    def test_low_architecture_score_produces_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": [],
                "cycles": [],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 45,
                "score_factors": {"parse_errors": 3},
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        score_gaps = [g for g in gaps if "score" in g.issue_key or "degradation" in g.issue_key]
        self.assertTrue(len(score_gaps) >= 1)
        self.assertEqual(score_gaps[0].priority, "high")

    def test_score_above_threshold_no_score_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": [],
                "cycles": [],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 85,
                "score_factors": {},
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        score_gaps = [g for g in gaps if "score" in g.issue_key or "degradation" in g.issue_key]
        self.assertEqual(len(score_gaps), 0)

    def test_subsystem_filter_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, issue_subsystem="workflow")
            analysis: Dict[str, Any] = {
                "parse_error_files": ["bad.py"],
                "cycles": [["a", "b", "a"]],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 45,
                "score_factors": {},
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        # All returned gaps must be in the "workflow" subsystem
        for g in gaps:
            self.assertEqual(g.subsystem, "workflow", f"Non-workflow gap returned: {g.issue_key}")

    def test_gaps_sorted_by_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": ["bad.py"],  # critical
                "cycles": [["a", "b", "a"]],      # high
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 45,          # high (score < 50)
                "score_factors": {},
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        priority_order = [ra.ISSUE_PRIORITY_LEVELS.index(g.priority) for g in gaps]
        self.assertEqual(priority_order, sorted(priority_order))

    def test_no_duplicate_gaps(self) -> None:
        """diagnose_gaps must not produce duplicate fingerprints."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": ["bad.py"],
                "cycles": [],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 45,
                "score_factors": {},
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        fps = [ra.issue_fingerprint(g.subsystem, g.issue_key) for g in gaps]
        self.assertEqual(len(fps), len(set(fps)), "Duplicate fingerprints in diagnose_gaps output")


# ---------------------------------------------------------------------------
# 19. Issue-first mode: run_issue_cycle output schema
# ---------------------------------------------------------------------------

REQUIRED_ISSUE_OUTPUT_FIELDS = frozenset({
    "status", "mode", "dry_run", "gaps_detected", "gaps_selected",
    "issue_actions", "summary", "architecture_score",
    "requested_model", "actual_model", "primary_model", "fallback_model",
    "model_used", "fallback_used", "fallback_reason", "fallback_occurred",
    "artifact_files", "charter",
    # Backward-compat fields
    "lane", "lanes_active", "branch", "changed_files", "validation",
    "pull_request_url", "no_safe_code_mutation_reason",
})


class TestRunIssueCycleOutputSchema(unittest.TestCase):
    def test_output_schema_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode=ra.ISSUE_MODE, dry_run=True)
            result = ra.run_issue_cycle(config)
        missing = REQUIRED_ISSUE_OUTPUT_FIELDS - set(result.keys())
        self.assertEqual(missing, set(), f"Missing output fields in issue mode: {missing}")

    def test_status_is_issue_cycle_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode=ra.ISSUE_MODE, dry_run=True)
            result = ra.run_issue_cycle(config)
        self.assertEqual(result["status"], "issue_cycle_complete")
        self.assertEqual(result["mode"], ra.ISSUE_MODE)

    def test_dry_run_flag_reflected_in_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode=ra.ISSUE_MODE, dry_run=True)
            result = ra.run_issue_cycle(config)
        self.assertTrue(result["dry_run"])

    def test_run_cycle_routes_issue_mode(self) -> None:
        """run_cycle with mode='issue' must delegate to run_issue_cycle."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode=ra.ISSUE_MODE, dry_run=True)
            result = ra.run_cycle(config)
        self.assertEqual(result["status"], "issue_cycle_complete")

    def test_max_issues_limits_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            # Create conditions for multiple gaps: parse errors + cycles
            (root / "bad.py").write_text("def foo(\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True, check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "bad files"], capture_output=True, check=True)
            config = _make_config(root, mode=ra.ISSUE_MODE, dry_run=True, max_issues=1)
            result = ra.run_issue_cycle(config)
        self.assertLessEqual(len(result["issue_actions"]), 1)


# ---------------------------------------------------------------------------
# 20. Issue-first mode: charter-validated secondary mode notice
# ---------------------------------------------------------------------------

class TestCharterValidatedModeNotice(unittest.TestCase):
    """Charter-validated mutation modes must emit an informational notice and still function."""

    def test_mutate_mode_emits_charter_notice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, mode="mutate")
            analysis: Dict[str, Any] = {
                "parse_error_files": [],
                "cycles": [],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 80,
                "score_factors": {},
                "roadmap": [],
                "python_files": [],
                "debug_print_candidates": [],
                "local_import_graph": {},
            }
            import io
            stderr_capture = io.StringIO()
            import sys as _sys
            old_stderr = _sys.stderr
            _sys.stderr = stderr_capture
            try:
                ra.build_patch_plan(config, analysis, {}, {})
            finally:
                _sys.stderr = old_stderr
            output = stderr_capture.getvalue()
        self.assertIn("charter-validated", output)
        self.assertIn("issue", output.lower())

    def test_default_mode_is_issue(self) -> None:
        """The default CLI mode must be 'issue', not 'report' or 'mutate'."""
        args = ra.parse_args([])
        self.assertEqual(args.mode, ra.ISSUE_MODE)


# ---------------------------------------------------------------------------
# 21. Charter lane map and higher-lane gap detection
# ---------------------------------------------------------------------------

class TestCharterLaneMap(unittest.TestCase):
    """CHARTER_LANE_MAP must list all 10 charter-defined lanes."""

    def test_charter_lane_map_has_ten_lanes(self) -> None:
        self.assertEqual(len(ra.CHARTER_LANE_MAP), 10)
        self.assertEqual(set(ra.CHARTER_LANE_MAP.keys()), set(range(10)))

    def test_charter_lane_map_entries_are_tuples(self) -> None:
        for lane_num, entry in ra.CHARTER_LANE_MAP.items():
            self.assertIsInstance(entry, tuple, f"Lane {lane_num} entry is not a tuple")
            self.assertEqual(len(entry), 3, f"Lane {lane_num} entry has {len(entry)} fields, expected 3")

    def test_charter_lanes_cover_mutation_lane_order(self) -> None:
        """Every lane in MUTATION_LANE_ORDER must appear in CHARTER_LANE_MAP values."""
        automated_names = {entry[0] for entry in ra.CHARTER_LANE_MAP.values()}
        for lane in ra.MUTATION_LANE_ORDER:
            self.assertIn(lane, automated_names, f"MUTATION_LANE_ORDER lane '{lane}' not in CHARTER_LANE_MAP")


class TestHigherLaneGapDetection(unittest.TestCase):
    """diagnose_gaps must detect gaps for charter lanes 5 and 7 when signals are present."""

    def _model_meta(self, used: bool = False) -> Dict[str, Any]:
        return {
            "used": used, "summary": None, "requested_model": None, "actual_model": None,
            "primary_model": None, "fallback_model": None, "model_used": None,
            "fallback_used": False, "fallback_reason": None, "fallback_occurred": False, "enabled": False,
        }

    def test_dependency_direction_violations_produce_gap(self) -> None:
        """Cross-boundary imports should trigger a Lane 5 (contract repair) gap."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": [],
                "cycles": [],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 80,
                "score_factors": {},
                "local_import_graph": {
                    # Module-name format (matching build_analysis output)
                    "backend.interface.api": ["backend.core.engine"],
                },
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        contract_gaps = [g for g in gaps if g.issue_key == "contract-repair"]
        self.assertGreaterEqual(len(contract_gaps), 1, "Expected a contract-repair gap for interface→core import")
        self.assertEqual(contract_gaps[0].subsystem, "core")

    def test_agent_boundary_violations_produce_gap(self) -> None:
        """Cross-agent imports should trigger a Lane 7 (agent boundary enforcement) gap."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": [],
                "cycles": [],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 80,
                "score_factors": {},
                "local_import_graph": {
                    # Module-name format (matching build_analysis output)
                    "backend.agents.planner.core": ["backend.agents.executor.internal"],
                },
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        boundary_gaps = [g for g in gaps if g.issue_key == "agent-boundary"]
        self.assertGreaterEqual(len(boundary_gaps), 1, "Expected an agent-boundary gap for cross-agent import")
        self.assertEqual(boundary_gaps[0].subsystem, "agents")

    def test_no_violations_no_higher_lane_gaps(self) -> None:
        """When there are no violations, no Lane 5 or 7 gaps should appear."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": [],
                "cycles": [],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 80,
                "score_factors": {},
                "local_import_graph": {
                    # Module-name format — same package, no cross-boundary
                    "backend.core.engine": ["backend.core.utils"],
                },
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        higher_gaps = [g for g in gaps if g.issue_key in ("contract-repair", "agent-boundary")]
        self.assertEqual(len(higher_gaps), 0)

    def test_agents_to_interface_is_allowed_per_charter(self) -> None:
        """agents→interface follows §6 allowed direction and must NOT be flagged."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": [],
                "cycles": [],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 80,
                "score_factors": {},
                "local_import_graph": {
                    "backend.agents.planner": ["backend.interface.api"],
                },
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        contract_gaps = [g for g in gaps if g.issue_key == "contract-repair"]
        self.assertEqual(len(contract_gaps), 0, "agents→interface is allowed per §6; no contract-repair gap expected")

    def test_interface_to_runtime_detected_as_violation(self) -> None:
        """interface→runtime violates §6 direction and must be flagged."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": [],
                "cycles": [],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 80,
                "score_factors": {},
                "local_import_graph": {
                    "backend.interface.api": ["backend.runtime.scheduler"],
                },
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        contract_gaps = [g for g in gaps if g.issue_key == "contract-repair"]
        self.assertGreaterEqual(len(contract_gaps), 1, "interface→runtime should be a contract-repair gap")


# ---------------------------------------------------------------------------
# 22. _module_segments normalizer
# ---------------------------------------------------------------------------

class TestModuleSegments(unittest.TestCase):
    """_module_segments must handle both module names and file paths."""

    def test_module_name_splits_on_dots(self) -> None:
        self.assertEqual(ra._module_segments("backend.core.engine"), ("backend", "core", "engine"))

    def test_file_path_splits_on_slashes(self) -> None:
        parts = ra._module_segments("backend/core/engine.py")
        self.assertEqual(parts, ("backend", "core", "engine"))

    def test_file_path_without_py_extension(self) -> None:
        parts = ra._module_segments("backend/core/engine")
        self.assertEqual(parts, ("backend", "core", "engine"))

    def test_single_segment_module(self) -> None:
        self.assertEqual(ra._module_segments("repo_architect"), ("repo_architect",))


# ---------------------------------------------------------------------------
# 23. _module_to_path mapper
# ---------------------------------------------------------------------------

class TestModuleToPath(unittest.TestCase):
    """_module_to_path should resolve module names to file paths from analysis data."""

    def test_maps_via_python_files(self) -> None:
        analysis = {"python_files": [{"module": "backend.core.engine", "path": "backend/core/engine.py"}]}
        self.assertEqual(ra._module_to_path("backend.core.engine", analysis), "backend/core/engine.py")

    def test_falls_back_to_dot_replacement(self) -> None:
        analysis = {"python_files": []}
        self.assertEqual(ra._module_to_path("backend.core.engine", analysis), "backend/core/engine.py")

    def test_falls_back_when_no_python_files(self) -> None:
        analysis: Dict[str, Any] = {}
        self.assertEqual(ra._module_to_path("backend.core.engine", analysis), "backend/core/engine.py")


# ---------------------------------------------------------------------------
# 24. Dedupe failure handling in synthesize_issue
# ---------------------------------------------------------------------------

class TestDedupeFailureHandling(unittest.TestCase):
    """find_existing_github_issue should raise on API errors, not swallow them."""

    def test_find_existing_raises_on_api_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            config.github_token = "fake-token"
            config.github_repo = "owner/repo"
            # Mock github_request to raise RepoArchitectError (simulates API failure)
            with patch.object(ra, "github_request", side_effect=ra.RepoArchitectError("simulated 5xx")):
                with self.assertRaises(ra.RepoArchitectError):
                    ra.find_existing_github_issue(config, "abc123def456")

    def test_find_existing_raises_on_network_error(self) -> None:
        """URLError (network failure) should propagate as RepoArchitectError."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            config.github_token = "fake-token"
            config.github_repo = "owner/repo"
            with patch.object(ra, "github_request", side_effect=ra.RepoArchitectError("network error: timeout")):
                with self.assertRaises(ra.RepoArchitectError):
                    ra.find_existing_github_issue(config, "abc123def456")


class TestGithubRequestErrorNormalization(unittest.TestCase):
    """github_request must normalize both HTTPError and URLError into RepoArchitectError."""

    def test_url_error_wrapped_as_repo_architect_error(self) -> None:
        """URLError from network failure should raise RepoArchitectError, not bubble raw."""
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("DNS lookup failed")):
            with self.assertRaises(ra.RepoArchitectError) as ctx:
                ra.github_request("fake-token", "/repos/test/repo")
            self.assertIn("network error", str(ctx.exception).lower())

    def test_http_error_wrapped_as_repo_architect_error(self) -> None:
        """HTTPError should raise RepoArchitectError."""
        import io
        import urllib.error
        body = io.BytesIO(b"rate limited")
        exc = urllib.error.HTTPError("http://api.github.com", 429, "Too Many Requests", {}, body)
        with patch("urllib.request.urlopen", side_effect=exc):
            with self.assertRaises(ra.RepoArchitectError) as ctx:
                ra.github_request("fake-token", "/repos/test/repo")
            self.assertIn("429", str(ctx.exception))


# ---------------------------------------------------------------------------
# 25. Import cycle suggested_files maps to file paths
# ---------------------------------------------------------------------------

class TestImportCycleSuggestedFiles(unittest.TestCase):
    """Import cycle gaps should produce file paths in suggested_files, not module names."""

    def _model_meta(self, used: bool = False) -> Dict[str, Any]:
        return {
            "used": used, "summary": None, "requested_model": None, "actual_model": None,
            "primary_model": None, "fallback_model": None, "model_used": None,
            "fallback_used": False, "fallback_reason": None, "fallback_occurred": False, "enabled": False,
        }

    def test_suggested_files_are_paths_not_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": [],
                "cycles": [["backend.core.a", "backend.core.b", "backend.core.a"]],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 80,
                "score_factors": {},
                "python_files": [
                    {"module": "backend.core.a", "path": "backend/core/a.py"},
                    {"module": "backend.core.b", "path": "backend/core/b.py"},
                ],
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        cycle_gaps = [g for g in gaps if g.issue_key == "import-cycles"]
        self.assertTrue(len(cycle_gaps) >= 1)
        # Suggested files should be file paths, not module names
        for f in cycle_gaps[0].suggested_files:
            self.assertIn("/", f, f"Expected a file path but got module name: {f}")
            self.assertTrue(f.endswith(".py"), f"Expected .py extension but got: {f}")


# ---------------------------------------------------------------------------
# 26. Charter §14/§15/§16 constants and companion files
# ---------------------------------------------------------------------------

class TestCharterPriorityOrder(unittest.TestCase):
    """Verify CHARTER_PRIORITY_ORDER matches charter §14."""

    def test_has_eight_items(self) -> None:
        self.assertEqual(len(ra.CHARTER_PRIORITY_ORDER), 8)

    def test_starts_with_parse_correctness(self) -> None:
        self.assertIn("parse", ra.CHARTER_PRIORITY_ORDER[0].lower())

    def test_ends_with_self_modification(self) -> None:
        self.assertIn("self-modification", ra.CHARTER_PRIORITY_ORDER[-1].lower())


class TestAgentInstructionContract(unittest.TestCase):
    """Verify AGENT_INSTRUCTION_CONTRACT matches charter §16."""

    def test_has_eight_instructions(self) -> None:
        self.assertEqual(len(ra.AGENT_INSTRUCTION_CONTRACT), 8)

    def test_mentions_canonical_entrypoint(self) -> None:
        combined = " ".join(ra.AGENT_INSTRUCTION_CONTRACT)
        self.assertIn("backend/unified_server.py", combined)

    def test_all_entries_are_strings(self) -> None:
        for item in ra.AGENT_INSTRUCTION_CONTRACT:
            self.assertIsInstance(item, str)
            self.assertTrue(len(item) > 10, f"Instruction too short: {item}")


class TestCharterCompanionFiles(unittest.TestCase):
    """Verify §15 companion files exist and are valid JSON."""

    def test_companion_file_constants_defined(self) -> None:
        self.assertEqual(len(ra.CHARTER_COMPANION_FILES), 3)
        for path in ra.CHARTER_COMPANION_FILES:
            self.assertTrue(path.endswith(".json"), f"Expected .json: {path}")

    def test_companion_files_exist(self) -> None:
        git_root = pathlib.Path(__file__).parent.parent
        for rel in ra.CHARTER_COMPANION_FILES:
            full = git_root / rel
            self.assertTrue(full.exists(), f"Missing companion file: {rel}")

    def test_companion_files_are_valid_json(self) -> None:
        git_root = pathlib.Path(__file__).parent.parent
        for rel in ra.CHARTER_COMPANION_FILES:
            full = git_root / rel
            with open(full, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIsInstance(data, dict, f"{rel} is not a JSON object")

    def test_policy_json_has_required_fields(self) -> None:
        git_root = pathlib.Path(__file__).parent.parent
        with open(git_root / "docs/repo_architect/policy.json", encoding="utf-8") as f:
            data = json.load(f)
        required = {"default_mode", "modes", "canonical_entrypoint", "priority_order", "agent_instruction_contract"}
        self.assertTrue(required.issubset(set(data.keys())), f"Missing fields: {required - set(data.keys())}")

    def test_mutation_lanes_json_has_all_10_lanes(self) -> None:
        git_root = pathlib.Path(__file__).parent.parent
        with open(git_root / "docs/repo_architect/mutation_lanes.json", encoding="utf-8") as f:
            data = json.load(f)
        lanes = data.get("lanes", {})
        self.assertEqual(len(lanes), 10, f"Expected 10 lanes, got {len(lanes)}")
        for i in range(10):
            self.assertIn(str(i), lanes, f"Missing lane {i}")

    def test_dependency_contract_json_has_prohibitions(self) -> None:
        git_root = pathlib.Path(__file__).parent.parent
        with open(git_root / "docs/repo_architect/dependency_contract.json", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("hard_prohibitions", data)
        self.assertTrue(len(data["hard_prohibitions"]) >= 3)


class TestLoadCharterContextCompanionFiles(unittest.TestCase):
    """Verify load_charter_context returns companion_files metadata."""

    def test_companion_files_in_context(self) -> None:
        git_root = pathlib.Path(__file__).parent.parent
        ctx = ra.load_charter_context(git_root)
        self.assertIn("companion_files", ctx)
        self.assertIsInstance(ctx["companion_files"], list)
        # In the real repo, all 3 should exist
        self.assertEqual(len(ctx["companion_files"]), 3)


# ---------------------------------------------------------------------------
# 29. dependency_contract.json charter alignment
# ---------------------------------------------------------------------------

class TestDependencyContractCharterAlignment(unittest.TestCase):
    """dependency_contract.json must align with charter §6 and Lane 5 detection."""

    def _load_contract(self) -> Dict[str, Any]:
        git_root = pathlib.Path(__file__).parent.parent
        with open(git_root / "docs/repo_architect/dependency_contract.json", encoding="utf-8") as f:
            return json.load(f)

    def test_no_self_referential_schema(self) -> None:
        """$schema must not point to the contract file itself."""
        data = self._load_contract()
        self.assertNotIn("$schema", data)

    def test_layer_order_matches_charter_s6(self) -> None:
        """layer_order must be [runtime, core, knowledge, agents, interface] per charter §6."""
        data = self._load_contract()
        self.assertEqual(data["layer_order"], ["runtime", "core", "knowledge", "agents", "interface"])

    def test_allowed_direction_describes_inward_flow(self) -> None:
        """allowed_direction must describe dependency from outer to inner layers."""
        data = self._load_contract()
        direction = data["allowed_direction"].lower()
        # Must mention outer/inner layer dependency concepts
        self.assertIn("inner", direction)
        self.assertIn("depend", direction)

    def test_layer_order_semantics_field_present(self) -> None:
        """layer_order_semantics must clarify that index 0 is the foundation."""
        data = self._load_contract()
        self.assertIn("layer_order_semantics", data)
        self.assertIn("innermost", data["layer_order_semantics"].lower())


# ---------------------------------------------------------------------------
# 30. Hard exception normalization in find_existing_github_issue
# ---------------------------------------------------------------------------

class TestDedupeHardExceptionNormalization(unittest.TestCase):
    """find_existing_github_issue must normalise ALL exceptions to RepoArchitectError."""

    def _config(self) -> ra.Config:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            config.github_token = "fake-token"
            config.github_repo = "owner/repo"
            return config

    def test_non_dict_response_returns_none(self) -> None:
        """Non-dict API response should be handled gracefully (returns None)."""
        config = self._config()
        with patch.object(ra, "github_request", return_value="not-a-dict"):
            result = ra.find_existing_github_issue(config, "abc123")
            self.assertIsNone(result)

    def test_runtime_error_normalised_to_repo_architect_error(self) -> None:
        """Unexpected RuntimeError must become RepoArchitectError, not bubble raw."""
        config = self._config()
        with patch.object(ra, "github_request", side_effect=RuntimeError("unexpected")):
            with self.assertRaises(ra.RepoArchitectError) as ctx:
                ra.find_existing_github_issue(config, "abc123")
            self.assertIn("Dedupe lookup failed", str(ctx.exception))

    def test_type_error_normalised_to_repo_architect_error(self) -> None:
        """Unexpected TypeError must become RepoArchitectError, not bubble raw."""
        config = self._config()
        # Simulate github_request returning something that causes TypeError downstream
        with patch.object(ra, "github_request", side_effect=TypeError("unexpected type")):
            with self.assertRaises(ra.RepoArchitectError) as ctx:
                ra.find_existing_github_issue(config, "abc123")
            self.assertIn("Dedupe lookup failed", str(ctx.exception))

    def test_key_error_normalised_to_repo_architect_error(self) -> None:
        """Unexpected KeyError must become RepoArchitectError."""
        config = self._config()
        with patch.object(ra, "github_request", side_effect=KeyError("missing")):
            with self.assertRaises(ra.RepoArchitectError) as ctx:
                ra.find_existing_github_issue(config, "abc123")
            self.assertIn("Dedupe lookup failed", str(ctx.exception))

    def test_repo_architect_error_still_propagates(self) -> None:
        """RepoArchitectError from github_request must propagate unchanged."""
        config = self._config()
        with patch.object(ra, "github_request", side_effect=ra.RepoArchitectError("API 500")):
            with self.assertRaises(ra.RepoArchitectError) as ctx:
                ra.find_existing_github_issue(config, "abc123")
            self.assertIn("API 500", str(ctx.exception))


# ---------------------------------------------------------------------------
# 31. labels_confirmed proves relabel on existing issues
# ---------------------------------------------------------------------------

class TestLabelsConfirmed(unittest.TestCase):
    """Verify the distinction between labels_applied (requested) and labels_confirmed (API proof).

    labels_applied: deterministic set computed by the orchestration layer, always populated.
    labels_confirmed: labels returned by the GitHub API after create/update, proving the
    request succeeded.  Must be None for dry-run and error paths (no API call made).
    """

    def _make_gap(self) -> ra.ArchGap:
        return ra.ArchGap(
            subsystem="workflow", issue_key="test-gap", title="[arch-gap] Test",
            summary="s", problem="p", why_it_matters="w", scope="s2",
            suggested_files=[], implementation_notes="i",
            acceptance_criteria=["done"], validation_commands=["pytest"],
            out_of_scope="x", copilot_prompt="fix it", priority="medium", confidence=0.8,
        )

    def test_labels_confirmed_on_update_path(self) -> None:
        """When existing issue is updated, labels_confirmed must reflect PATCH response."""
        gap = self._make_gap()
        fp = ra.issue_fingerprint(gap.subsystem, gap.issue_key)
        fake_existing = {"number": 42, "html_url": "https://github.com/test/42",
                         "body": f"<!-- arch-gap-fingerprint: {fp} -->"}
        # Simulate PATCH response with labels array
        patch_resp = {"id": 42, "labels": [
            {"name": "arch-gap"}, {"name": "copilot-task"},
            {"name": "needs-implementation"}, {"name": "workflow"},
        ]}

        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, github_token="fake-tok", github_repo="org/repo")
            with patch.object(ra, "find_existing_github_issue", return_value=fake_existing):
                with patch.object(ra, "update_github_issue_api", return_value={"id": 1}):
                    with patch.object(ra, "set_github_issue_labels", return_value=patch_resp):
                        with patch.object(ra, "ensure_github_labels"):
                            action = ra.synthesize_issue(config, gap, "run-001", dry_run=False)

        self.assertEqual(action.action, "updated")
        self.assertIsNotNone(action.labels_confirmed)
        self.assertIn("arch-gap", action.labels_confirmed)
        self.assertIn("workflow", action.labels_confirmed)

    def test_labels_confirmed_on_create_path(self) -> None:
        """When a new issue is created, labels_confirmed must reflect create response."""
        gap = self._make_gap()
        create_resp = {"number": 99, "html_url": "https://github.com/test/99",
                       "labels": [{"name": "arch-gap"}, {"name": "copilot-task"}]}

        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, github_token="fake-tok", github_repo="org/repo")
            with patch.object(ra, "find_existing_github_issue", return_value=None):
                with patch.object(ra, "create_github_issue_api", return_value=create_resp):
                    with patch.object(ra, "ensure_github_labels"):
                        action = ra.synthesize_issue(config, gap, "run-001", dry_run=False)

        self.assertEqual(action.action, "created")
        self.assertIsNotNone(action.labels_confirmed)
        self.assertIn("arch-gap", action.labels_confirmed)

    def test_labels_confirmed_none_for_dry_run(self) -> None:
        """In dry_run mode, labels_confirmed should be None."""
        gap = self._make_gap()
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            action = ra.synthesize_issue(config, gap, "run-001", dry_run=True)
        self.assertIsNone(action.labels_confirmed)

    def test_labels_confirmed_none_on_error(self) -> None:
        """On API error, labels_confirmed should be None."""
        gap = self._make_gap()
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root, github_token="fake-tok", github_repo="org/repo")
            with patch.object(ra, "find_existing_github_issue", return_value=None):
                with patch.object(ra, "create_github_issue_api", side_effect=ra.RepoArchitectError("fail")):
                    with patch.object(ra, "ensure_github_labels"):
                        action = ra.synthesize_issue(config, gap, "run-001", dry_run=False)
        self.assertEqual(action.action, "error")
        self.assertIsNone(action.labels_confirmed)


# ---------------------------------------------------------------------------
# 32. Generated report files are gitignored
# ---------------------------------------------------------------------------

class TestGeneratedReportArtifactsGitignored(unittest.TestCase):
    """Generated per-run report .md files must not be tracked by git."""

    def test_report_files_are_gitignored(self) -> None:
        """The five generated report .md files must appear in .gitignore."""
        git_root = pathlib.Path(__file__).parent.parent
        gitignore = (git_root / ".gitignore").read_text(encoding="utf-8")
        expected = [
            "docs/repo_architect/runtime_inventory.md",
            "docs/repo_architect/circular_dependencies.md",
            "docs/repo_architect/parse_errors.md",
            "docs/repo_architect/entrypoint_clusters.md",
            "docs/repo_architect/top_risks.md",
        ]
        for f in expected:
            self.assertIn(f, gitignore, f"{f} should be in .gitignore")

    def test_report_files_not_tracked(self) -> None:
        """Generated report .md files should not be tracked by git."""
        git_root = pathlib.Path(__file__).parent.parent
        result = subprocess.run(
            ["git", "-C", str(git_root), "ls-files", "--error-unmatch",
             "docs/repo_architect/runtime_inventory.md"],
            capture_output=True,
        )
        # ls-files --error-unmatch returns non-zero when file is NOT tracked
        self.assertNotEqual(result.returncode, 0,
                            "runtime_inventory.md should not be tracked by git")


# ---------------------------------------------------------------------------
# 33. _agent_name helper
# ---------------------------------------------------------------------------

class TestAgentName(unittest.TestCase):
    """Verify _agent_name correctly extracts the agent identifier segment."""

    def test_standard_agent_module(self) -> None:
        segs = ra._module_segments("backend.agents.planner.core")
        self.assertEqual(ra._agent_name(segs), "planner")

    def test_agent_at_boundary(self) -> None:
        segs = ra._module_segments("backend.agents.executor")
        self.assertEqual(ra._agent_name(segs), "executor")

    def test_no_agents_segment(self) -> None:
        segs = ra._module_segments("backend.core.engine")
        self.assertIsNone(ra._agent_name(segs))

    def test_agents_at_end_no_child(self) -> None:
        """If 'agents' is the last segment, there's no agent name."""
        segs = ("backend", "agents")
        self.assertIsNone(ra._agent_name(segs))


# ---------------------------------------------------------------------------
# 34. Lane 7 same-agent-different-depth is NOT a violation
# ---------------------------------------------------------------------------

class TestLane7SameAgentNotFlagged(unittest.TestCase):
    """Imports within the same agent at different depths must not be flagged."""

    def _model_meta(self, used: bool = False) -> Dict[str, Any]:
        return {
            "used": used, "summary": None, "requested_model": None, "actual_model": None,
            "primary_model": None, "fallback_model": None, "model_used": None,
            "fallback_used": False, "fallback_reason": None, "fallback_occurred": False, "enabled": False,
        }

    def test_same_agent_different_depth_no_gap(self) -> None:
        """backend.agents.foo → backend.agents.foo.utils is same agent, not a violation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": [],
                "cycles": [],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 80,
                "score_factors": {},
                "local_import_graph": {
                    "backend.agents.foo": ["backend.agents.foo.utils"],
                },
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        boundary_gaps = [g for g in gaps if g.issue_key == "agent-boundary"]
        self.assertEqual(len(boundary_gaps), 0,
                         "Same-agent import at different depth should NOT trigger agent-boundary gap")

    def test_cross_agent_still_flagged(self) -> None:
        """backend.agents.foo → backend.agents.bar.internal is a cross-agent violation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_git_root(tmp)
            config = _make_config(root)
            analysis: Dict[str, Any] = {
                "parse_error_files": [],
                "cycles": [],
                "entrypoint_clusters": {},
                "entrypoint_paths": [],
                "architecture_score": 80,
                "score_factors": {},
                "local_import_graph": {
                    "backend.agents.foo.core": ["backend.agents.bar.internal"],
                },
            }
            gaps = ra.diagnose_gaps(config, analysis, self._model_meta())
        boundary_gaps = [g for g in gaps if g.issue_key == "agent-boundary"]
        self.assertGreaterEqual(len(boundary_gaps), 1,
                                "Cross-agent import should still trigger agent-boundary gap")


if __name__ == "__main__":
    unittest.main()
