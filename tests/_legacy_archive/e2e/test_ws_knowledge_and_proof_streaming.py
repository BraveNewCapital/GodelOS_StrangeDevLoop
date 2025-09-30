import os
import json
import time
import asyncio
from typing import Any, Dict, Optional

import pytest
import requests


def _get_base_urls():
    """
    Resolve base HTTP and WS URLs from environment or defaults.
    """
    base_http = os.getenv("GODELOS_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    if base_http.startswith("https://"):
        base_ws = "wss://" + base_http[len("https://"):]
    elif base_http.startswith("http://"):
        base_ws = "ws://" + base_http[len("http://"):]
    else:
        # Fallback assumption
        base_ws = "ws://" + base_http
        base_http = "http://" + base_http
    return base_http, base_ws


def _post_json(url: str, payload: Dict[str, Any], timeout: float = 10.0) -> requests.Response:
    return requests.post(url, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=timeout)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ws_knowledge_update_and_proof_trace_streaming():
    """
    E2E: Verify that
      1) Asserting a fact via KR endpoint emits a knowledge_update event on the cognitive WebSocket.
      2) Proving a goal emits proof_trace events via the cognitive WebSocket, culminating in a finished event.

    Steps:
    - Connect to /ws/cognitive-stream and start listening
    - POST /kr/assert with a simple fact
    - Observe a knowledge_update event
    - POST /api/inference/prove for the same fact
    - Observe proof_trace events including a finished event (ideally success=True)

    Skips:
    - If websockets lib is not installed
    - If server is not reachable or responds with KSI unavailable (503)
    """
    try:
        import websockets  # type: ignore
    except Exception:
        pytest.skip("websockets package not available; skipping WS E2E test")

    base_http, base_ws = _get_base_urls()
    ws_url = f"{base_ws}/ws/cognitive-stream"

    # Quick health probe for server up
    try:
        r = requests.get(f"{base_http}/health", timeout=5.0)
        assert r.status_code in (200, 404, 422, 500)  # server responds
    except Exception:
        pytest.skip("Unified server not reachable; skipping WS E2E test")

    # Message collection
    msg_queue: asyncio.Queue = asyncio.Queue()

    async def ws_listener():
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                # Accept and collect messages
                while True:
                    try:
                        raw = await ws.recv()
                        try:
                            data = json.loads(raw)
                        except Exception:
                            data = {"_raw": raw}
                        await msg_queue.put(data)
                    except Exception:
                        break
        except Exception:
            # Could not connect
            await msg_queue.put({"_ws_error": True})

    listener_task = asyncio.create_task(ws_listener())

    async def wait_for(predicate, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """
        Wait for a message satisfying the predicate within timeout.
        Predicate signature: Dict[str, Any] -> bool
        """
        end = time.time() + timeout
        while time.time() < end:
            try:
                remaining = max(0.0, end - time.time())
                msg = await asyncio.wait_for(msg_queue.get(), timeout=remaining)
                if predicate(msg):
                    return msg
            except asyncio.TimeoutError:
                break
        return None

    # Wait briefly for initial state or any connection indicator
    init_msg = await wait_for(lambda m: isinstance(m, dict), timeout=5.0)
    if init_msg is not None and init_msg.get("_ws_error"):
        pytest.skip("Failed to connect to WS cognitive stream endpoint")

    # 1) Assert a fact -> expect knowledge_update
    fact_text = "TestPred(Alpha)"
    try:
        resp = _post_json(f"{base_http}/kr/assert", {
            "statement": fact_text,
            "context_id": "TRUTHS",
            "confidence": 0.95,
            "metadata": {"tags": ["e2e_test"]}
        }, timeout=10.0)
    except requests.exceptions.RequestException as e:
        listener_task.cancel()
        pytest.skip(f"KR assert endpoint not reachable: {e}")

    if resp.status_code == 503:
        # Likely KSI unavailable in this environment
        listener_task.cancel()
        pytest.skip("KSI unavailable; skipping WS E2E test")

    assert resp.status_code in (200, 201), f"KR assert failed: {resp.status_code} {resp.text}"
    try:
        body = resp.json()
    except Exception:
        body = {}
    assert body.get("success") is True, f"KR assert did not report success: {body}"

    # Wait for knowledge_update on WS
    ku_msg = await wait_for(
        lambda m: isinstance(m, dict) and m.get("type") == "knowledge_update",
        timeout=10.0
    )
    assert ku_msg is not None, "Did not receive knowledge_update event on WS"
    assert isinstance(ku_msg.get("data"), dict), "knowledge_update missing data field"
    assert ku_msg["data"].get("action") == "assert", f"Expected assert action, got: {ku_msg['data'].get('action')}"
    assert fact_text in ku_msg["data"].get("statement", ""), f"knowledge_update statement does not include asserted fact: {ku_msg}"

    # 2) Prove the goal -> expect proof_trace cognitive events
    # Prefer the /api/inference/prove route; include both context_ids and contexts for compatibility
    try:
        resp2 = _post_json(f"{base_http}/api/inference/prove", {
            "goal": fact_text,
            "context_ids": ["TRUTHS"],
            "contexts": ["TRUTHS"]
        }, timeout=20.0)
    except requests.exceptions.RequestException as e:
        listener_task.cancel()
        pytest.fail(f"Inference prove endpoint not reachable: {e}")

    assert resp2.status_code in (200, 201), f"Inference prove failed: {resp2.status_code} {resp2.text}"
    try:
        prove_body = resp2.json()
    except Exception:
        prove_body = {}
    assert "success" in prove_body, f"Malformed prove response: {prove_body}"
    cv = (prove_body.get("proof", {}) or {}).get("context_versions")
    assert isinstance(cv, dict), "Prove response missing proof.context_versions"

    # Wait for at least one proof_trace step and a finished event
    def is_proof_trace(m: Dict[str, Any]) -> bool:
        # Two possible shapes:
        # - Wrapped: {"type": "cognitive_event", "data": {"event_type":"proof_trace", ...}}
        # - Raw: {"event_type":"proof_trace", ...}
        if m.get("type") == "cognitive_event" and isinstance(m.get("data"), dict):
            return m["data"].get("event_type") == "proof_trace"
        return m.get("event_type") == "proof_trace"

    def is_finished(m: Dict[str, Any]) -> bool:
        if m.get("type") == "cognitive_event" and isinstance(m.get("data"), dict):
            return m["data"].get("event_type") == "proof_trace" and m["data"].get("status") == "finished"
        return m.get("event_type") == "proof_trace" and m.get("status") == "finished"

    # Capture an early step
    step_msg = await wait_for(is_proof_trace, timeout=10.0)
    assert step_msg is not None, "Did not receive any proof_trace event on WS"

    # Capture finished event
    finished_msg = await wait_for(is_finished, timeout=10.0)
    assert finished_msg is not None, "Did not receive finished proof_trace event on WS"

    # Validate success if present
    if finished_msg.get("type") == "cognitive_event":
        inner = finished_msg.get("data", {})
        assert inner.get("goal") is not None, "finished proof_trace missing goal"
        assert isinstance(inner.get("context_ids"), list), "finished proof_trace missing context_ids"
        assert "success" in inner, "finished proof_trace missing success flag"
        assert isinstance(inner.get("context_versions"), dict), "finished proof_trace missing context_versions"
    else:
        assert finished_msg.get("goal") is not None, "finished proof_trace missing goal"
        assert isinstance(finished_msg.get("context_ids"), list), "finished proof_trace missing context_ids"
        assert "success" in finished_msg, "finished proof_trace missing success flag"
        assert isinstance(finished_msg.get("context_versions"), dict), "finished proof_trace missing context_versions"

    # Cleanup and cancel listener
    listener_task.cancel()
    try:
        await listener_task
    except Exception:
        pass
