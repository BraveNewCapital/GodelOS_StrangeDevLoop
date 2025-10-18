import os
from typing import Dict, Tuple

import pytest

try:
    import httpx
except Exception as e:  # pragma: no cover - ensure clear import error
    raise RuntimeError("httpx is required for live API tests. Install from requirements.txt.") from e


BASE_URL = os.environ.get("GODELOS_BASE_URL", "http://127.0.0.1:8000")


def _check_backend_health(client: httpx.Client) -> Tuple[bool, Dict]:
    try:
        resp = client.get("/api/health", timeout=5.0)
        if resp.status_code == 200:
            return True, resp.json()
    except Exception:
        pass
    # Try fallback health
    try:
        resp = client.get("/health", timeout=5.0)
        if resp.status_code == 200:
            return True, resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"ok": True}
    except Exception:
        pass
    return False, {}


@pytest.fixture(scope="module")
def live_api():
    """Yield a live httpx client bound to the real backend; skip if not running."""
    client = httpx.Client(base_url=BASE_URL, follow_redirects=True)
    try:
        ok, _ = _check_backend_health(client)
        if not ok:
            pytest.skip(
                f"Backend not reachable at {BASE_URL}. Start it with './start-godelos.sh --dev' and retry.")
        yield client
    finally:
        try:
            client.close()
        except Exception:
            pass


@pytest.mark.spec_aligned
@pytest.mark.requires_backend
def test_user_story_knowledge_reasoning_nlg(live_api: httpx.Client):
    """
    User story: As a knowledge engineer, I can assert a rule and a fact, prove a consequence,
    query for results, and realize a statement into natural language.
    
    Given a running GödelOS backend server
    When I assert rules and facts via the API
    Then I can query for results and generate natural language output
    
    NOTE: Requires backend running - start with: ./start-godelos.sh --dev
    """

    client = live_api

    # Discover capabilities to ensure NL↔Logic endpoints are advertised
    # Use root endpoint which exposes an 'endpoints' map
    caps = client.get("/", timeout=10)
    assert caps.status_code == 200
    caps_json = caps.json()
    assert isinstance(caps_json, dict)
    endpoints = (caps_json.get("endpoints") or {}).get("nl_logic") or []
    assert any("/api/kr/query" in e for e in endpoints)

    # Ensure KSI is available; otherwise skip this flow
    ksi = client.get("/api/ksi/capabilities", timeout=10)
    assert ksi.status_code in (200, 503)
    if ksi.status_code == 200:
        ksi_json = ksi.json() or {}
        if not ksi_json.get("ksi_available", True):
            pytest.skip("KSI adapter unavailable; skipping KR/inference flow")

    # 1) Assert a rule and a fact into TRUTHS
    rule = {
        "statement": "forall ?x. Human(?x) => Mortal(?x)",
        "context_id": "TRUTHS",
        "confidence": 0.95,
        "metadata": {"tags": ["axiom", "demo"]},
    }
    r1 = client.post("/api/kr/assert", json=rule, timeout=15)
    assert r1.status_code == 200, r1.text
    assert isinstance(r1.json(), dict)

    fact = {"statement": "Human(Socrates)", "context_id": "TRUTHS"}
    r2 = client.post("/api/kr/assert", json=fact, timeout=15)
    assert r2.status_code == 200, r2.text

    # 2) Prove a goal using inference engine (if available)
    prove_req = {"goal": "Mortal(Socrates)", "context_ids": ["TRUTHS"]}
    proof = client.post("/api/inference/prove", json=prove_req, timeout=30)
    if proof.status_code == 503:
        pytest.xfail("Inference engine unavailable; skipping proof check")
    assert proof.status_code == 200, proof.text
    proof_json = proof.json()
    assert isinstance(proof_json, dict)
    # With forward chaining implemented, the proof should succeed
    if "success" in proof_json:
        assert proof_json["success"], f"Forward chaining should prove Mortal(Socrates) from rule + fact. Response: {proof_json}"
    else:
        assert "proof" in proof_json

    # 3) Query for results to ensure the fact was stored (using direct query, not existential)
    q = client.get(
        "/api/kr/query",
        params={"pattern": "Human(Socrates)", "context_ids": "TRUTHS"},
        timeout=15,
    )
    assert q.status_code == 200, q.text
    qj = q.json()
    assert isinstance(qj, dict)
    assert (qj.get("count") or 0) >= 1

    # 4) Realize a statement to natural language
    nlg = client.post("/api/nlg/realize", json={"ast": "Mortal(Socrates)", "style": "statement"}, timeout=10)
    assert nlg.status_code == 200, nlg.text
    nlg_json = nlg.json()
    assert isinstance(nlg_json, dict)
    assert isinstance(nlg_json.get("text"), str) and len(nlg_json["text"]) > 0


@pytest.mark.spec_aligned
@pytest.mark.requires_backend
def test_user_story_transparency_metrics(live_api: httpx.Client):
    """
    User story: As an observer, I can fetch transparency metrics to understand recent activity.
    
    Given a running GödelOS backend server
    When I query the transparency metrics endpoint
    Then I receive activity statistics and recent events
    
    NOTE: Requires backend running - start with: ./start-godelos.sh --dev
    """

    client = live_api

    resp = client.get("/api/v1/transparency/metrics", timeout=10)
    # Some builds may not expose enhanced APIs; tolerate 404/503 by skipping
    if resp.status_code in (404, 503):
        pytest.skip("Transparency metrics endpoint not available in this build")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    # Loosely require at least one numeric metric
    has_number = any(isinstance(v, (int, float)) for v in data.values())
    assert has_number
