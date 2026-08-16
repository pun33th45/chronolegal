"""Targeted test for the Ollama request timeout configuration.

Verifies that the configured timeout actually reaches the async httpx
client ChatOllama uses for .ainvoke()/.astream() — no network call is
made; this only inspects the constructed client's configuration.
"""

import httpx

from app.services.ai.llm_provider import _build_llm


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
