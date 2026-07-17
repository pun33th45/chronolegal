"""Unit tests for TextChunker and LegalChunker."""
import pytest

from backend.app.services.ai.chunker import LegalChunker, TextChunker, _split_by_legal_structure


# ---------------------------------------------------------------------------
# TextChunker — char_offset regression
# ---------------------------------------------------------------------------

def test_char_offset_advances_correctly():
    """Repeated phrases must map to distinct (start, end) positions."""
    text = "Whereas the parties agree. Whereas the parties agree. Final clause."
    chunker = TextChunker(chunk_size=30, chunk_overlap=5)
    chunks_meta = chunker.chunk_with_metadata(text, {})
    starts = [m["start_char"] for _, m in chunks_meta if m["start_char"] != -1]
    # All start positions should be strictly increasing
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts), "Duplicate start_char positions found"


def test_char_offset_no_negative_offsets():
    text = "One. " * 50
    chunker = TextChunker(chunk_size=20, chunk_overlap=5)
    chunks_meta = chunker.chunk_with_metadata(text, {})
    for _, meta in chunks_meta:
        if meta["start_char"] != -1:
            assert meta["start_char"] >= 0
            assert meta["end_char"] > meta["start_char"]


# ---------------------------------------------------------------------------
# Legal structure splitting
# ---------------------------------------------------------------------------

JUDGMENT = """IN THE SUPREME COURT OF INDIA

1. This is an appeal against the order of the High Court.

2. The facts of the case are as follows.

FACTS

The petitioner filed a writ petition challenging the order.

HELD

The court held that the impugned order is ultra vires.

CONCLUSION

The appeal is allowed."""


def test_split_by_legal_structure_detects_sections():
    sections = _split_by_legal_structure(JUDGMENT)
    assert len(sections) >= 3
    headers = [h for _, h in sections if h]
    assert any("FACTS" in (h or "") for h in headers)
    assert any("HELD" in (h or "") for h in headers)


def test_split_numbered_paragraphs():
    text = "Preamble text.\n\n1. First para.\n\n2. Second para.\n\n3. Third para."
    sections = _split_by_legal_structure(text)
    assert len(sections) >= 3


# ---------------------------------------------------------------------------
# LegalChunker
# ---------------------------------------------------------------------------

def test_legal_chunker_stores_section_header():
    chunker = LegalChunker(chunk_size=200, chunk_overlap=20)
    chunks = chunker.chunk_legal(JUDGMENT, {"case_id": "test"})
    assert chunks, "Expected non-empty chunk list"
    headers_in_meta = [m.get("section_header") for _, m in chunks]
    assert any(h for h in headers_in_meta), "Expected at least one non-None section_header"


def test_legal_chunker_fallback_for_short_text():
    short = "Just a short text with no legal structure."
    chunker = LegalChunker(chunk_size=50, chunk_overlap=5)
    chunks = chunker.chunk_legal(short, {})
    assert chunks, "Should still produce chunks via fallback"


def test_legal_chunker_chunk_index_monotonic():
    chunker = LegalChunker(chunk_size=100, chunk_overlap=10)
    chunks = chunker.chunk_legal(JUDGMENT, {})
    indices = [m["chunk_index"] for _, m in chunks]
    assert indices == list(range(len(chunks)))
