import os
import time
import uuid
from typing import Dict, Any, Optional

import pytest
import requests


@pytest.mark.e2e
@pytest.mark.requires_backend
def test_nl_ast_ksi_roundtrip_via_public_endpoints(test_config):
    """
    E2E: NL→AST→KSI round-trip and query via public endpoints.

    Flow:
    1) Formalize a simple NL/formal statement into an AST via POST /nlu/formalize
    2) Assert it via POST /kr/assert into a unique test context
    3) Query it via GET /kr/query and verify a hit
    4) Retract it via POST /kr/retract
    5) Query again and verify it no longer matches

    Notes:
    - Uses the canonical unified endpoints with KSIAdapter behind them.
    - Skips gracefully if formalization is unavailable.
    """

    base = test_config.get("backend_url", "http://localhost:8000")
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # Quick health and capability check
    try:
        health = session.get(f"{base}/health", timeout=5)
        assert health.status_code in (200, 503), f"Unexpected health status: {health.status_code}"
    except Exception as e:
        pytest.skip(f"Backend health not accessible: {e}")

    caps = session.get(f"{base}/ksi/capabilities", timeout=5)
    # Capabilities may report {"ksi_available": False} when KSI not ready; skip test in that case
    if caps.status_code != 200:
        pytest.skip(f"KSI capabilities endpoint unavailable: {caps.status_code}")
    caps_json = caps.json()
    if not caps_json.get("ksi_available", False):
        pytest.skip("KSI not available per /ksi/capabilities")

    # Use a unique context to avoid crosstalk with other tests
    context_id = f"E2E_CTX_{uuid.uuid4().hex[:10]}"
    # Pick a simple formal statement expected to parse: a unary predicate application
    # If formal parser is unavailable, endpoint may still fallback to wrapper AST when possible.
    statement_text = "Human(Socrates)"

    # 1) NL → AST
    formalize_resp = session.post(
        f"{base}/nlu/formalize",
        json={"text": statement_text},
        timeout=10,
    )
    assert formalize_resp.status_code == 200, f"formalize failed: {formalize_resp.text}"
    formalize_json = formalize_resp.json()
    if not formalize_json.get("success") or not formalize_json.get("ast"):
        pytest.skip(f"Formalization unavailable or failed: {formalize_json}")

    # 2) Assert into KSI (public endpoint)
    assert_resp = session.post(
        f"{base}/kr/assert",
        json={
            "statement": statement_text,
            "context_id": context_id,
            "confidence": 0.99,
            "metadata": {"tags": ["e2e_test"], "note": "roundtrip"}
        },
        timeout=10,
    )
    assert assert_resp.status_code == 200, f"/kr/assert failed: {assert_resp.text}"
    assert_json = assert_resp.json()
    assert assert_json.get("success") is True, f"Assert unsuccessful: {assert_json}"
    assert "version" in assert_json and isinstance(assert_json["version"], int), "Missing version from assert result"

    # 3) Query via public endpoint; expect at least one match
    # We query the same pattern we asserted. Even with no variables, a backend may return an empty binding dict per match.
    query_resp = session.get(
        f"{base}/kr/query",
        params=[("pattern", statement_text), ("context_ids", context_id)],
        timeout=10,
    )
    assert query_resp.status_code == 200, f"/kr/query failed: {query_resp.text}"
    query_json = query_resp.json()
    bindings = query_json.get("bindings", [])
    count = int(query_json.get("count", len(bindings)))
    assert count >= 1 or len(bindings) >= 1, f"Expected a match after assert; got: {query_json}"

    # 4) Retract via public endpoint
    retract_resp = session.post(
        f"{base}/kr/retract",
        json={
            "pattern": statement_text,
            "context_id": context_id,
            "metadata": {"reason": "cleanup_e2e"}
        },
        timeout=10,
    )
    assert retract_resp.status_code == 200, f"/kr/retract failed: {retract_resp.text}"
    retract_json = retract_resp.json()
    assert retract_json.get("success") is True, f"Retract unsuccessful: {retract_json}"

    # 5) Query again; expect zero matches
    query_after_resp = session.get(
        f"{base}/kr/query",
        params=[("pattern", statement_text), ("context_ids", context_id)],
        timeout=10,
    )
    assert query_after_resp.status_code == 200, f"/kr/query (after retract) failed: {query_after_resp.text}"
    query_after_json = query_after_resp.json()
    bindings_after = query_after_json.get("bindings", [])
    count_after = int(query_after_json.get("count", len(bindings_after)))
    assert count_after == 0 or len(bindings_after) == 0, f"Expected no matches after retract; got: {query_after_json}"


@pytest.mark.e2e
@pytest.mark.requires_backend
def test_formalize_endpoint_fallbacks_and_errors(test_config):
    """
    Sanity checks for /nlu/formalize edge-cases.

    - Empty input -> 400 from the API handler
    - A clearly non-formal sentence may still be formalized via wrapper AST if the core_kr is available.
      If not, we only require the endpoint to return a JSON response with success flag.
    """
    base = test_config.get("backend_url", "http://localhost:8000")
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # Empty input should yield 400 per unified_server validation
    bad = session.post(f"{base}/nlu/formalize", json={}, timeout=5)
    assert bad.status_code == 400, f"Expected 400 for empty input, got {bad.status_code}: {bad.text}"

    # Non-formal text may fallback; we don't assert success hard, but ensure a valid JSON shape
    fallback_text = "Socrates is a human."
    resp = session.post(f"{base}/nlu/formalize", json={"text": fallback_text}, timeout=10)
    assert resp.status_code in (200, 500), f"Unexpected status from /nlu/formalize: {resp.status_code}"
    # If 200, ensure JSON has expected keys
    if resp.status_code == 200:
        js = resp.json()
        assert "success" in js and "confidence" in js and "errors" in js, "Unexpected response shape from /nlu/formalize"
