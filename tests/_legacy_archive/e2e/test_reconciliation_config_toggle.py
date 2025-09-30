import json
import time
import uuid

import pytest
import requests


def _make_ws_url(http_base: str) -> str:
    base = (http_base or "").rstrip("/")
    if base.startswith("https://"):
        ws_base = "wss://" + base[len("https://") :]
    elif base.startswith("http://"):
        ws_base = "ws://" + base[len("http://") :]
    else:
        ws_base = "ws://" + base
    return f"{ws_base}/ws/cognitive-stream"


def _try_import_ws_client():
    try:
        import websocket as ws_cli  # websocket-client (sync)
        return ws_cli
    except Exception:
        return None


@pytest.mark.e2e
@pytest.mark.requires_backend
def test_reconciliation_config_toggle_and_summary_events(test_config):
    """
    E2E: Toggle reconciliation diff flags via admin endpoint and verify summary events appear on the WS stream.

    Steps:
    1) POST /admin/reconciliation/config to set:
       - include_statement_diffs = true
       - statements_limit = 5
       - interval_seconds = 1
       - emit_summary_every_n_cycles = 1
    2) Connect to /ws/cognitive-stream and wait for a reconciliation_summary cognitive_event.
    3) Validate schema fields of the summary payload.
    """
    base = test_config.get("backend_url", "http://localhost:8000")
    ws_url = _make_ws_url(base)
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # Verify health endpoint is reachable (pytest should have already validated requires_backend)
    try:
        health = session.get(f"{base}/health", timeout=5)
        assert health.status_code in (200, 503)
    except Exception as e:
        pytest.skip(f"Backend health not accessible: {e}")

    # Update reconciliation monitor config to speed up summary cadence
    cfg_resp = session.post(
        f"{base}/admin/reconciliation/config",
        json={
            "include_statement_diffs": True,
            "statements_limit": 5,
            "interval_seconds": 1,
            "emit_summary_every_n_cycles": 1,
            "emit_streamed": True,
        },
        timeout=10,
    )
    # If admin endpoint isn't available in the current build, skip gracefully
    if cfg_resp.status_code == 404:
        pytest.skip("Admin reconciliation config endpoint not available")
    assert cfg_resp.status_code == 200, f"Config update failed: {cfg_resp.status_code} {cfg_resp.text}"
    cfg_json = cfg_resp.json()
    assert cfg_json.get("success") is True, f"Unexpected config response: {cfg_json}"

    # Connect to WebSocket and observe events
    ws_client = _try_import_ws_client()
    if not ws_client:
        pytest.skip("websocket-client not installed; skipping WS verification")

    ws = ws_client.create_connection(ws_url, timeout=10)
    try:
        # Drain any initial message
        try:
            ws.settimeout(0.25)
            _ = ws.recv()
        except Exception:
            pass

        deadline_s = 10.0
        t0 = time.perf_counter()
        summary_event = None

        while (time.perf_counter() - t0) < deadline_s:
            remaining = max(0.1, deadline_s - (time.perf_counter() - t0))
            ws.settimeout(remaining)
            try:
                raw = ws.recv()
            except Exception:
                continue

            # Parse incoming message
            evt = None
            if isinstance(raw, (str, bytes)):
                try:
                    evt = json.loads(raw)
                except Exception:
                    continue
            elif isinstance(raw, dict):
                evt = raw

            if not isinstance(evt, dict):
                continue

            # We expect the unified envelope
            if evt.get("type") != "cognitive_event":
                continue
            inner = evt.get("data", {}) or {}
            if inner.get("event_type") == "reconciliation_summary" and inner.get("component") == "reconciliation_monitor":
                summary_event = inner
                break

        assert summary_event is not None, "Did not receive reconciliation_summary within timeout"

        # Validate essential fields
        details = summary_event.get("details", {}) or {}
        assert "cycle" in details and isinstance(details["cycle"], int), f"Missing or invalid cycle: {details}"
        assert "timestamp" in details, f"Missing timestamp in details: {details}"
        assert "contexts_checked" in details and isinstance(details["contexts_checked"], list), f"Missing contexts_checked: {details}"
        assert "counts" in details and isinstance(details["counts"], dict), f"Missing counts: {details}"
        assert "errors" in details and isinstance(details["errors"], list), f"Missing errors: {details}"

    finally:
        try:
            ws.close()
        except Exception:
            pass
