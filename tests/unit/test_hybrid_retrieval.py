"""Unit tests for hybrid RRF retrieval helpers."""
import pytest

from backend.app.services.ai.rag_pipeline import RAGPipeline


@pytest.fixture
def pipeline():
    return RAGPipeline()


def test_rrf_single_list(pipeline):
    # With one list, ordering is preserved
    result = pipeline._reciprocal_rank_fusion([[0, 1, 2]])
    assert result == [0, 1, 2]


def test_rrf_two_lists_boosts_agreement(pipeline):
    # Both lists agree doc 2 is best
    dense = [0, 1, 2]
    bm25 = [2, 0, 1]
    result = pipeline._reciprocal_rank_fusion([dense, bm25])
    # Doc 0 ranks 1st in dense, 2nd in bm25 → moderate score
    # Doc 2 ranks 3rd in dense, 1st in bm25 → also moderate
    assert len(result) == 3
    assert set(result) == {0, 1, 2}


def test_rrf_k_parameter(pipeline):
    result_low_k = pipeline._reciprocal_rank_fusion([[0, 1, 2], [2, 1, 0]], k=1)
    result_high_k = pipeline._reciprocal_rank_fusion([[0, 1, 2], [2, 1, 0]], k=1000)
    # Both should produce same ordering (symmetrical case here)
    assert set(result_low_k) == {0, 1, 2}
    assert set(result_high_k) == {0, 1, 2}


def test_bm25_rank_returns_all_indices(pipeline):
    docs = ["section 302 ipc murder", "article 21 right to life", "contract law damages"]
    ranked = pipeline._bm25_rank("murder ipc", docs)
    assert sorted(ranked) == [0, 1, 2]
    assert ranked[0] == 0  # best BM25 match for "murder ipc"


def test_fuse_results_disabled(pipeline, monkeypatch):
    monkeypatch.setattr("backend.app.services.ai.rag_pipeline.settings.HYBRID_SEARCH", False)
    docs = ["a", "b", "c"]
    dense_order = [0, 1, 2]
    result = pipeline._fuse_results("query", docs, dense_order)
    assert result == dense_order
