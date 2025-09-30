import json
import time
import uuid
from typing import Any, Dict, Optional

import pytest
import requests


def _base_urls():
    base_http = "http://127.0.0.1:8000"
    # Allow override via environment if pytest test_config is not present
    try:
        import os
        base_http = os.getenv("GODELOS_BASE_URL", base_http).rstrip("/")
    except Exception:
        pass
    if base_http.startswith("https://"):
        base_ws = "wss://" + base_http[len("https://") :]
    elif base_http.startswith("http://"):
        base_ws = "ws://" + base_http[len("http://") :]
    else:
        base_ws = "ws://" + base_http
        base_http = "http://" + base_http
    return base_http, base_ws


def _post_json(url: str, body: Dict[str, Any], timeout: float = 10.0) -> requests.Response:
    return requests.post(url, data=json.dumps(body), headers={"Content-Type": "application/json"}, timeout=timeout)


def _try_import_ws_client():
    try:
        import websocket as ws_cli  # websocket-client (sync)
        return ws_cli
    except Exception:
        return None


def _ws_url(base_ws: str) -> str:
    return f"{base_ws}/ws/cognitive-stream"


@pytest.mark.e2e
@pytest.mark.requires_backend
def test_reconciliation_diff_statement_version_mismatch():
    """
    E2E: Induce reconciliation diff discrepancy (statement_version_mismatch) and verify it via WS.

    Strategy:
    1) Enable statement diffs with a small statements_limit and fast interval via admin config.
    2) Seed a fresh context with baseline statements using the KSIAdapter path (batch assert).
    3) Perform a raw insert using admin/kr/assert-raw that bypasses version bump and events.
    4) Listen on /ws/cognitive-stream for a reconciliation_discrepancy event where:
       details.kind == "statement_version_mismatch" && details.context_id == our test context.
    """
    base_http, base_ws = _base_urls()
    ws_client = _try_import_ws_client()
    if not ws_client:
        pytest.skip("websocket-client not installed; skipping reconciliation diff WS test")

    # Sanity: backend health reachable
    try:
        health = requests.get(f"{base_http}/health", timeout=5)
        assert health.status_code in (200, 503, 404, 422)
    except Exception as e:
        pytest.skip(f"Backend not reachable: {e}")

    # Configure reconciliation monitor for fast diffs (admin)
    cfg_resp = _post_json(
        f"{base_http}/admin/reconciliation/config",
        {
            "include_statement_diffs": True,
            "statements_limit": 10,
            "interval_seconds": 1,
            "emit_summary_every_n_cycles": 1,
            "emit_streamed": True,
        },
        timeout=10.0,
    )
    if cfg_resp.status_code == 404:
        pytest.skip("Admin reconciliation config endpoint not available in this build")
    assert cfg_resp.status_code == 200, f"Failed to update reconciliation config: {cfg_resp.status_code} {cfg_resp.text}"
    cfg_json = {}
    try:
        cfg_json = cfg_resp.json()
    except Exception:
        pass
    assert cfg_json.get("success") is True, f"Unexpected config response: {cfg_json}"

    # Create a unique test context to avoid interference
    ctx = f"E2E_DIFF_CTX_{uuid.uuid4().hex[:8]}"

    # Seed baseline statements via KSIAdapter path (batch assert)
    seed_statements = [
        "SeedPred(A1)",
        "SeedPred(A2)",
    ]
    batch_resp = _post_json(
        f"{base_http}/admin/kr/assert-batch",
        {
            "statements": seed_statements,
            "context_id": ctx,
            "confidence": 0.97,
            "metadata": {"tags": ["e2e_diff_seed"]},
            "emit_events": True,
        },
        timeout=15.0,
    )
    if batch_resp.status_code == 404:
        pytest.skip("Admin batch assert endpoint not available in this build")
    assert batch_resp.status_code == 200, f"Batch assert failed: {batch_resp.status_code} {batch_resp.text}"
    try:
        batch_json = batch_resp.json()
    except Exception:
        batch_json = {}
    assert batch_json.get("success") in (True, False), f"Unexpected batch result: {batch_json}"
    # Even if some fail to assert (due to environment), we proceed — baseline snapshot should still capture context.

    # Connect to WS
    ws_url = _ws_url(base_ws)
    ws = ws_client.create_connection(ws_url, timeout=10)
    try:
        # Drain any initial message
        try:
            ws.settimeout(0.25)
            _ = ws.recv()
        except Exception:
            pass

        # Give the monitor 1-2 cycles to capture baseline snapshot
        time.sleep(2.0)

        # Raw insert bypassing KSIAdapter (no version bump)
        raw_stmt = "RawOnlyPred(B1)"
        raw_resp = _post_json(
            f"{base_http}/admin/kr/assert-raw",
            {"statement": raw_stmt, "context_id": ctx},
            timeout=10.0,
        )
        if raw_resp.status_code == 404:
            pytest.skip("Admin raw assert endpoint not available in this build")
        assert raw_resp.status_code == 200, f"Raw assert failed: {raw_resp.status_code} {raw_resp.text}"
        try:
            raw_json = raw_resp.json()
        except Exception:
            raw_json = {}
        assert raw_json.get("success") in (True, False), f"Unexpected raw assert result: {raw_json}"

        # Wait for reconciliation_discrepancy => statement_version_mismatch for our context
        deadline = time.time() + 20.0  # allow multiple cycles
        got_mismatch = None
        while time.time() < deadline:
            remaining = max(0.1, deadline - time.time())
            ws.settimeout(remaining)
            try:
                raw_msg = ws.recv()
            except Exception:
                continue

            # Parse message
            try:
                evt = json.loads(raw_msg) if isinstance(raw_msg, (str, bytes)) else raw_msg
            except Exception:
                continue
            if not isinstance(evt, dict):
                continue

            # Filter reconciliation discrepancy events
            if evt.get("type") != "cognitive_event":
                continue
            data = evt.get("data", {}) or {}
            if data.get("event_type") != "reconciliation_discrepancy":
                continue
            details = data.get("details", {}) or {}
            if (
                details.get("kind") == "statement_version_mismatch"
                and details.get("context_id") == ctx
            ):
                got_mismatch = details
                break

        assert got_mismatch is not None, "Did not receive statement_version_mismatch discrepancy for test context"

    finally:
        try:
            ws.close()
        except Exception:
            pass
