"""Unit tests for inline citation enforcement."""
from backend.app.services.ai.rag_pipeline import RAGPipeline


def strip(answer: str, num_docs: int) -> str:
    return RAGPipeline._strip_invalid_citations(answer, num_docs)


def test_valid_citations_kept():
    assert strip("The court held X [1].", 3) == "The court held X [1]."


def test_out_of_range_removed():
    result = strip("This is unsupported [6].", 5)
    assert "[6]" not in result


def test_citation_zero_removed():
    result = strip("See [0] for details.", 5)
    assert "[0]" not in result


def test_mixed_valid_invalid():
    result = strip("Cited in [1,4,7].", 5)
    # 7 is invalid (>5), should be stripped from the group
    assert "7" not in result
    assert "1" in result
    assert "4" in result


def test_no_citations_unchanged():
    text = "There are no citations here."
    assert strip(text, 5) == text


def test_multiple_citations():
    result = strip("Held [1]. Also [2] and [3]. Invalid [10].", 3)
    assert "[1]" in result
    assert "[2]" in result
    assert "[3]" in result
    assert "[10]" not in result
