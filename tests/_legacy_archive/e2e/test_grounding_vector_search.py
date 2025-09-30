import uuid
from typing import Any, Iterable, List

import pytest
import requests


def _extract_result_ids(results: Iterable[Any]) -> List[str]:
    """
    Normalize various result shapes returned by vector search into a list of IDs.

    Acceptable shapes:
    - List[Tuple[str, float]] -> take first element as id
    - List[Dict[str, Any]] with key "id"
    - List[str]
    """
    ids: List[str] = []
    for r in results or []:
        try:
            if isinstance(r, dict) and "id" in r:
                ids.append(str(r["id"]))
            elif isinstance(r, (list, tuple)) and len(r) >= 1:
                ids.append(str(r[0]))
            elif isinstance(r, str):
                ids.append(r)
        except Exception:
            # ignore malformed entry
            pass
    return ids


@pytest.mark.e2e
@pytest.mark.requires_backend
def test_grounding_vector_search_if_available(test_config):
    """
    E2E: Grounding mini-test leveraging vector search if the vector DB is available.

    Flow:
    1) Check /capabilities for vector_database_available; skip if unavailable.
    2) POST /api/v1/vector-db/add-items with a small, distinct set of texts.
    3) POST /api/v1/vector-db/search with a query semantically similar to one inserted item.
    4) Validate results are non-empty and include at least one of the inserted IDs.

    Notes:
    - This test is capability-aware and skips when the vector DB is not present.
    - It tolerates different result shapes (tuple/list/dict) from the search endpoint.
    """
    base = test_config.get("backend_url", "http://localhost:8000")
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # (1) Capability check
    caps = session.get(f"{base}/capabilities", timeout=10)
    if caps.status_code != 200:
        pytest.skip(f"/capabilities unavailable: {caps.status_code}")
    caps_js = caps.json()
    if not caps_js.get("vector_database_available", False):
        pytest.skip("Vector database not available per /capabilities")

    # Light health check (optional)
    health = session.get(f"{base}/api/v1/vector-db/health", timeout=10)
    if health.status_code != 200:
        pytest.skip(f"Vector DB health endpoint not ready: {health.status_code}")

    # (2) Add items with unique IDs to avoid collisions
    ns = f"e2e-{uuid.uuid4().hex[:8]}"
    items = [
        {
            "id": f"{ns}-physics",
            "text": "Quantum mechanics studies particles at atomic and subatomic scales.",
            "metadata": {"topic": "physics", "tags": ["quantum", "particles"]},
        },
        {
            "id": f"{ns}-biology",
            "text": "Cellular biology explores the structure and function of cells in living organisms.",
            "metadata": {"topic": "biology", "tags": ["cells", "organisms"]},
        },
        {
            "id": f"{ns}-cs",
            "text": "Machine learning enables computers to learn patterns from data.",
            "metadata": {"topic": "computer_science", "tags": ["ml", "learning", "data"]},
        },
    ]
    add_resp = session.post(
        f"{base}/api/v1/vector-db/add-items",
        json={"items": items, "batch_size": 10},
        timeout=30,
    )
    assert add_resp.status_code == 200, f"add-items failed: {add_resp.text}"
    add_js = add_resp.json()
    assert add_js.get("status") in ("success", "accepted"), f"Unexpected add-items status: {add_js}"

    # (3) Search with a query similar to the physics item
    search_query = "particle physics and quantum phenomena"
    search_resp = session.post(
        f"{base}/api/v1/vector-db/search",
        json={"query": search_query, "k": 5},
        timeout=30,
    )
    assert search_resp.status_code == 200, f"search failed: {search_resp.text}"
    search_js = search_resp.json()
    assert search_js.get("status") == "success", f"Unexpected search status: {search_js}"
    data = search_js.get("data", {}) or {}
    results = data.get("results", []) or []

    # (4) Validate non-empty results and presence of at least one inserted ID
    found_ids = _extract_result_ids(results)
    assert len(found_ids) > 0, f"No results returned for query: {search_js}"
    inserted_ids = [i["id"] for i in items]
    is_overlap = any(fid in inserted_ids for fid in found_ids)
    assert is_overlap, f"Expected at least one of {inserted_ids} in results; got {found_ids}"
