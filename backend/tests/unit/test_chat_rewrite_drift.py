"""Regression: Chat (RAGPipeline.run / .stream) must keep the relevant judgment
in its evidence when the LLM query rewrite drifts — pads the question with
invented statutes and case names that pull dense retrieval toward unrelated,
larger judgments. Same failure mode reproduced live for /search.
Mocked retrieval/reranker/LLM/cache — no database, no network."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.rag_pipeline import RAGPipeline

QUESTION = "What principle was established by the judgment?"
DRIFTED = (
    "What principle was established by the judgment concerning Section 304B of the "
    "Indian Penal Code and State of Maharashtra v. M. R. N. (2018)?"
)
TARGET = "upload_target-case"
BIG = "upload_big-case"
INSUFFICIENT = "The uploaded legal corpus does not contain sufficient evidence to answer this question."


def _result(case_id, n, start=0):
    rng = range(start, start + n)
    return {
        "ids": [[f"{case_id}__chunk_{i}" for i in rng]],
        "documents": [[f"{case_id} passage {i}" for i in rng]],
        "metadatas": [[{"case_id": case_id, "case_name": case_id, "chunk_index": i} for i in rng]],
        "distances": [[0.05 + 0.001 * i for i in range(n)]],
    }


def _concat(*results):
    return {k: [sum((r[k][0] for r in results), [])] for k in results[0]}


async def _similarity_search(query, n_results, where=None):
    """Mimics the live index: the user's own wording finds the target case;
    the drifted rewrite only reaches the big judgment. A case_id filter is
    honoured exactly like Chroma's `where`."""
    if where and "case_id" in where:
        cid = where["case_id"]["$eq"]
        return _result(cid, 3)
    if query == QUESTION:
        return _concat(_result(TARGET, 2), _result(BIG, n_results - 2))
    return _result(BIG, n_results, start=100)


def _rerank_scores(target_score=0.95, other_score=0.1):
    async def rerank(query, documents, top_k=None):
        scored = [(i, target_score if TARGET in d else other_score) for i, d in enumerate(documents)]
        return sorted(scored, key=lambda s: s[1], reverse=True)[:top_k]

    return rerank


def _pipeline(rewrite=DRIFTED, rerank=None):
    p = RAGPipeline()
    p._embedder = AsyncMock()
    p._embedder.similarity_search.side_effect = _similarity_search
    p._reranker = AsyncMock()
    p._reranker.rerank.side_effect = rerank or _rerank_scores()
    stack = ExitStack()
    stack.enter_context(patch("app.services.ai.rag_pipeline.rewrite_query", new=AsyncMock(return_value=rewrite)))
    stack.enter_context(patch("app.services.ai.rag_pipeline.cache", new=AsyncMock(get=AsyncMock(return_value=None))))
    gen = stack.enter_context(patch("app.services.ai.rag_pipeline.generate_text", new=AsyncMock(return_value="Held X [1].")))

    async def _stream(*_a, **_k):
        yield "Held X [1]."

    stack.enter_context(patch("app.services.ai.rag_pipeline.stream_text", new=_stream))
    return p, gen, stack


def _reranked_with(p):
    return [c.args[0] for c in p._reranker.rerank.call_args_list]


def _searched_queries(p):
    return sorted(c.kwargs["query"] for c in p._embedder.similarity_search.call_args_list)


async def test_run_keeps_target_case_despite_rewrite_drift():
    p, gen, stack = _pipeline()
    with stack:
        res = await p.run(QUESTION)
    assert res.sufficient_context is True
    assert res.citations and res.citations[0].case_id == TARGET
    assert _searched_queries(p) == sorted([QUESTION, DRIFTED])
    assert QUESTION in _reranked_with(p)  # the original question is always scored
    assert res.rewritten_query == DRIFTED


async def test_stream_keeps_target_case_despite_rewrite_drift():
    p, _, stack = _pipeline()
    with stack:
        chunks = [c async for c in p.stream(QUESTION)]
    statuses = [c.content for c in chunks if c.type == "status"]
    assert statuses == ["understanding", "retrieving", "reranking", "generating"]
    citations = next(c.citations for c in chunks if c.type == "citation")
    assert citations[0].case_id == TARGET
    assert QUESTION in _reranked_with(p)


async def test_normal_question_without_drift_searches_once():
    p, _, stack = _pipeline(rewrite=QUESTION)  # rewrite identical to the question
    with stack:
        res = await p.run(QUESTION)
    assert p._embedder.similarity_search.call_count == 1
    assert res.citations[0].case_id == TARGET


@pytest.mark.parametrize("mode", ["run", "stream"])
async def test_case_scoped_chat_only_retrieves_the_requested_case(mode):
    scoped = "upload_scoped-case"
    p, _, stack = _pipeline(rerank=_rerank_scores(other_score=0.9))
    with stack:
        if mode == "run":
            citations = (await p.run(QUESTION, filters={"case_id": scoped})).citations
        else:
            chunks = [c async for c in p.stream(QUESTION, filters={"case_id": scoped})]
            citations = next(c.citations for c in chunks if c.type == "citation")
    # Every retrieval (original AND rewrite) carried the case filter...
    wheres = [c.kwargs["where"] for c in p._embedder.similarity_search.call_args_list]
    assert len(wheres) == 2 and all(w == {"case_id": {"$eq": scoped}} for w in wheres)
    # ...so every citation is from that case, with matching chunk ids.
    assert citations and {c.case_id for c in citations} == {scoped}
    assert all(c.chunk_id.startswith(f"{scoped}__chunk_") for c in citations)


async def test_unrelated_question_is_refused_without_generation():
    p, gen, stack = _pipeline(rerank=_rerank_scores(target_score=0.05, other_score=0.01))
    with stack:
        res = await p.run("Best recipe for chocolate chip cookies?")
        chunks = [c async for c in p.stream("Best recipe for chocolate chip cookies?")]
    assert res.sufficient_context is False and res.answer == INSUFFICIENT
    gen.assert_not_called()
    assert [c.content for c in chunks if c.type == "text"] == [INSUFFICIENT]
    assert not any(c.type == "citation" for c in chunks)


async def test_citation_ids_match_their_passages():
    p, _, stack = _pipeline()
    with stack:
        res = await p.run(QUESTION)
    for c in res.citations:
        assert c.chunk_id.startswith(f"{c.case_id}__chunk_")
        assert c.content.startswith(c.case_id)  # passage text belongs to the cited case


async def test_vague_question_still_benefits_from_the_rewrite():
    """Measured on real data: reranking a vague case-scoped question on its
    original wording alone scored 0.09 (refused) where the rewrite, which
    names the case and topic, scored 0.97. Keeping the better of the two
    scores must preserve that answer."""
    scoped = "upload_scoped-case"

    async def rerank(query, documents, top_k=None):
        score = 0.97 if query == DRIFTED else 0.09
        return [(i, score) for i in range(len(documents))][:top_k]

    p, gen, stack = _pipeline(rerank=rerank)
    with stack:
        res = await p.run(QUESTION, filters={"case_id": scoped})
    assert res.sufficient_context is True
    gen.assert_called_once()
    assert sorted(_reranked_with(p)) == sorted([QUESTION, DRIFTED])
    assert {c.case_id for c in res.citations} == {scoped}
