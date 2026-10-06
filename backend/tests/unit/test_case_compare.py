"""Unit tests for grounded case comparison and research-stage statuses
(mocked retrieval, reranker and LLM — no database, no network)."""

from unittest.mock import AsyncMock, patch

import pytest

CASE_A = {"case_id": "case-a", "case_name": "Kesavananda Bharati v. State of Kerala"}
CASE_B = {"case_id": "case-b", "case_name": "Minerva Mills v. Union of India"}


def _search_for(case_passages):
    """similarity_search mock that returns each case's own passages."""

    async def search(query, n_results, where):
        case_id = where["case_id"]["$eq"]
        docs = case_passages[case_id]
        return {
            "documents": [docs],
            "metadatas": [[{"case_id": case_id, "chunk_index": i} for i in range(len(docs))]],
            "distances": [[0.1] * len(docs)],
        }

    return search


def _patched(scores_by_case, answer="### Case A\nHeld X [1].\n### Case B\nHeld Y [2]."):
    passages = {"case-a": ["A passage one", "A passage two"], "case-b": ["B passage one", "B passage two"]}

    async def rerank(query, docs, top_k=None):
        case_scores = scores_by_case["case-a" if docs[0].startswith("A") else "case-b"]
        return list(enumerate(case_scores))[:top_k]

    return (
        patch("app.services.ai.rag_pipeline.rewrite_query", new=AsyncMock(side_effect=lambda q, case_name=None: q)),
        patch("app.services.ai.rag_pipeline.EmbeddingService"),
        patch("app.services.ai.rag_pipeline.Reranker"),
        patch("app.services.ai.rag_pipeline.generate_text", new=AsyncMock(return_value=answer)),
        passages,
        rerank,
    )


async def _run_compare(scores_by_case, answer=None):
    from app.services.ai.rag_pipeline import RAGPipeline

    p_rewrite, p_embed, p_rerank, p_gen, passages, rerank = (
        _patched(scores_by_case) if answer is None else _patched(scores_by_case, answer)
    )
    with p_rewrite, p_embed as MockEmbed, p_rerank as MockReranker, p_gen as mock_generate:
        MockEmbed.return_value.similarity_search = AsyncMock(side_effect=_search_for(passages))
        MockReranker.return_value.rerank = AsyncMock(side_effect=rerank)
        result = await RAGPipeline().compare(CASE_A, CASE_B, "How are they related?")
        return result, mock_generate


@pytest.mark.asyncio
async def test_compare_is_grounded_in_both_cases():
    result, mock_generate = await _run_compare({"case-a": [0.9, 0.7], "case-b": [0.95, 0.8]})

    assert result.sufficient_context is True
    case_ids = [c.case_id for c in result.citations]
    assert case_ids == ["case-a", "case-a", "case-b", "case-b"]
    assert [c.rank for c in result.citations] == [1, 2, 3, 4]
    assert result.citations[0].chunk_id == "case-a__chunk_0"
    # The LLM saw passages labelled with the judgment they came from.
    prompt = mock_generate.await_args.args[0]
    assert "(Case A: Kesavananda Bharati v. State of Kerala)" in prompt
    assert "(Case B: Minerva Mills v. Union of India)" in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("weak_side", ["case-a", "case-b"])
async def test_compare_refuses_when_either_case_lacks_evidence(weak_side):
    from app.services.ai.prompt_templates import COMPARE_INSUFFICIENT

    scores = {"case-a": [0.9, 0.8], "case-b": [0.9, 0.8]}
    scores[weak_side] = [0.2, 0.1]  # below SIMILARITY_THRESHOLD (0.6)
    result, mock_generate = await _run_compare(scores)

    assert result.sufficient_context is False
    assert result.answer == COMPARE_INSUFFICIENT
    assert result.citations == []
    mock_generate.assert_not_awaited()  # no LLM call without evidence


@pytest.mark.asyncio
async def test_compare_drops_out_of_range_citation_markers():
    result, _ = await _run_compare(
        {"case-a": [0.9], "case-b": [0.9]}, answer="Case A held X [1]. Case B held Y [2]. Bogus [9]."
    )
    assert "[9]" not in result.answer and "[1]" in result.answer and "[2]" in result.answer


@pytest.mark.asyncio
async def test_compare_respects_llm_insufficient_answer():
    from app.services.ai.prompt_templates import COMPARE_INSUFFICIENT

    result, _ = await _run_compare({"case-a": [0.9], "case-b": [0.9]}, answer=COMPARE_INSUFFICIENT)
    assert result.sufficient_context is False and result.citations == []


@pytest.mark.asyncio
async def test_section_level_insufficiency_does_not_discard_comparison():
    from app.services.ai.prompt_templates import COMPARE_INSUFFICIENT

    answer = (
        "### Case A\nHeld X [1].\n### Case B\nHeld Y [2].\n"
        f"### How they relate\n{COMPARE_INSUFFICIENT}\n### Key differences\n- X vs Y [1][2]"
    )
    result, _ = await _run_compare({"case-a": [0.9], "case-b": [0.9]}, answer=answer)
    assert result.sufficient_context is True
    assert len(result.citations) == 2


@pytest.mark.asyncio
async def test_stream_emits_real_stage_statuses_in_order():
    from app.services.ai.rag_pipeline import RAGPipeline

    async def fake_stream(*_args, **_kwargs):
        yield "Answer [1]."

    with (
        patch("app.services.ai.rag_pipeline.rewrite_query", new=AsyncMock(return_value="q")),
        patch("app.services.ai.rag_pipeline.EmbeddingService") as MockEmbed,
        patch("app.services.ai.rag_pipeline.Reranker") as MockReranker,
        patch("app.services.ai.rag_pipeline.stream_text", new=fake_stream),
    ):
        MockEmbed.return_value.similarity_search = AsyncMock(
            return_value={
                "documents": [["passage"]],
                "metadatas": [[{"case_id": "c", "case_name": "C", "chunk_index": 3}]],
                "distances": [[0.1]],
            }
        )
        MockReranker.return_value.rerank = AsyncMock(return_value=[(0, 0.9)])
        events = [e async for e in RAGPipeline().stream("question")]

    statuses = [e.content for e in events if e.type == "status"]
    assert statuses == ["understanding", "retrieving", "reranking", "generating"]
    kinds = [e.type for e in events]
    assert kinds.index("citation") < kinds.index("text")
    citation = next(e for e in events if e.type == "citation").citations[0]
    assert citation.chunk_id == "c__chunk_3"
