"""
Full RAG pipeline:
Query → Rewrite → Embed → Retrieve → Rerank → Build Context → LLM → Answer + Citations
"""
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from loguru import logger

from app.core.config import settings
from app.core.exceptions import InsufficientContextError
from app.schemas.chat import Citation, RelatedCase, StreamChunk
from app.services.ai.embedding_service import EmbeddingService
from app.services.ai.llm_provider import generate_text, stream_text
from app.services.ai.prompt_templates import (
    LEGAL_QA_SYSTEM,
    LEGAL_QA_USER,
)
from app.services.ai.query_rewriter import rewrite_query
from app.services.ai.reranker import Reranker


@dataclass
class RAGResult:
    answer: str
    citations: list[Citation]
    related_cases: list[RelatedCase] = field(default_factory=list)
    rewritten_query: str | None = None
    context_used: bool = True
    sufficient_context: bool = True
    latency_ms: int = 0
    token_count: int | None = None


class RAGPipeline:
    def __init__(self) -> None:
        self._embedder: EmbeddingService | None = None
        self._reranker: Reranker | None = None

    @property
    def embedder(self) -> EmbeddingService:
        if self._embedder is None:
            self._embedder = EmbeddingService()
        return self._embedder

    @property
    def reranker(self) -> Reranker:
        if self._reranker is None:
            self._reranker = Reranker()
        return self._reranker

    async def run(
        self,
        query: str,
        conversation_history: list[Any] | None = None,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> RAGResult:
        start = time.perf_counter()
        top_k = top_k or settings.TOP_K_RERANKED

        # Step 1: Rewrite query
        rewritten = await rewrite_query(query)
        logger.debug(f"Query rewritten: '{query}' → '{rewritten}'")

        # Step 2: Retrieve from vector DB
        chroma_filters = self._build_chroma_filters(filters)
        raw_results = await self.embedder.similarity_search(
            query=rewritten,
            n_results=settings.TOP_K_RETRIEVAL,
            where=chroma_filters,
        )

        documents = raw_results.get("documents", [[]])[0]
        metadatas = raw_results.get("metadatas", [[]])[0]
        distances = raw_results.get("distances", [[]])[0]

        if not documents:
            return RAGResult(
                answer="The uploaded legal corpus does not contain sufficient evidence to answer this question.",
                citations=[],
                rewritten_query=rewritten,
                context_used=False,
                sufficient_context=False,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )

        # Step 3: Rerank
        reranked = await self.reranker.rerank(rewritten, documents, top_k=top_k)

        # Step 4: Build context and citations
        context_parts = []
        pre_citations = []
        for rank, (orig_idx, score) in enumerate(reranked):
            doc = documents[orig_idx]
            meta = metadatas[orig_idx] if orig_idx < len(metadatas) else {}
            similarity = 1 - (distances[orig_idx] if orig_idx < len(distances) else 0)

            context_parts.append(
                f"[Document {rank + 1}]\n"
                f"Case: {meta.get('case_name', 'Unknown')}\n"
                f"Court: {meta.get('court', 'N/A')} | Date: {meta.get('date', 'N/A')}\n"
                f"Content: {doc}\n"
            )
            pre_citations.append({
                "rank": rank + 1,
                "case_id": meta.get("case_id", ""),
                "case_name": meta.get("case_name", "Unknown"),
                "chunk_id": f"{meta.get('case_id', '')}__chunk_{meta.get('chunk_index', 0)}",
                "content": doc[:500],
                "similarity_score": round(score, 4),
                "court": meta.get("court"),
                "date": meta.get("date"),
            })

        context = "\n\n---\n\n".join(context_parts)
        history_text = self._format_history(conversation_history or [])

        # Step 5: Check context quality
        max_score = max(score for _, score in reranked) if reranked else 0
        if max_score < settings.SIMILARITY_THRESHOLD:
            return RAGResult(
                answer="The uploaded legal corpus does not contain sufficient evidence to answer this question.",
                citations=[Citation(**c) for c in pre_citations],
                rewritten_query=rewritten,
                context_used=True,
                sufficient_context=False,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )

        # Step 6: Generate answer
        user_prompt = LEGAL_QA_USER.format(
            context=context,
            history=history_text,
            question=query,
        )
        answer = await generate_text(user_prompt, system_prompt=LEGAL_QA_SYSTEM)

        citations = [Citation(**c) for c in pre_citations]
        latency_ms = int((time.perf_counter() - start) * 1000)

        return RAGResult(
            answer=answer,
            citations=citations,
            rewritten_query=rewritten,
            context_used=True,
            sufficient_context=True,
            latency_ms=latency_ms,
        )

    async def stream(
        self,
        query: str,
        conversation_history: list[Any] | None = None,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        _INSUFFICIENT = "The uploaded legal corpus does not contain sufficient evidence to answer this question."
        top_k = top_k or settings.TOP_K_RERANKED

        rewritten = await rewrite_query(query)
        chroma_filters = self._build_chroma_filters(filters)
        raw_results = await self.embedder.similarity_search(
            query=rewritten,
            n_results=settings.TOP_K_RETRIEVAL,
            where=chroma_filters,
        )

        documents = raw_results.get("documents", [[]])[0]
        metadatas = raw_results.get("metadatas", [[]])[0]
        distances = raw_results.get("distances", [[]])[0]

        if not documents:
            yield StreamChunk(type="text", content=_INSUFFICIENT)
            return

        reranked = await self.reranker.rerank(rewritten, documents, top_k=top_k)

        # Gate: check reranker score before generating or yielding citations
        max_score = max(score for _, score in reranked) if reranked else 0
        if max_score < settings.SIMILARITY_THRESHOLD:
            yield StreamChunk(type="text", content=_INSUFFICIENT)
            return

        context_parts = []
        citations_data = []
        for rank, (orig_idx, score) in enumerate(reranked):
            doc = documents[orig_idx]
            meta = metadatas[orig_idx] if orig_idx < len(metadatas) else {}
            similarity = 1 - (distances[orig_idx] if orig_idx < len(distances) else 0)
            context_parts.append(
                f"[Document {rank + 1}]\n"
                f"Case: {meta.get('case_name', 'Unknown')}\n"
                f"Court: {meta.get('court', 'N/A')} | Date: {meta.get('date', 'N/A')}\n"
                f"Content: {doc}\n"
            )
            citations_data.append(Citation(
                rank=rank + 1,
                case_id=meta.get("case_id", ""),
                case_name=meta.get("case_name", "Unknown"),
                chunk_id=f"{meta.get('case_id', '')}__chunk_{meta.get('chunk_index', 0)}",
                content=doc[:500],
                similarity_score=round(score, 4),
                court=meta.get("court"),
                date=meta.get("date"),
            ))

        # Yield citations only after the threshold gate passes
        yield StreamChunk(type="citation", citations=citations_data)

        context = "\n\n---\n\n".join(context_parts)
        history_text = self._format_history(conversation_history or [])
        user_prompt = LEGAL_QA_USER.format(
            context=context,
            history=history_text,
            question=query,
        )

        async for text_chunk in stream_text(user_prompt, system_prompt=LEGAL_QA_SYSTEM):
            yield StreamChunk(type="text", content=text_chunk)

    def _build_chroma_filters(self, filters: dict[str, Any] | None) -> dict | None:
        if not filters:
            return None
        where: dict[str, Any] = {}
        if filters.get("court"):
            where["court"] = {"$eq": filters["court"]}
        return where if where else None

    def _format_history(self, history: list[Any]) -> str:
        if not history:
            return "No prior conversation."
        lines = []
        for msg in history[-6:]:  # Last 3 turns
            role = getattr(msg, "role", "unknown")
            content = getattr(msg, "content", "")[:200]
            lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines)
