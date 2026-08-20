"""Targeted tests for llm_provider.py.

- Ollama request timeout configuration: verifies the configured timeout
  actually reaches the async httpx client ChatOllama uses for
  .ainvoke()/.astream() — no network call is made; this only inspects the
  constructed client's configuration.
- Groq configuration (model/timeout/missing-key): same "inspect the
  constructed client, make no network call" approach as the Ollama test.
  No real GROQ_API_KEY is ever used — a fake, obviously-non-real string.
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

from app.core.config import settings
from app.services.ai.llm_provider import _build_llm, generate_text, get_llm, stream_text


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


def test_groq_timeout_reaches_client(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "fake-test-key-not-real")

    llm = _build_llm(
        provider="groq",
        model="test-groq-timeout-model",
        base_url="unused-for-groq",
        temperature=0.1,
        max_tokens=100,
        timeout=42,
    )

    assert llm.async_client._client.timeout == 42.0


def test_groq_model_configuration_reaches_provider(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "fake-test-key-not-real")

    llm = _build_llm(
        provider="groq",
        model="test-groq-model-config-model",
        base_url="unused-for-groq",
        temperature=0.2,
        max_tokens=512,
        timeout=30,
    )

    assert llm.model_name == "test-groq-model-config-model"
    assert llm.temperature == 0.2
    assert llm.max_tokens == 512
    assert llm.streaming is True


def test_groq_missing_api_key_raises_clearly(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")

    with pytest.raises(Exception, match="api_key"):
        _build_llm(
            provider="groq",
            model="test-groq-missing-key-model",
            base_url="unused-for-groq",
            temperature=0.1,
            max_tokens=100,
            timeout=10,
        )


def test_unsupported_provider_raises_value_error():
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        _build_llm(
            provider="not-a-real-provider",
            model="test-model",
            base_url="unused",
            temperature=0.1,
            max_tokens=100,
            timeout=10,
        )


def test_get_llm_uses_the_provider_specific_model_setting(monkeypatch):
    """Regression test: get_llm() previously always passed settings.LLM_MODEL
    (the Ollama-style default) to _build_llm() regardless of LLM_PROVIDER,
    so selecting LLM_PROVIDER=groq/openai/anthropic silently ignored
    GROQ_MODEL/OPENAI_MODEL/ANTHROPIC_MODEL and tried to call the real
    provider with an Ollama model name — caught by making a real, live Groq
    API call, which every existing (fully mocked) test had missed since
    they all call _build_llm() directly with an explicit model, bypassing
    get_llm()'s wiring entirely."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "fake-test-key-not-real")
    monkeypatch.setattr(settings, "GROQ_MODEL", "test-provider-specific-model")
    monkeypatch.setattr(settings, "LLM_MODEL", "llama3.1:8b")  # must NOT be used

    llm = get_llm()

    assert llm.model_name == "test-provider-specific-model"


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
