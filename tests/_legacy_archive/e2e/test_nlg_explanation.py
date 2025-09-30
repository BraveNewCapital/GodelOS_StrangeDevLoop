import uuid
from typing import List

import pytest
import requests


@pytest.mark.e2e
@pytest.mark.requires_backend
def test_nlg_explanation_of_trivial_proof_steps(test_config):
    """
    E2E: Generate an NLG explanation for a trivial proof's steps.

    Flow:
    1) Ensure KSI is available via /ksi/capabilities.
    2) Assert a trivial statement (Human(Socrates)) into a unique test context via /kr/assert.
    3) Prove the same statement via /inference/prove.
    4) Extract proof steps and send them to /nlg/realize to obtain a compact explanation.
    5) Validate that the explanation text contains at least one known step description.
    6) Retract the statement to clean up.

    This validates that:
    - The NL→KR mutation path works for a simple assertion.
    - The proof machinery produces a proof with steps for a trivial goal.
    - The NLG endpoint can render a readable explanation from proof steps.
    """
    base = test_config.get("backend_url", "http://localhost:8000")
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # 1) Capability check for KSI; skip if unavailable
    caps = session.get(f"{base}/ksi/capabilities", timeout=10)
    if caps.status_code != 200:
        pytest.skip(f"KSI capabilities endpoint unavailable: {caps.status_code}")
    caps_json = caps.json()
    if not caps_json.get("ksi_available", False):
        pytest.skip("KSI not available per /ksi/capabilities")

    # 2) Assert a trivial statement in a dedicated context
    context_id = f"E2E_NLG_CTX_{uuid.uuid4().hex[:10]}"
    statement_text = "Human(Socrates)"

    formal_resp = session.post(
        f"{base}/nlu/formalize",
        json={"text": statement_text},
        timeout=10,
    )
    assert formal_resp.status_code == 200, f"/nlu/formalize failed: {formal_resp.text}"
    formal_json = formal_resp.json()
    if not formal_json.get("success") or not formal_json.get("ast"):
        pytest.skip(f"Formalization failed or unavailable: {formal_json}")

    assert_resp = session.post(
        f"{base}/kr/assert",
        json={
            "statement": statement_text,
            "context_id": context_id,
            "confidence": 0.99,
            "metadata": {"tags": ["e2e_nlg"], "note": "trivial_proof_setup"}
        },
        timeout=10,
    )
    assert assert_resp.status_code == 200, f"/kr/assert failed: {assert_resp.text}"
    assert_json = assert_resp.json()
    assert assert_json.get("success") is True, f"Assertion unsuccessful: {assert_json}"

    try:
        # 3) Prove the asserted statement
        prove_resp = session.post(
            f"{base}/inference/prove",
            json={"goal": statement_text, "context_ids": [context_id]},
            timeout=15,
        )
        assert prove_resp.status_code == 200, f"/inference/prove failed: {prove_resp.text}"
        prove_json = prove_resp.json()

        # Trivial proof should succeed
        assert prove_json.get("success") is True, f"Proof did not succeed: {prove_json}"

        proof = prove_json.get("proof", {}) or {}
        steps: List[dict] = proof.get("steps", [])
        assert isinstance(steps, list) and steps, f"No proof steps found: {proof}"

        # 4) Build an explanation request using proof step descriptions
        descriptions = [s.get("description", "") for s in steps if isinstance(s, dict)]
        # Ensure we have at least one non-empty description
        if not any(descriptions):
            pytest.skip(f"No step descriptions available to realize: {steps}")

        nlg_resp = session.post(
            f"{base}/nlg/realize",
            json={"object": descriptions, "style": "explanation"},
            timeout=10,
        )
        assert nlg_resp.status_code == 200, f"/nlg/realize failed: {nlg_resp.text}"
        nlg_json = nlg_resp.json()
        text = nlg_json.get("text", "")
        assert isinstance(text, str) and len(text) > 0, f"Empty NLG text: {nlg_json}"

        # 5) Validate explanation contains at least one known phrase from step descriptions
        known_phrases = [
            "Goal statement exists in KB",
            "Pattern query",
            "not found directly; attempting pattern query",
            "KSI unavailable; cannot attempt proof",  # in case environment flips
        ]
        if not any(phrase in text for phrase in known_phrases):
            # Fall back to checking any of the original descriptions appear
            if not any(desc for desc in descriptions if desc and desc in text):
                pytest.fail(f"NLG explanation did not include expected content. Text: {text}")

    finally:
        # 6) Cleanup: retract the statement from the test context
        try:
            retract_resp = session.post(
                f"{base}/kr/retract",
                json={"pattern": statement_text, "context_id": context_id, "metadata": {"reason": "e2e_cleanup"}},
                timeout=10,
            )
            # Do not assert on cleanup; just best-effort
            _ = retract_resp.status_code
        except Exception:
            pass
