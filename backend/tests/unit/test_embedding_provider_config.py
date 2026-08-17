"""Verifies embedding_service.py's provider/backend selection logic
(EMBEDDING_PROVIDER, CHROMA_MODE) without touching real network or disk
resources. These are branch-selection tests, not model-loading tests —
actually loading BAAI/bge-large-en-v1.5 or talking to a real Chroma/OpenAI
endpoint is deliberately out of scope for a fast unit test.
"""

import langchain_openai
import pytest

from app.core.config import settings
from app.services.ai import embedding_service


@pytest.fixture(autouse=True)
def _clear_caches():
    embedding_service._get_embedding_model.cache_clear()
    embedding_service._get_chroma_client.cache_clear()
    yield
    embedding_service._get_embedding_model.cache_clear()
    embedding_service._get_chroma_client.cache_clear()


def test_default_embedding_provider_is_huggingface(monkeypatch):
    """Existing self-hosted deployments must keep loading the local model
    unless EMBEDDING_PROVIDER is explicitly changed."""
    captured = {}

    class _FakeHFEmbeddings:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(embedding_service, "HuggingFaceEmbeddings", _FakeHFEmbeddings)
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "huggingface")

    model = embedding_service._get_embedding_model()

    assert isinstance(model, _FakeHFEmbeddings)
    assert captured["model_name"] == settings.EMBEDDING_MODEL


def test_openai_embedding_provider_is_selected_when_configured(monkeypatch):
    captured = {}

    class _FakeOpenAIEmbeddings:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(langchain_openai, "OpenAIEmbeddings", _FakeOpenAIEmbeddings)
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test")

    model = embedding_service._get_embedding_model()

    assert isinstance(model, _FakeOpenAIEmbeddings)
    assert captured["model"] == "text-embedding-3-small"
    assert captured["api_key"] == "sk-test"


def test_default_chroma_mode_is_http(monkeypatch):
    """Existing self-hosted Docker Compose deployments must keep talking to
    an external Chroma server unless CHROMA_MODE is explicitly changed."""
    captured = {}

    def _fake_http_client(**kwargs):
        captured.update(kwargs)
        return "http-client-sentinel"

    monkeypatch.setattr(embedding_service.chromadb, "HttpClient", _fake_http_client)
    monkeypatch.setattr(settings, "CHROMA_MODE", "http")

    client = embedding_service._get_chroma_client()

    assert client == "http-client-sentinel"
    assert captured == {"host": settings.CHROMA_HOST, "port": settings.CHROMA_PORT}


def test_embedded_chroma_mode_uses_persistent_client(monkeypatch, tmp_path):
    captured = {}

    def _fake_persistent_client(**kwargs):
        captured.update(kwargs)
        return "persistent-client-sentinel"

    monkeypatch.setattr(
        embedding_service.chromadb, "PersistentClient", _fake_persistent_client
    )
    monkeypatch.setattr(settings, "CHROMA_MODE", "embedded")
    monkeypatch.setattr(settings, "CHROMA_PERSIST_DIRECTORY", str(tmp_path))

    client = embedding_service._get_chroma_client()

    assert client == "persistent-client-sentinel"
    assert captured == {"path": str(tmp_path)}
