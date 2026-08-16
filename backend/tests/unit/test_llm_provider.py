"""Targeted tests for llm_provider.py.

- Ollama request timeout configuration: verifies the configured timeout
  actually reaches the async httpx client ChatOllama uses for
  .ainvoke()/.astream() — no network call is made; this only inspects the
  constructed client's configuration.
- generate_text/stream_text content extraction: BaseMessage.content is
  typed str | list[str | dict] because some providers (e.g. Anthropic) can
  return a list of content blocks instead of plain text. These tests mock
  the chat model itself (no network call) to prove both shapes are
  normalized to plain strings.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.ai.llm_provider import _build_llm, generate_text, stream_text


def test_ollama_timeout_reaches_async_client():
    llm = _build_llm(
        provider="ollama",
        model="test-model",
        base_url="http://ollama:11434",
        temperature=0.1,
        max_tokens=100,
        timeout=42,
    )

    async_httpx_timeout = llm._async_client._client.timeout
    assert async_httpx_timeout == httpx.Timeout(42)


@pytest.mark.asyncio
async def test_generate_text_passes_through_plain_string_content():
    fake_llm = SimpleNamespace(
        ainvoke=AsyncMock(return_value=SimpleNamespace(content="Hello world"))
    )
    with patch("app.services.ai.llm_provider.get_llm", return_value=fake_llm):
        result = await generate_text("prompt")

    assert result == "Hello world"


@pytest.mark.asyncio
async def test_generate_text_extracts_text_from_content_blocks():
    """Simulates a provider (e.g. Anthropic with multiple blocks) returning
    content as a list of blocks rather than a plain string."""
    fake_content = [
        {"type": "text", "text": "Hello "},
        {"type": "text", "text": "world"},
    ]
    fake_llm = SimpleNamespace(
        ainvoke=AsyncMock(return_value=SimpleNamespace(content=fake_content))
    )
    with patch("app.services.ai.llm_provider.get_llm", return_value=fake_llm):
        result = await generate_text("prompt")

    assert result == "Hello world"
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_stream_text_extracts_text_from_content_blocks():
    async def fake_astream(_messages):
        yield SimpleNamespace(content=[{"type": "text", "text": "Hello "}])
        yield SimpleNamespace(content=[{"type": "text", "text": "world"}])

    fake_llm = SimpleNamespace(astream=fake_astream)
    with patch("app.services.ai.llm_provider.get_llm", return_value=fake_llm):
        chunks = [chunk async for chunk in stream_text("prompt")]

    assert chunks == ["Hello ", "world"]
