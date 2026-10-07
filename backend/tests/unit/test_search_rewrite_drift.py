"""Regression: a freshly uploaded judgment must stay findable in /search even
when the LLM query rewrite drifts (pads the query with invented statutes and
case names). Reproduced live: the drifted rewrite's nearest neighbours were all
from the largest judgment, so the new case never entered the candidate pool.
Mocked retrieval/reranker/LLM — no database, no network."""

from unittest.mock import AsyncMock, patch

from app.services.ai.search_service import SearchService

QUERY = "Can the State divert river water from downstream farmers without hearing them?"
DRIFTED = (
    "State diversion of river water: Article 31(1)(b), Indian Water Resources Act, 1975, "
    "Rule 4 of the Code of Civil Procedure; State of Maharashtra v. M. R. N. (2018)"
)
NEW_CASE = "upload_new-case"
BIG_CASE = "upload_big-case"


def _chunks(case_id, n, start=0):
    ids = [f"{case_id}__chunk_{i}" for i in range(start, start + n)]
    return {
        "ids": [ids],
        "documents": [[f"{case_id} passage {i}" for i in range(start, start + n)]],
        "metadatas": [[{"case_id": case_id, "case_name": case_id, "chunk_index": i} for i in range(start, start + n)]],
        "distances": [[0.05 + 0.001 * i for i in range(n)]],
    }


async def _similarity_search(query, n_results, where=None):
    # The user's own wording finds the new judgment first; the drifted rewrite
    # only reaches chunks of the big judgment (as observed on the live index).
    if query == QUERY:
        new = _chunks(NEW_CASE, 2)
        big = _chunks(BIG_CASE, n_results - 2)
        return {k: [new[k][0] + big[k][0]] for k in new}
    return _chunks(BIG_CASE, n_results, start=100)


async def _rerank(query, documents, top_k=None):
    # Cross-encoder stand-in: the new judgment's passages are most relevant.
    scores = [(i, 1.0 if NEW_CASE in d else 0.1) for i, d in enumerate(documents)]
    return sorted(scores, key=lambda s: s[1], reverse=True)[:top_k]


async def test_new_case_survives_drifted_rewrite():
    svc = SearchService()
    svc._embedder = AsyncMock()
    svc._embedder.similarity_search.side_effect = _similarity_search
    svc._reranker = AsyncMock()
    svc._reranker.rerank.side_effect = _rerank

    with patch("app.services.ai.search_service.rewrite_query", new=AsyncMock(return_value=DRIFTED)):
        resp = await svc.search(QUERY, top_k=10)

    assert resp.rewritten_query == DRIFTED
    assert resp.results[0].case_id == NEW_CASE
    # Both the original and the rewritten query were used for retrieval...
    searched = [c.kwargs["query"] for c in svc._embedder.similarity_search.call_args_list]
    assert sorted(searched) == sorted([QUERY, DRIFTED])
    # ...and reranking judged relevance against what the user actually asked.
    assert svc._reranker.rerank.call_args.args[0] == QUERY


def test_merge_candidates_dedupes_by_chunk_id_keeping_closest():
    a = _chunks(NEW_CASE, 2)
    b = _chunks(NEW_CASE, 1)
    b["distances"] = [[0.01]]  # same chunk id as a's first chunk, but closer
    docs, metas, dists = SearchService._merge_candidates([a, b])
    assert len(docs) == 2
    assert dists[0] == 0.01 and metas[0]["chunk_index"] == 0
