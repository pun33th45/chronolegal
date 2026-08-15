"""Unit tests for the RAG pipeline (mocked external services)."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_rag_run_returns_result():
    from app.services.ai.rag_pipeline import RAGPipeline

    with (
        patch(
            "app.services.ai.rag_pipeline.rewrite_query",
            new=AsyncMock(return_value="Article 21 right to life"),
        ),
        patch("app.services.ai.rag_pipeline.EmbeddingService") as MockEmbed,
        patch("app.services.ai.rag_pipeline.Reranker") as MockReranker,
        patch(
            "app.services.ai.rag_pipeline.generate_text",
            new=AsyncMock(return_value="Article 21 guarantees life and liberty."),
        ) as mock_generate,
    ):
        mock_embed = MockEmbed.return_value
        mock_embed.similarity_search = AsyncMock(
            return_value={
                "documents": [["Article 21 text excerpt..."]],
                "metadatas": [
                    [{"case_id": "maneka-1978", "case_name": "Maneka Gandhi"}]
                ],
                "distances": [[0.1]],
            }
        )

        mock_reranker = MockReranker.return_value
        mock_reranker.rerank = AsyncMock(return_value=[(0, 0.95)])

        pipeline = RAGPipeline()
        result = await pipeline.run(query="What is Article 21?", top_k=3)

        assert result.answer == "Article 21 guarantees life and liberty."
        assert result.sufficient_context is True
        assert result.latency_ms >= 0
        mock_generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_rag_insufficient_context():
    from app.services.ai.rag_pipeline import RAGPipeline

    with (
        patch(
            "app.services.ai.rag_pipeline.rewrite_query",
            new=AsyncMock(return_value="XYZ"),
        ),
        patch("app.services.ai.rag_pipeline.EmbeddingService") as MockEmbed,
        patch("app.services.ai.rag_pipeline.Reranker") as MockReranker,
        patch(
            "app.services.ai.rag_pipeline.generate_text", new=AsyncMock()
        ) as mock_generate,
    ):
        mock_embed = MockEmbed.return_value
        mock_embed.similarity_search = AsyncMock(
            return_value={
                "documents": [["very distant text"]],
                "metadatas": [[{"case_id": "abc", "case_name": "Unknown Case"}]],
                "distances": [[0.98]],  # Very high distance = low similarity
            }
        )

        mock_reranker = MockReranker.return_value
        mock_reranker.rerank = AsyncMock(return_value=[(0, 0.02)])

        pipeline = RAGPipeline()
        result = await pipeline.run(query="XYZ irrelevant", top_k=3)

        assert result.sufficient_context is False
        # The similarity-threshold gate must short-circuit before ever calling the LLM.
        mock_generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_rag_stream_yields_chunks():
    from app.services.ai.rag_pipeline import RAGPipeline

    async def fake_stream_text(*args, **kwargs):
        for token in ["Article ", "21 ", "text."]:
            yield token

    with (
        patch(
            "app.services.ai.rag_pipeline.rewrite_query",
            new=AsyncMock(return_value="Article 21"),
        ),
        patch("app.services.ai.rag_pipeline.EmbeddingService") as MockEmbed,
        patch("app.services.ai.rag_pipeline.Reranker") as MockReranker,
        patch("app.services.ai.rag_pipeline.stream_text", new=fake_stream_text),
    ):
        mock_embed = MockEmbed.return_value
        mock_embed.similarity_search = AsyncMock(
            return_value={
                "documents": [["Maneka Gandhi text"]],
                "metadatas": [
                    [{"case_id": "maneka-1978", "case_name": "Maneka Gandhi"}]
                ],
                "distances": [[0.05]],
            }
        )

        mock_reranker = MockReranker.return_value
        mock_reranker.rerank = AsyncMock(return_value=[(0, 0.92)])

        pipeline = RAGPipeline()
        chunks = []
        async for chunk in pipeline.stream(query="What is Article 21?", top_k=3):
            chunks.append(chunk)

        text_chunks = [c for c in chunks if c.type == "text"]
        assert len(text_chunks) > 0
        assert "".join(c.content for c in text_chunks) == "Article 21 text."
