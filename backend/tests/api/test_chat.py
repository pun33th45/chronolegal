"""Integration tests for the /chat endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.fixture
def mock_rag_pipeline():
    from app.schemas.chat import StreamChunk
    from app.services.ai.rag_pipeline import RAGResult

    mock_result = RAGResult(
        answer="Article 21 guarantees right to life.",
        citations=[],
        related_cases=[],
        rewritten_query="Article 21 right to life",
        context_used=True,
        sufficient_context=True,
        latency_ms=450,
        token_count=120,
    )

    async def fake_stream(*args, **kwargs):
        yield StreamChunk(type="text", content="Article 21 ")
        yield StreamChunk(type="text", content="guarantees right to life.")
        yield StreamChunk(type="citation", citations=[])

    with patch("app.api.v1.endpoints.chat.RAGPipeline") as MockPipeline:
        instance = MockPipeline.return_value
        instance.run = AsyncMock(return_value=mock_result)
        instance.stream = fake_stream
        yield instance


@pytest.mark.asyncio
async def test_chat_non_stream(
    client: AsyncClient,
    auth_headers: dict,
    mock_rag_pipeline,
):
    resp = await client.post(
        "/api/v1/chat/",
        json={"message": "What is Article 21?", "stream": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "conversation_id" in data
    assert data["sufficient_context"] is True


@pytest.mark.asyncio
async def test_chat_creates_conversation(
    client: AsyncClient,
    auth_headers: dict,
    mock_rag_pipeline,
):
    resp = await client.post(
        "/api/v1/chat/",
        json={"message": "Explain basic structure doctrine", "stream": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    conversation_id = resp.json()["conversation_id"]
    assert conversation_id

    # Fetch the conversation
    conv_resp = await client.get(
        f"/api/v1/chat/conversations/{conversation_id}",
        headers=auth_headers,
    )
    assert conv_resp.status_code == 200
    assert len(conv_resp.json()["messages"]) == 2  # user + assistant


@pytest.mark.asyncio
async def test_list_conversations(
    client: AsyncClient,
    auth_headers: dict,
):
    resp = await client.get("/api/v1/chat/conversations", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_delete_conversation(
    client: AsyncClient,
    auth_headers: dict,
    mock_rag_pipeline,
):
    create_resp = await client.post(
        "/api/v1/chat/",
        json={"message": "Test", "stream": False},
        headers=auth_headers,
    )
    conv_id = create_resp.json()["conversation_id"]

    del_resp = await client.delete(
        f"/api/v1/chat/conversations/{conv_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(
        f"/api/v1/chat/conversations/{conv_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_rejects_non_owners_conversation(
    client: AsyncClient,
    auth_headers: dict,
):
    # A random non-existent UUID should 404
    resp = await client.get(
        "/api/v1/chat/conversations/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404
