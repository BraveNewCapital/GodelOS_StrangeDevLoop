#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple KR Endpoint Client for GödelOS examples

This lightweight client wraps the public KR endpoints exposed by the unified backend
server, allowing example scripts to interact with the Knowledge Representation (KR)
stack via HTTP instead of instantiating KnowledgeStoreInterface directly.

Endpoints used (served by backend.unified_server:app):
- POST /kr/assert                       -> Assert a textual statement (NL→AST inside server)
- POST /kr/retract                      -> Retract a textual pattern/statement
- GET  /ksi/capabilities                -> Inspect KSIAdapter availability and known contexts
- POST /admin/kr/assert-batch           -> Assert a batch of statements (optional events)
- POST /admin/kr/assert-raw             -> Raw underlying KSI insert (no version bump/events)
- POST /admin/reconciliation/config     -> Update reconciliation monitor config at runtime
- GET  /health, /api/health (best-effort health check)

Usage:
    from examples.kr_client import KRClient

    client = KRClient(base_url="http://127.0.0.1:8000")
    caps = client.ksi_capabilities()
    print("KSI available:", caps.get("ksi_available"))

    res = client.assert_statement("Human(Socrates)", context_id="TRUTHS")
    print("Asserted:", res)

    res = client.retract_pattern("Human(Socrates)", context_id="TRUTHS")
    print("Retracted:", res)

Notes:
- This client is dependency-light and uses only the 'requests' package.
- It is designed for examples and quick scripts. For production code, prefer a
  typed API client and robust error handling as needed.

Environment:
- GODELOS_BASE_URL can be set to change the default base URL (e.g. http://localhost:8000).
"""

from __future__ import annotations

import os
import time
import json
from typing import Any, Dict, Iterable, List, Optional, Union

try:
    import requests
except Exception as e:  # pragma: no cover
    raise RuntimeError("The 'requests' package is required for KRClient. Please install it via 'pip install requests'.") from e


JSON = Dict[str, Any]


class KRClient:
    """
    Minimal HTTP client for GödelOS KR endpoints.

    - Base URL defaults to env GODELOS_BASE_URL or http://127.0.0.1:8000
    - All methods raise RuntimeError on unreachable server or unexpected responses
      unless fail_silently=True is passed to the specific call.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        timeout: float = 30.0,
        default_context: str = "TRUTHS",
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("GODELOS_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")
        self.timeout = float(timeout)
        self.default_context = default_context
        self._session = session or requests.Session()
        # Identify client in server-side logs for observability
        self._session.headers.update({"User-Agent": "GodelOS-KRClient/1.0"})

    # --------------- Internal helpers

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _handle_resp(self, resp: requests.Response, *, expect_json: bool = True) -> Union[JSON, str]:
        if resp.status_code >= 400:
            detail = None
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(f"HTTP {resp.status_code}: {detail}")
        if expect_json:
            try:
                return resp.json()
            except Exception:
                raise RuntimeError(f"Expected JSON response but got: {resp.text[:200]}")
        return resp.text

    # --------------- Health and capabilities

    def health(self, *, fail_silently: bool = False) -> JSON:
        """
        Check server health (tries /health, falls back to /api/health).
        """
        for p in ("/health", "/api/health"):
            try:
                r = self._session.get(self._url(p), timeout=self.timeout)
                return self._handle_resp(r, expect_json=True)
            except Exception as e:
                last_err = e
        if fail_silently:
            return {"status": "unknown", "error": str(last_err)}  # type: ignore[name-defined]
        raise RuntimeError(f"Health check failed: {last_err}")  # type: ignore[name-defined]

    def ksi_capabilities(self, *, fail_silently: bool = False) -> JSON:
        """
        Inspect KSIAdapter availability and known contexts.
        """
        try:
            r = self._session.get(self._url("/ksi/capabilities"), timeout=self.timeout)
            return self._handle_resp(r, expect_json=True)
        except Exception as e:
            if fail_silently:
                return {"ksi_available": False, "error": str(e)}
            raise

    # --------------- KR mutations

    def assert_statement(
        self,
        statement: str,
        *,
        context_id: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[JSON] = None,
        fail_silently: bool = False,
    ) -> JSON:
        """
        Assert a textual statement (server formalizes NL→AST internally).

        Returns:
            { success: bool, context_id: str, version: int, statement_hash?: str }

        Raises:
            RuntimeError on HTTP or parsing errors unless fail_silently=True.
        """
        payload: JSON = {
            "statement": str(statement),
            "context_id": context_id or self.default_context,
        }
        if confidence is not None:
            payload["confidence"] = float(confidence)
        if metadata:
            payload["metadata"] = dict(metadata)
        try:
            r = self._session.post(self._url("/kr/assert"), json=payload, timeout=self.timeout)
            return self._handle_resp(r, expect_json=True)
        except Exception as e:
            if fail_silently:
                return {"success": False, "error": str(e)}
            raise

    def retract_pattern(
        self,
        pattern: str,
        *,
        context_id: Optional[str] = None,
        metadata: Optional[JSON] = None,
        fail_silently: bool = False,
    ) -> JSON:
        """
        Retract a textual pattern/statement.

        Returns:
            { success: bool, context_id: str, version: int, statement_hash?: str }
        """
        payload: JSON = {
            "pattern": str(pattern),
            "context_id": context_id or self.default_context,
        }
        if metadata:
            payload["metadata"] = dict(metadata)
        try:
            r = self._session.post(self._url("/kr/retract"), json=payload, timeout=self.timeout)
            return self._handle_resp(r, expect_json=True)
        except Exception as e:
            if fail_silently:
                return {"success": False, "error": str(e)}
            raise

    def assert_batch(
        self,
        statements: Iterable[str],
        *,
        context_id: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[JSON] = None,
        emit_events: bool = True,
        fail_silently: bool = False,
    ) -> JSON:
        """
        Assert a batch of statements via admin test endpoint.

        Note: This is primarily for testing/demo; production code should rely on normal
        public endpoints unless there's a specific need for batch inserts.
        """
        payload: JSON = {
            "statements": [str(s) for s in statements],
            "context_id": context_id or self.default_context,
            "emit_events": bool(emit_events),
        }
        if confidence is not None:
            payload["confidence"] = float(confidence)
        if metadata:
            payload["metadata"] = dict(metadata)

        try:
            r = self._session.post(self._url("/admin/kr/assert-batch"), json=payload, timeout=self.timeout)
            return self._handle_resp(r, expect_json=True)
        except Exception as e:
            if fail_silently:
                return {"success": False, "error": str(e)}
            raise

    def assert_raw(
        self,
        statement: str,
        *,
        context_id: Optional[str] = None,
        fail_silently: bool = False,
    ) -> JSON:
        """
        Raw insert into the underlying KSI (no version bump or event emission).
        Useful for inducing reconciliation diffs in tests/demos.

        Returns:
            { success: bool, context_id: str, note: str }
        """
        payload: JSON = {
            "statement": str(statement),
            "context_id": context_id or self.default_context,
        }
        try:
            r = self._session.post(self._url("/admin/kr/assert-raw"), json=payload, timeout=self.timeout)
            return self._handle_resp(r, expect_json=True)
        except Exception as e:
            if fail_silently:
                return {"success": False, "error": str(e)}
            raise

    # --------------- Reconciliation monitor configuration

    def update_reconciliation_config(
        self,
        *,
        include_statement_diffs: Optional[bool] = None,
        statements_limit: Optional[int] = None,  # pass None to disable limit
        interval_seconds: Optional[int] = None,
        emit_summary_every_n_cycles: Optional[int] = None,
        max_discrepancies_per_cycle: Optional[int] = None,
        contexts_to_check: Optional[Union[str, List[str]]] = None,  # list or comma-separated string
        emit_streamed: Optional[bool] = None,
        ping_when_idle: Optional[bool] = None,
        fail_silently: bool = False,
    ) -> JSON:
        """
        Update reconciliation monitor settings at runtime. Only provided keys are changed.

        Returns:
            {
              "success": True/False,
              "config": { ... effective config ... }
            }
        """
        payload: JSON = {}
        if include_statement_diffs is not None:
            payload["include_statement_diffs"] = bool(include_statement_diffs)
        if statements_limit is not None or statements_limit is None:
            # Allow explicit None to disable limit
            payload["statements_limit"] = statements_limit
        if interval_seconds is not None:
            payload["interval_seconds"] = int(interval_seconds)
        if emit_summary_every_n_cycles is not None:
            payload["emit_summary_every_n_cycles"] = int(emit_summary_every_n_cycles)
        if max_discrepancies_per_cycle is not None:
            payload["max_discrepancies_per_cycle"] = int(max_discrepancies_per_cycle)
        if contexts_to_check is not None:
            payload["contexts_to_check"] = contexts_to_check
        if emit_streamed is not None:
            payload["emit_streamed"] = bool(emit_streamed)
        if ping_when_idle is not None:
            payload["ping_when_idle"] = bool(ping_when_idle)

        try:
            r = self._session.post(self._url("/admin/reconciliation/config"), json=payload, timeout=self.timeout)
            return self._handle_resp(r, expect_json=True)
        except Exception as e:
            if fail_silently:
                return {"success": False, "error": str(e)}
            raise

    # --------------- Context management helpers (best-effort)

    def ensure_server_ready(self, *, wait_seconds: float = 10.0) -> bool:
        """
        Best-effort wait until the server reports healthy. Returns True if healthy within wait_seconds.
        """
        deadline = time.time() + max(0.0, float(wait_seconds))
        last_err: Optional[Exception] = None
        while time.time() < deadline:
            try:
                h = self.health(fail_silently=False)
                if isinstance(h, dict):
                    return True
            except Exception as e:
                last_err = e
            time.sleep(0.5)
        if last_err:
            raise RuntimeError(f"Server not healthy within {wait_seconds}s: {last_err}")
        return False

    # --------------- Context manager

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            pass

    def __enter__(self) -> "KRClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# --------------- Example CLI usage

def _example_cli() -> None:
    """
    Minimal CLI demonstration:
    - Checks health
    - Prints KSI capabilities
    - Asserts a trivial fact, then retracts it
    """
    import argparse
    ap = argparse.ArgumentParser(description="Simple GödelOS KR client")
    ap.add_argument("--base-url", default=os.getenv("GODELOS_BASE_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--context", default="TRUTHS")
    ap.add_argument("--statement", default="Human(Socrates)")
    args = ap.parse_args()

    with KRClient(base_url=args.base_url, default_context=args.context) as client:
        try:
            ok = client.ensure_server_ready(wait_seconds=10.0)
            print("Health:", "ok" if ok else "unknown")
        except Exception as e:
            print("Health check failed:", e)
            return

        try:
            caps = client.ksi_capabilities(fail_silently=True)
            print("KSI Capabilities:", json.dumps(caps, indent=2))
        except Exception as e:
            print("Capabilities error:", e)

        print(f"Asserting: {args.statement} in {args.context}")
        res = client.assert_statement(args.statement, fail_silently=True)
        print("Assert result:", json.dumps(res, indent=2))

        print(f"Retracting: {args.statement} from {args.context}")
        res = client.retract_pattern(args.statement, fail_silently=True)
        print("Retract result:", json.dumps(res, indent=2))


if __name__ == "__main__":
    _example_cli()
