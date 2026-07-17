import pytest
from app.services.ai.chunker import TextChunker


def test_chunk_empty_text():
    chunker = TextChunker()
    assert chunker.chunk("") == []
    assert chunker.chunk("   ") == []


def test_chunk_short_text():
    chunker = TextChunker(chunk_size=512, chunk_overlap=64)
    text = "This is a short legal text."
    chunks = chunker.chunk(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_long_text():
    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    text = "word " * 200
    chunks = chunker.chunk(text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 120  # Some tolerance


def test_chunk_with_metadata():
    chunker = TextChunker(chunk_size=100, chunk_overlap=10)
    text = "legal text " * 50
    base_meta = {"case_id": "test-001", "case_name": "Test Case"}
    result = chunker.chunk_with_metadata(text, base_meta)

    assert len(result) > 0
    for chunk, meta in result:
        assert meta["case_id"] == "test-001"
        assert "chunk_index" in meta
        assert meta["chunk_index"] >= 0
