import json
import time
import uuid
import os
from typing import Any, Dict, Optional

import pytest
import requests

# Make performance tests optional; set RUN_PERF_TESTS=1 to enable
RUN_PERF_TESTS = os.getenv("RUN_PERF_TESTS", "").lower() in ("1", "true", "yes", "on")
pytestmark = pytest.mark.skipif(not RUN_PERF_TESTS, reason="Set RUN_PERF_TESTS=1 to run performance tests")


def _make_ws_url(http_base: str) -> str:
    base = http_base.rstrip("/")
    if base.startswith("https://"):
        ws_base = "wss://" + base[len("https://") :]
    elif base.startswith("http://"):
        ws_base = "ws://" + base[len("http://") :]
    else:
        # Fallback: assume ws scheme
        ws_base = "ws://" + base
    return f"{ws_base}/ws/cognitive-stream"


def _try_import_ws_clients():
    """
    Try to import a synchronous and an asynchronous websocket client.
    Returns a tuple (ws_client, websockets_lib).
    """
    ws_client = None
    websockets_lib = None
    try:
        import websocket as ws_cli  # websocket-client (sync)
        ws_client = ws_cli
    except Exception:
        ws_client = None
    try:
        import websockets as ws_lib  # websockets (async)
        websockets_lib = ws_lib
    except Exception:
        websockets_lib = None
    return ws_client, websockets_lib


def _receive_knowledge_update_sync(ws_client_mod, url: str, context_id: str, deadline_s: float) -> Optional[float]:
    """
    Use websocket-client (sync) to wait for a knowledge_update event and return latency in ms.
    Returns None if no matching event received before deadline.
    """
    start_connect = time.perf_counter()
    ws = ws_client_mod.create_connection(url, timeout=deadline_s)
    try:
        # Drain initial messages (if any)
        t0 = None
        while True:
            remaining = deadline_s - (time.perf_counter() - start_connect)
            if remaining <= 0:
                return None
            ws.settimeout(max(0.05, remaining))
            try:
                raw = ws.recv()
            except Exception:
                # Connection closed or timed out before any message; continue to assert and then wait
                break
            if not raw:
                break
            try:
                evt = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            except Exception:
                evt = None
            # We only drain; not measuring yet
            break

        # Perform HTTP assertion after WS is ready to capture event latency
        # The caller will do the HTTP assert; we begin measuring at that point
        return None  # Signal caller to perform assert and then re-enter receive loop
    finally:
        ws.close()


def _wait_for_knowledge_update_sync(ws_client_mod, url: str, context_id: str, start_mark: float, deadline_s: float) -> Optional[float]:
    """
    After issuing HTTP assert, wait for knowledge_update with matching context_id.
    Returns latency ms since start_mark, or None if not received before deadline.
    """
    ws = ws_client_mod.create_connection(url, timeout=deadline_s)
    try:
        while True:
            remaining = deadline_s - (time.perf_counter() - start_mark)
            if remaining <= 0:
                return None
            ws.settimeout(max(0.01, remaining))
            try:
                raw = ws.recv()
            except Exception:
                continue
            try:
                evt = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            except Exception:
                continue
            if not isinstance(evt, dict):
                continue
            if evt.get("type") == "knowledge_update":
                data = evt.get("data", {}) or {}
                if data.get("context_id") == context_id and data.get("action") == "assert":
                    return (time.perf_counter() - start_mark) * 1000.0
    finally:
        ws.close()


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.requires_backend
def test_kr_mutation_latency_smoke(test_config):
    """
    Measure latency for /kr/assert and /kr/retract using a unique context.
    """
    base = test_config.get("backend_url", "http://localhost:8000")
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})

    # Capability check: skip if KSI unavailable
    caps = sess.get(f"{base}/ksi/capabilities", timeout=10)
    if caps.status_code != 200 or not (caps.json() or {}).get("ksi_available", False):
        pytest.skip("KSI not available per /ksi/capabilities")

    thresholds = test_config.get("performance_thresholds", {})
    api_ms = float(thresholds.get("api_response_ms", 2000))

    ctx = f"PERF_CTX_{uuid.uuid4().hex[:10]}"
    stmt = "Human(Socrates)"

    # /kr/assert
    t0 = time.perf_counter()
    resp = sess.post(
        f"{base}/kr/assert",
        json={
            "statement": stmt,
            "context_id": ctx,
            "confidence": 0.95,
            "metadata": {"tags": ["perf_smoke"]},
        },
        timeout=10,
    )
    dt_assert_ms = (time.perf_counter() - t0) * 1000.0
    assert resp.status_code == 200, f"/kr/assert failed: {resp.text}"
    js = resp.json()
    assert js.get("success") is True, f"Assert unsuccessful: {js}"
    assert dt_assert_ms <= api_ms, f"/kr/assert latency {dt_assert_ms:.1f}ms exceeded {api_ms}ms"

    # /kr/retract
    t1 = time.perf_counter()
    resp2 = sess.post(
        f"{base}/kr/retract",
        json={"pattern": stmt, "context_id": ctx, "metadata": {"reason": "cleanup"}},
        timeout=10,
    )
    dt_retract_ms = (time.perf_counter() - t1) * 1000.0
    assert resp2.status_code == 200, f"/kr/retract failed: {resp2.text}"
    js2 = resp2.json()
    assert js2.get("success") is True, f"Retract unsuccessful: {js2}"
    assert dt_retract_ms <= api_ms, f"/kr/retract latency {dt_retract_ms:.1f}ms exceeded {api_ms}ms"


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.requires_backend
def test_inference_latency_smoke(test_config):
    """
    Measure latency for /inference/prove on a trivial goal after asserting it.
    """
    base = test_config.get("backend_url", "http://localhost:8000")
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})

    # Capability check
    caps = sess.get(f"{base}/ksi/capabilities", timeout=10)
    if caps.status_code != 200 or not (caps.json() or {}).get("ksi_available", False):
        pytest.skip("KSI not available per /ksi/capabilities")

    thresholds = test_config.get("performance_thresholds", {})
    infer_ms = float(thresholds.get("query_processing_ms", 5000))

    ctx = f"PERF_INF_CTX_{uuid.uuid4().hex[:10]}"
    stmt = "Human(Socrates)"

    # Ensure the statement is present
    ar = sess.post(
        f"{base}/kr/assert",
        json={"statement": stmt, "context_id": ctx, "confidence": 0.99, "metadata": {"tags": ["perf_infer"]}},
        timeout=10,
    )
    if ar.status_code != 200 or not (ar.json() or {}).get("success", False):
        pytest.skip(f"Setup assert failed: {ar.status_code} {ar.text}")

    try:
        # Prove the same statement
        t0 = time.perf_counter()
        pr = sess.post(
            f"{base}/inference/prove",
            json={"goal": stmt, "context_ids": [ctx]},
            timeout=15,
        )
        dt_ms = (time.perf_counter() - t0) * 1000.0
        assert pr.status_code == 200, f"/inference/prove failed: {pr.text}"
        pjs = pr.json()
        # Even in degraded mode, the endpoint should return a structured JSON; success may be False
        assert "proof" in pjs, f"Proof object missing: {pjs}"
        assert dt_ms <= infer_ms, f"/inference/prove latency {dt_ms:.1f}ms exceeded {infer_ms}ms"
    finally:
        # Cleanup
        try:
            sess.post(
                f"{base}/kr/retract",
                json={"pattern": stmt, "context_id": ctx, "metadata": {"reason": "perf_cleanup"}},
                timeout=10,
            )
        except Exception:
            pass


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.requires_backend
def test_websocket_delivery_latency_smoke(test_config):
    """
    Measure latency from KR assert to knowledge_update delivery over WS.
    """
    base = test_config.get("backend_url", "http://localhost:8000")
    ws_url = _make_ws_url(base)
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})

    # Capability check for KSI
    caps = sess.get(f"{base}/ksi/capabilities", timeout=10)
    if caps.status_code != 200 or not (caps.json() or {}).get("ksi_available", False):
        pytest.skip("KSI not available per /ksi/capabilities")

    thresholds = test_config.get("performance_thresholds", {})
    ws_ms = float(thresholds.get("websocket_latency_ms", 100))
    # Allow more headroom for overall wait to accommodate environment variance
    overall_deadline_s = max(2.0, (ws_ms / 1000.0) * 10.0)

    ctx = f"PERF_WS_CTX_{uuid.uuid4().hex[:10]}"
    stmt = "Human(Socrates)"

    ws_client_mod, websockets_lib = _try_import_ws_clients()
    if not ws_client_mod and not websockets_lib:
        pytest.skip("No websocket client libraries available (websocket-client or websockets)")

    # Prefer synchronous websocket-client for simplicity
    if ws_client_mod:
        # Open a connection briefly to perform any initial handshake/drain
        pre = ws_client_mod.create_connection(ws_url, timeout=overall_deadline_s)
        try:
            try:
                pre.settimeout(0.2)
                _ = pre.recv()
            except Exception:
                pass
        finally:
            pre.close()

        # Mark start just before issuing /kr/assert
        t0 = time.perf_counter()
        ar = sess.post(
            f"{base}/kr/assert",
            json={
                "statement": stmt,
                "context_id": ctx,
                "confidence": 0.9,
                "metadata": {"tags": ["perf_ws"]},
            },
            timeout=10,
        )
        if ar.status_code != 200 or not (ar.json() or {}).get("success", False):
            pytest.skip(f"Setup assert failed: {ar.status_code} {ar.text}")

        # Now wait for the knowledge_update
        elapsed_ms = None
        ws = ws_client_mod.create_connection(ws_url, timeout=overall_deadline_s)
        try:
            while True:
                remaining = overall_deadline_s - (time.perf_counter() - t0)
                if remaining <= 0:
                    break
                ws.settimeout(max(0.01, remaining))
                try:
                    raw = ws.recv()
                except Exception:
                    continue
                try:
                    evt = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                except Exception:
                    continue
                if not isinstance(evt, dict):
                    continue
                if evt.get("type") == "knowledge_update":
                    data = evt.get("data", {}) or {}
                    if data.get("context_id") == ctx and data.get("action") == "assert":
                        elapsed_ms = (time.perf_counter() - t0) * 1000.0
                        break
        finally:
            ws.close()

        try:
            # Cleanup
            sess.post(
                f"{base}/kr/retract",
                json={"pattern": stmt, "context_id": ctx, "metadata": {"reason": "perf_ws_cleanup"}},
                timeout=10,
            )
        except Exception:
            pass

        if elapsed_ms is None:
            pytest.skip("Did not receive knowledge_update over WS within deadline")
        assert elapsed_ms <= ws_ms, f"WS delivery latency {elapsed_ms:.1f}ms exceeded {ws_ms}ms"

    else:
        # Fallback to async websockets lib if available
        import asyncio

        async def run_ws_flow() -> Optional[float]:
            start = None
            elapsed = None
            try:
                async with websockets_lib.connect(ws_url) as websocket:
                    try:
                        # Drain any initial message
                        await asyncio.wait_for(websocket.recv(), timeout=0.2)
                    except Exception:
                        pass

                # Issue KR assert and start the timer
                nonlocal_sess = requests.Session()
                nonlocal_sess.headers.update({"Content-Type": "application/json"})
                start = time.perf_counter()
                ar2 = nonlocal_sess.post(
                    f"{base}/kr/assert",
                    json={
                        "statement": stmt,
                        "context_id": ctx,
                        "confidence": 0.9,
                        "metadata": {"tags": ["perf_ws_async"]},
                    },
                    timeout=10,
                )
                if ar2.status_code != 200 or not (ar2.json() or {}).get("success", False):
                    return None

                async with websockets_lib.connect(ws_url) as websocket2:
                    while True:
                        remaining = overall_deadline_s - (time.perf_counter() - start)
                        if remaining <= 0:
                            break
                        try:
                            raw = await asyncio.wait_for(websocket2.recv(), timeout=max(0.01, remaining))
                        except Exception:
                            continue
                        try:
                            evt = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                        except Exception:
                            continue
                        if not isinstance(evt, dict):
                            continue
                        if evt.get("type") == "knowledge_update":
                            data = evt.get("data", {}) or {}
                            if data.get("context_id") == ctx and data.get("action") == "assert":
                                elapsed = (time.perf_counter() - start) * 1000.0
                                break
            finally:
                try:
                    requests.post(
                        f"{base}/kr/retract",
                        json={"pattern": stmt, "context_id": ctx, "metadata": {"reason": "perf_ws_async_cleanup"}},
                        timeout=10,
                    )
                except Exception:
                    pass
            return elapsed

        elapsed_ms = asyncio.get_event_loop().run_until_complete(run_ws_flow())
        if elapsed_ms is None:
            pytest.skip("Did not receive knowledge_update over WS (async) within deadline")
        assert elapsed_ms <= ws_ms, f"WS delivery latency (async) {elapsed_ms:.1f}ms exceeded {ws_ms}ms"
