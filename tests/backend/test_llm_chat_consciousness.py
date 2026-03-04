"""Tests that /api/llm-chat/message routes through the consciousness engine."""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.unified_server import app


@pytest.fixture(autouse=True)
def _patch_globals():
    """Patch global service instances used by the chat endpoint."""
    mock_llm = AsyncMock()
    mock_llm.process_query = AsyncMock(return_value={
        "response": "Hello from LLM",
        "tool_calls": [],
        "reasoning": ["step1"],
    })

    mock_uce = AsyncMock()
    mock_uce.process_with_unified_awareness = AsyncMock(return_value="conscious response")

    with patch("backend.unified_server.tool_based_llm", mock_llm), \
         patch("backend.unified_server.unified_consciousness_engine", mock_uce):
        yield {"llm": mock_llm, "uce": mock_uce}


@pytest.fixture
def client():
    return TestClient(app)


def test_chat_returns_llm_response(client, _patch_globals):
    """Chat endpoint should still return the LLM response."""
    resp = client.post("/api/llm-chat/message", json={"message": "hi"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "Hello from LLM"


def test_chat_triggers_consciousness_engine(client, _patch_globals):
    """Chat endpoint should fire process_with_unified_awareness as a side-effect."""
    resp = client.post("/api/llm-chat/message", json={"message": "hello"})
    assert resp.status_code == 200

    uce = _patch_globals["uce"]
    uce.process_with_unified_awareness.assert_called_once()
    call_args = uce.process_with_unified_awareness.call_args
    assert call_args[0][0] == "hello"  # prompt is the user message
    assert call_args[1]["context"]["source"] == "llm_chat"


def test_chat_works_without_consciousness_engine(client):
    """Chat should still work when unified_consciousness_engine is None."""
    mock_llm = AsyncMock()
    mock_llm.process_query = AsyncMock(return_value={
        "response": "LLM only",
        "tool_calls": [],
        "reasoning": [],
    })

    with patch("backend.unified_server.tool_based_llm", mock_llm), \
         patch("backend.unified_server.unified_consciousness_engine", None):
        resp = client.post("/api/llm-chat/message", json={"message": "test"})
        assert resp.status_code == 200
        assert resp.json()["response"] == "LLM only"
