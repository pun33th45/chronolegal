"""Regression: Compare must build each side's evidence from the passages that
answer the question, even when the per-case query rewrite drifts. Measured on
real data: a case-name-stuffed rewrite kept selecting a procedural headnote
passage of Minerva Mills (best score 0.705, barely over the 0.6 gate) instead
of the passage on clauses (4)/(5) of Article 368 that the question asked about
(0.996). Mocked retrieval/reranker/LLM — no database, no network."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from app.services.ai.prompt_templates import COMPARE_INSUFFICIENT
from app.services.ai.rag_pipeline import RAGPipeline

CASE_A = {"case_id": "case-a", "case_name": "Kesavananda Bharati v. State of Kerala"}
CASE_B = {"case_id": "case-b", "case_name": "Minerva Mills v. Union of India"}
QUESTION = "Did the court strike down Sections 4 and 55 of the 42nd Amendment?"


def _drift(question, case_name=None):
    # Case-name-stuffed rewrite, as observed live.
    return f"{case_name} (31 July 1980) judgment, headnote, Supreme Court, {question}"


def _passage(cid, idx, text):
    return {"id": f"{cid}__chunk_{idx}", "doc": f"{cid} {text}", "meta": {"case_id": cid, "chunk_index": idx}}


async def _similarity_search(query, n_results, where=None):
    """Within each case, the user's question reaches the passage that answers
    it (chunk 7); the drifted rewrite only reaches the headnote (chunk 0)."""
    cid = where["case_id"]["$eq"]
    found = [_passage(cid, 0, "headnote: petitions challenged the amendment")]
    if query == QUESTION:
        found.insert(0, _passage(cid, 7, "relevant: clauses (4) and (5) of Article 368 struck down"))
    return {
        "ids": [[p["id"] for p in found]],
        "documents": [[p["doc"] for p in found]],
        "metadatas": [[p["meta"] for p in found]],
        "distances": [[0.1 + 0.01 * i for i in range(len(found))]],
    }


def _rerank(relevant=0.95, headnote_vs_rewrite=0.3, vs_rewrite_only=None):
    async def rerank(query, documents, top_k=None):
        scored = []
        for i, d in enumerate(documents):
            if vs_rewrite_only is not None:  # vague-question model: only the rewrite scores well
                s = vs_rewrite_only if query != QUESTION else 0.1
            elif "relevant" in d:
                s = relevant if query == QUESTION else 0.4
            else:
                s = headnote_vs_rewrite if query != QUESTION else 0.05
            scored.append((i, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k] if top_k else scored

    return rerank


def _pipeline(rewrite=_drift, rerank=None, answer="### Case A\nHeld X [1].\n### Case B\nHeld Y [2]."):
    p = RAGPipeline()
    p._embedder = AsyncMock()
    p._embedder.similarity_search.side_effect = _similarity_search
    p._reranker = AsyncMock()
    p._reranker.rerank.side_effect = rerank or _rerank()
    stack = ExitStack()
    stack.enter_context(patch("app.services.ai.rag_pipeline.rewrite_query", new=AsyncMock(side_effect=rewrite)))
    gen = stack.enter_context(patch("app.services.ai.rag_pipeline.generate_text", new=AsyncMock(return_value=answer)))
    return p, gen, stack


async def test_drifted_rewrite_still_cites_the_answering_passage():
    p, gen, stack = _pipeline()
    with stack:
        res = await p.compare(CASE_A, CASE_B, QUESTION, top_k_per_case=1)
    # Rewrite-only evidence would be the headnote at 0.3 -> refused. Now:
    assert res.sufficient_context is True
    assert [c.chunk_id for c in res.citations] == ["case-a__chunk_7", "case-b__chunk_7"]
    assert all("relevant" in c.content for c in res.citations)
    gen.assert_awaited_once()


async def test_normal_question_without_drift_searches_once_per_case():
    p, _, stack = _pipeline(rewrite=lambda q, case_name=None: q)
    with stack:
        res = await p.compare(CASE_A, CASE_B, QUESTION, top_k_per_case=1)
    assert p._embedder.similarity_search.call_count == 2  # one per case, no duplicate
    assert res.sufficient_context is True


async def test_vague_question_keeps_the_rewrite_benefit():
    p, gen, stack = _pipeline(rerank=_rerank(vs_rewrite_only=0.9))
    with stack:
        res = await p.compare(CASE_A, CASE_B, "What principle was established?", top_k_per_case=1)
    assert res.sufficient_context is True  # better-of-two score, not original-only
    gen.assert_awaited_once()


async def test_every_retrieval_is_filtered_to_its_own_case():
    p, _, stack = _pipeline()
    with stack:
        res = await p.compare(CASE_A, CASE_B, QUESTION, top_k_per_case=2)
    wheres = [c.kwargs["where"]["case_id"]["$eq"] for c in p._embedder.similarity_search.call_args_list]
    assert sorted(wheres) == ["case-a", "case-a", "case-b", "case-b"]  # question + rewrite, per case
    assert [c.case_id for c in res.citations] == ["case-a", "case-a", "case-b", "case-b"]


async def test_citations_correspond_to_their_passages():
    p, _, stack = _pipeline()
    with stack:
        res = await p.compare(CASE_A, CASE_B, QUESTION, top_k_per_case=2)
    for c in res.citations:
        assert c.chunk_id.startswith(f"{c.case_id}__chunk_")
        assert c.content.startswith(c.case_id)
    assert [c.rank for c in res.citations] == [1, 2, 3, 4]


async def test_insufficient_evidence_still_refuses_without_generation():
    p, gen, stack = _pipeline(rerank=_rerank(relevant=0.2, headnote_vs_rewrite=0.1))
    with stack:
        res = await p.compare(CASE_A, CASE_B, "Best recipe for chocolate chip cookies?", top_k_per_case=1)
    assert res.sufficient_context is False and res.answer == COMPARE_INSUFFICIENT
    assert res.citations == []
    gen.assert_not_awaited()
