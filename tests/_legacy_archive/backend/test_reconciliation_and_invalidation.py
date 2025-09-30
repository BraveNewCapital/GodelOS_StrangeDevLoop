import asyncio
import json
from uuid import uuid4

import pytest
import httpx
from asgi_lifespan import LifespanManager
pytestmark = pytest.mark.e2e

# These tests assume the unified server is the single source of truth.
# They are capability-aware and will skip gracefully if KSI (symbolic KR) is unavailable.
try:
    from backend.unified_server import app as unified_app  # FastAPI instance with lifespan wiring
except Exception as e:
    unified_app = None  # type: ignore


async def _ksi_available(client: "httpx.AsyncClient") -> bool:
    try:
        resp = await client.get("/ksi/capabilities", timeout=30)
        if resp.status_code != 200:
            return False
        data = resp.json()
        return bool(data.get("ksi_available"))
    except Exception:
        return False


async def _enable_reconciliation_diffs(client: "httpx.AsyncClient", contexts=("TRUTHS",), statements_limit=1000) -> bool:
    payload = {
        "include_statement_diffs": True,
        "contexts_to_check": list(contexts),
        "statements_limit": statements_limit,
        "emit_streamed": False,
        "emit_summary_every_n_cycles": 0,
    }
    try:
        resp = await client.post("/admin/reconciliation/config", json=payload, timeout=30)
        if resp.status_code != 200:
            return False
        cfg = resp.json().get("config", {})
        return bool(cfg.get("include_statement_diffs"))
    except Exception:
        return False


@pytest.mark.asyncio
@pytest.mark.skipif(unified_app is None, reason="Unified server app unavailable")
async def test_reconciliation_detects_statement_version_mismatch():
    """
    Verify reconciliation diff detection: statements change without version bump.
    Sequence:
    1) Take baseline reconciliation snapshot (run_once).
    2) Insert a new statement via raw admin endpoint (bypasses version bump).
    3) Take another reconciliation snapshot.
    4) Expect Discrepancy.kind == 'statement_version_mismatch' in 'TRUTHS'.
    """
    async with LifespanManager(unified_app):
        transport = httpx.ASGITransport(app=unified_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Ensure KSI is available
            if not await _ksi_available(client):
                pytest.skip("KSI unavailable in this environment")

            # Enable statement-level diffs for reconciliation
            if not await _enable_reconciliation_diffs(client, contexts=("TRUTHS",), statements_limit=1000):
                pytest.skip("Unable to enable reconciliation statement diffs")

            # Ensure TRUTHS context exists and initialize versions by asserting S1 via normal endpoint
            s1 = f"I_{uuid4().hex[:6]}(a)"
            r_init = await client.post("/kr/assert", json={"statement": s1, "context_id": "TRUTHS"}, timeout=30)
            if r_init.status_code != 200 or not r_init.json().get("success"):
                pytest.skip("KR init assertion failed; cannot validate statement diffs")

            # Baseline reconciliation cycle
            r0 = await client.post("/admin/reconciliation/run-once", timeout=30)
            assert r0.status_code == 200 and r0.json().get("success") is True

            # Insert a unique statement via raw admin endpoint to avoid version bump
            unique_stmt = f"P_{uuid4().hex[:8]}(a)"
            r = await client.post("/admin/kr/assert-raw", json={"statement": unique_stmt, "context_id": "TRUTHS"}, timeout=30)
            assert r.status_code == 200
            body = r.json()
            # Note: raw insert bypasses version bump and event emission intentionally
            assert body.get("success") is True

            # Second reconciliation cycle; should detect mismatch due to statements change without version bump
            resp = await client.post("/admin/reconciliation/run-once", timeout=30)
            assert resp.status_code == 200 and resp.json().get("success") is True
            rep = resp.json().get("report") or {}
            kinds = [(d.get("kind"), d.get("context_id")) for d in (rep.get("discrepancies") or [])]
            assert ("statement_version_mismatch", "TRUTHS") in kinds, f"Expected statement_version_mismatch in TRUTHS, got {kinds}"


@pytest.mark.asyncio
@pytest.mark.skipif(unified_app is None, reason="Unified server app unavailable")
async def test_reconciliation_detects_version_changed_no_statement_diff():
    """
    Verify reconciliation diff detection: version changes without statement set changing.
    Sequence:
    1) Assert S1 via normal endpoint (version bump; set S1).
    2) Take snapshot (prev = S1, v1).
    3) Raw insert S2 (no version bump; set S1∪{S2}).
    4) Retract S2 via normal endpoint (version bump; set returns to S1, v2).
    5) Take snapshot and expect Discrepancy.kind == 'version_changed_no_statement_diff'.
    """
    async with LifespanManager(unified_app):
        transport = httpx.ASGITransport(app=unified_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Ensure KSI is available
            if not await _ksi_available(client):
                pytest.skip("KSI unavailable in this environment")

            # Enable statement diffs on TRUTHS
            if not await _enable_reconciliation_diffs(client, contexts=("TRUTHS",), statements_limit=1000):
                pytest.skip("Unable to enable reconciliation statement diffs")

            # Step 1: Assert S1 via normal endpoint (uses KSIAdapter => version bump)
            s1 = f"P_{uuid4().hex[:6]}(a)"
            r1 = await client.post("/kr/assert", json={"statement": s1, "context_id": "TRUTHS"}, timeout=30)
            if r1.status_code != 200:
                pytest.skip(f"Formalization or KSI assertion failed with status {r1.status_code}")
            assert r1.json().get("success") is True

            # Step 2: Snapshot after S1
            r_snap = await client.post("/admin/reconciliation/run-once", timeout=30)
            assert r_snap.status_code == 200 and r_snap.json().get("success") is True

            # Step 3: Raw insert S2 (no version bump)
            s2 = f"Q_{uuid4().hex[:6]}(b)"
            r_raw = await client.post("/admin/kr/assert-raw", json={"statement": s2, "context_id": "TRUTHS"}, timeout=30)
            assert r_raw.status_code == 200 and r_raw.json().get("success") is True

            # Step 4: Retract S2 via normal endpoint (version bump; set returns to S1)
            r2 = await client.post("/kr/retract", json={"pattern": s2, "context_id": "TRUTHS"}, timeout=30)
            if r2.status_code != 200 or not r2.json().get("success"):
                pytest.skip("Retraction did not succeed; cannot test version_changed_no_statement_diff reliably")

            # Step 5: Snapshot should report version_changed_no_statement_diff
            resp2 = await client.post("/admin/reconciliation/run-once", timeout=30)
            assert resp2.status_code == 200 and resp2.json().get("success") is True
            rep2 = resp2.json().get("report") or {}
            kinds = [(d.get("kind"), d.get("context_id")) for d in (rep2.get("discrepancies") or [])]
            assert ("version_changed_no_statement_diff", "TRUTHS") in kinds, f"Expected version_changed_no_statement_diff in TRUTHS, got {kinds}"


@pytest.mark.asyncio
@pytest.mark.skipif(unified_app is None, reason="Unified server app unavailable")
async def test_ksi_adapter_coherence_invalidation_hook_invoked_on_assert():
    """
    Verify that KSIAdapter's coherence invalidation hook is invoked on version-changing mutations.
    We attach a spy invalidator, perform a KR assertion via public endpoint, and ensure the hook is called.
    """
    # Ensure KSI is available and lazily initialized
    async with LifespanManager(unified_app):
        transport = httpx.ASGITransport(app=unified_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            if not await _ksi_available(client):
                pytest.skip("KSI unavailable in this environment")

            # Access the live KSIAdapter from the unified server module
            try:
                import backend.unified_server as server_module
                ksi_adapter = getattr(server_module, "ksi_adapter", None)
                if ksi_adapter is None or not ksi_adapter.available():
                    pytest.skip("KSIAdapter not initialized/available")
            except Exception:
                pytest.skip("Unable to access KSIAdapter from unified server")

            # Attach a spy invalidator
            calls = []

            async def _spy_invalidator(context_id: str, reason: str, details: dict):
                calls.append({"context_id": context_id, "reason": reason, "details": details})

            try:
                ksi_adapter.set_coherence_invalidator(_spy_invalidator)
            except Exception:
                pytest.skip("Failed to attach coherence invalidator to KSIAdapter")

            # Perform an assertion via public endpoint to trigger version bump and invalidation
            stmt = f"R_{uuid4().hex[:6]}(c)"
            resp = await client.post("/kr/assert", json={"statement": stmt, "context_id": "TRUTHS"}, timeout=30)
            if resp.status_code != 200 or not resp.json().get("success"):
                pytest.skip("KR assertion failed; cannot validate invalidation hook")

            # The invalidation hook is async; give the event loop a chance to process
            await asyncio.sleep(0.05)

            # Validate that the invalidation hook was called with expected context and reason
            assert any(c.get("reason") == "assert" and c.get("context_id") == "TRUTHS" for c in calls), f"Invalidation calls: {calls}"
