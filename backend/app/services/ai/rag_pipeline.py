"""
Full RAG pipeline:
Query → Rewrite → Embed → [BM25] → RRF Fuse → Rerank → Build Context → LLM → Answer + Citations
"""

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from loguru import logger

from app.core.config import settings
from app.core.redis import cache
from app.schemas.chat import Citation, RelatedCase, StreamChunk
from app.services.ai.embedding_service import EmbeddingService
from app.services.ai.llm_provider import generate_text, stream_text
from app.services.ai.prompt_templates import (
    CASE_COMPARE_SYSTEM,
    CASE_COMPARE_USER,
    COMPARE_INSUFFICIENT,
    LEGAL_QA_SYSTEM,
    LEGAL_QA_USER,
)
from app.services.ai.query_rewriter import rewrite_query
from app.services.ai.reranker import Reranker
from app.services.ai.search_service import SearchService

_RAG_CACHE_TTL = 3_600  # 1 hour — identical (query, filters) reuses the answer


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

    # ------------------------------------------------------------------
    # Hybrid retrieval helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _reciprocal_rank_fusion(
        ranked_lists: list[list[int]],
        k: int = 60,
    ) -> list[int]:
        """
        Fuse multiple ranked lists (of original document indices) using RRF.
        Returns indices sorted by descending fused score.
        """
        scores: dict[int, float] = {}
        for ranked in ranked_lists:
            for rank, idx in enumerate(ranked):
                scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
        return sorted(scores, key=lambda i: scores[i], reverse=True)

    def _bm25_rank(self, query: str, documents: list[str]) -> list[int]:
        """Return document indices sorted by BM25 score descending."""
        from rank_bm25 import BM25Okapi

        tokenized = [doc.lower().split() for doc in documents]
        bm25 = BM25Okapi(tokenized)
        scores = bm25.get_scores(query.lower().split())
        return sorted(range(len(documents)), key=lambda i: scores[i], reverse=True)

    def _fuse_results(
        self,
        query: str,
        documents: list[str],
        dense_order: list[int],
    ) -> list[int]:
        """
        If HYBRID_SEARCH is enabled, fuse dense + BM25 ranks via RRF.
        Otherwise return dense order unchanged.
        """
        if not settings.HYBRID_SEARCH or not documents:
            return dense_order
        bm25_order = self._bm25_rank(query, documents)
        return self._reciprocal_rank_fusion(
            [dense_order, bm25_order],
            k=settings.HYBRID_RRF_K,
        )

    async def _retrieve_candidates(
        self, query: str, rewritten: str, filters: dict[str, Any] | None
    ) -> tuple[list[str], list[dict]]:
        """Dense retrieval with BOTH the user's question and the LLM rewrite,
        merged and de-duplicated by chunk id. The rewrite can pad a question
        with invented statutes/case names that pull the query vector toward
        the largest judgments; the original wording keeps the relevant case
        in the pool. Both retrievals use the same filters, so case-scoped
        chat still only ever sees the requested case."""
        where = self._build_chroma_filters(filters)
        n_results = self._retrieval_n_results(filters)
        queries = [query] if rewritten == query else [query, rewritten]
        raws = await asyncio.gather(
            *(
                self.embedder.similarity_search(query=q, n_results=n_results, where=where)
                for q in queries
            )
        )
        documents, metadatas, _ = SearchService._merge_candidates(raws)
        return documents, metadatas

    async def _rerank(
        self, query: str, rewritten: str, documents: list[str], top_k: int
    ) -> list[tuple[int, float]]:
        """Score each passage against the user's question AND the rewrite and
        keep the better score. The original wording protects against a
        drifted rewrite; the rewrite still helps vague questions ("what
        principle was established?") that only make sense once the case or
        topic is filled in — reranking on the original alone refused those."""
        if rewritten == query:
            return await self.reranker.rerank(query, documents, top_k=top_k)
        by_query, by_rewrite = await asyncio.gather(
            self.reranker.rerank(query, documents),
            self.reranker.rerank(rewritten, documents),
        )
        best: dict[int, float] = {}
        for idx, score in [*by_query, *by_rewrite]:
            best[idx] = max(score, best.get(idx, score))
        return sorted(best.items(), key=lambda s: s[1], reverse=True)[:top_k]

    @staticmethod
    def _cache_key(query: str, top_k: int, filters: dict | None) -> str:
        payload = json.dumps(
            {"q": query, "k": top_k, "f": filters or {}}, sort_keys=True
        )
        return f"rag:{hashlib.md5(payload.encode()).hexdigest()}"

    async def run(
        self,
        query: str,
        conversation_history: list[Any] | None = None,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
        case_name: str | None = None,
    ) -> RAGResult:
        start = time.perf_counter()
        top_k = top_k or settings.TOP_K_RERANKED

        # Check answer cache (conversation_history excluded — answers are query-specific)
        cache_key = self._cache_key(query, top_k, filters)
        cached = await cache.get(cache_key)
        if cached:
            logger.debug(f"RAG cache hit: {cache_key}")
            return RAGResult(
                answer=cached["answer"],
                citations=[Citation(**c) for c in cached["citations"]],
                rewritten_query=cached.get("rewritten_query"),
                context_used=cached.get("context_used", True),
                sufficient_context=cached.get("sufficient_context", True),
                latency_ms=cached.get("latency_ms", 0),
            )

        # Step 1: Rewrite query
        rewritten = await rewrite_query(query, case_name=case_name)
        logger.debug(f"Query rewritten: '{query}' → '{rewritten}'")

        # Step 2: Retrieve from vector DB (original question + rewrite)
        documents, metadatas = await self._retrieve_candidates(query, rewritten, filters)

        if not documents:
            return RAGResult(
                answer=(
                    "The uploaded legal corpus does not contain sufficient "
                    "evidence to answer this question."
                ),
                citations=[],
                rewritten_query=rewritten,
                context_used=False,
                sufficient_context=False,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )

        # Step 3: Hybrid fusion (BM25 + dense via RRF) then rerank
        dense_order = list(range(len(documents)))  # ChromaDB already sorted by distance
        fused_order = self._fuse_results(rewritten, documents, dense_order)
        fused_docs = [documents[i] for i in fused_order]
        fused_meta = [metadatas[i] if i < len(metadatas) else {} for i in fused_order]

        # Rerank against both the user's question and the rewrite.
        reranked = await self._rerank(query, rewritten, fused_docs, top_k)

        # Step 4: Build context and citations (index into fused arrays)
        context_parts = []
        pre_citations = []
        for rank, (orig_idx, score) in enumerate(reranked):
            doc = fused_docs[orig_idx]
            meta = fused_meta[orig_idx] if orig_idx < len(fused_meta) else {}

            context_parts.append(
                f"[Document {rank + 1}]\n"
                f"Case: {meta.get('case_name', 'Unknown')}\n"
                f"Court: {meta.get('court', 'N/A')} | Date: {meta.get('date', 'N/A')}\n"
                f"Content: {doc}\n"
            )
            pre_citations.append(
                {
                    "rank": rank + 1,
                    "case_id": meta.get("case_id", ""),
                    "case_name": meta.get("case_name", "Unknown"),
                    "chunk_id": f"{meta.get('case_id', '')}__chunk_{meta.get('chunk_index', 0)}",
                    "content": doc[:500],
                    "similarity_score": round(score, 4),
                    "court": meta.get("court"),
                    "date": meta.get("date"),
                }
            )

        context = "\n\n---\n\n".join(context_parts)
        history_text = self._format_history(conversation_history or [])

        # Step 5: Check context quality
        max_score = max(score for _, score in reranked) if reranked else 0
        if max_score < settings.SIMILARITY_THRESHOLD:
            return RAGResult(
                answer=(
                    "The uploaded legal corpus does not contain sufficient "
                    "evidence to answer this question."
                ),
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
        answer = self._strip_invalid_citations(answer, len(reranked))

        citations = [Citation(**c) for c in pre_citations]
        latency_ms = int((time.perf_counter() - start) * 1000)

        result = RAGResult(
            answer=answer,
            citations=citations,
            rewritten_query=rewritten,
            context_used=True,
            sufficient_context=True,
            latency_ms=latency_ms,
        )

        # Cache the result for identical (query, top_k, filters)
        await cache.set(
            cache_key,
            {
                "answer": answer,
                "citations": [c.model_dump() for c in citations],
                "rewritten_query": rewritten,
                "context_used": True,
                "sufficient_context": True,
                "latency_ms": latency_ms,
            },
            ttl=_RAG_CACHE_TTL,
        )

        return result

    async def stream(
        self,
        query: str,
        conversation_history: list[Any] | None = None,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
        case_name: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        _INSUFFICIENT = (
            "The uploaded legal corpus does not contain sufficient "
            "evidence to answer this question."
        )
        top_k = top_k or settings.TOP_K_RERANKED

        # Each status is emitted at the moment that stage actually starts, so
        # the UI's research-progress steps mirror the real pipeline.
        yield StreamChunk(type="status", content="understanding")
        rewritten = await rewrite_query(query, case_name=case_name)
        yield StreamChunk(type="status", content="retrieving")
        documents, metadatas = await self._retrieve_candidates(query, rewritten, filters)

        if not documents:
            yield StreamChunk(type="text", content=_INSUFFICIENT)
            return

        # Hybrid fusion then rerank
        yield StreamChunk(type="status", content="reranking")
        dense_order = list(range(len(documents)))
        fused_order = self._fuse_results(rewritten, documents, dense_order)
        fused_docs = [documents[i] for i in fused_order]
        fused_meta = [metadatas[i] if i < len(metadatas) else {} for i in fused_order]

        reranked = await self._rerank(query, rewritten, fused_docs, top_k)

        # Gate: check reranker score before generating or yielding citations
        max_score = max(score for _, score in reranked) if reranked else 0
        if max_score < settings.SIMILARITY_THRESHOLD:
            yield StreamChunk(type="text", content=_INSUFFICIENT)
            return

        context_parts = []
        citations_data = []
        for rank, (orig_idx, score) in enumerate(reranked):
            doc = fused_docs[orig_idx]
            meta = fused_meta[orig_idx] if orig_idx < len(fused_meta) else {}
            context_parts.append(
                f"[Document {rank + 1}]\n"
                f"Case: {meta.get('case_name', 'Unknown')}\n"
                f"Court: {meta.get('court', 'N/A')} | Date: {meta.get('date', 'N/A')}\n"
                f"Content: {doc}\n"
            )
            citations_data.append(
                Citation(
                    rank=rank + 1,
                    case_id=meta.get("case_id", ""),
                    case_name=meta.get("case_name", "Unknown"),
                    chunk_id=f"{meta.get('case_id', '')}__chunk_{meta.get('chunk_index', 0)}",
                    content=doc[:500],
                    similarity_score=round(score, 4),
                    court=meta.get("court"),
                    date=meta.get("date"),
                )
            )

        # Yield citations only after the threshold gate passes
        yield StreamChunk(type="citation", citations=citations_data)
        yield StreamChunk(type="status", content="generating")

        context = "\n\n---\n\n".join(context_parts)
        history_text = self._format_history(conversation_history or [])
        user_prompt = LEGAL_QA_USER.format(
            context=context,
            history=history_text,
            question=query,
        )

        async for text_chunk in stream_text(user_prompt, system_prompt=LEGAL_QA_SYSTEM):
            yield StreamChunk(type="text", content=text_chunk)

    async def _case_evidence(
        self, question: str, case_id: str, case_name: str, top_k: int
    ) -> list[tuple[str, dict[str, Any], float]]:
        """The normal retrieval path scoped to one judgment: query rewrite ->
        LegalBERT dense retrieval (case-filtered, question + rewrite) -> BM25
        + RRF fusion -> cross-encoder rerank (better of question/rewrite).
        Returns (passage, metadata, rerank score)."""
        rewritten = await rewrite_query(question, case_name=case_name)
        documents, metadatas = await self._retrieve_candidates(
            question, rewritten, {"case_id": case_id}
        )
        if not documents:
            return []
        fused_order = self._fuse_results(rewritten, documents, list(range(len(documents))))
        fused_docs = [documents[i] for i in fused_order]
        fused_meta = [metadatas[i] if i < len(metadatas) else {} for i in fused_order]
        reranked = await self._rerank(question, rewritten, fused_docs, top_k)
        return [(fused_docs[i], fused_meta[i], score) for i, score in reranked]

    async def compare(
        self,
        case_a: dict[str, str],
        case_b: dict[str, str],
        question: str,
        top_k_per_case: int = 3,
    ) -> RAGResult:
        """Grounded comparison of two indexed judgments. Evidence is
        retrieved separately from each case, and each case must pass the same
        SIMILARITY_THRESHOLD evidence gate as normal research — if either
        side lacks evidence, no comparison is generated."""
        start = time.perf_counter()
        evidence = []
        for case in (case_a, case_b):
            passages = await self._case_evidence(
                question, case["case_id"], case["case_name"], top_k_per_case
            )
            best = max((score for _, _, score in passages), default=0.0)
            if best < settings.SIMILARITY_THRESHOLD:
                logger.info(
                    f"Compare: insufficient evidence in case_id={case['case_id']} "
                    f"(best rerank score {best:.3f})"
                )
                return RAGResult(
                    answer=COMPARE_INSUFFICIENT,
                    citations=[],
                    sufficient_context=False,
                    context_used=False,
                    latency_ms=int((time.perf_counter() - start) * 1000),
                )
            evidence.append((case, passages))

        context_parts: list[str] = []
        citations: list[Citation] = []
        for label, (case, passages) in zip(("Case A", "Case B"), evidence):
            for doc, meta, score in passages:
                n = len(citations) + 1
                context_parts.append(
                    f"[Document {n}] ({label}: {case['case_name']})\n{doc}\n"
                )
                citations.append(
                    Citation(
                        rank=n,
                        case_id=case["case_id"],
                        case_name=case["case_name"],
                        chunk_id=f"{case['case_id']}__chunk_{meta.get('chunk_index', 0)}",
                        content=doc[:500],
                        similarity_score=round(score, 4),
                        court=meta.get("court"),
                        date=meta.get("date"),
                    )
                )

        answer = await generate_text(
            CASE_COMPARE_USER.format(
                case_a=case_a["case_name"],
                case_b=case_b["case_name"],
                context="\n---\n".join(context_parts),
                question=question,
            ),
            system_prompt=CASE_COMPARE_SYSTEM,
        )
        answer = self._strip_invalid_citations(answer.strip(), len(citations))
        # Only a response that IS the refusal counts as one. The model may
        # also use the sentence inside a single section (e.g. "How they
        # relate") while still comparing both cases with citations — that
        # partial answer must not be thrown away.
        bare = answer.strip().strip('"').strip().lower()
        sufficient = not bare.startswith(COMPARE_INSUFFICIENT.lower()[:60]) or len(bare) > len(
            COMPARE_INSUFFICIENT
        ) + 40
        if not sufficient:
            logger.info("Compare: model reported insufficient evidence in the retrieved passages")
        return RAGResult(
            answer=answer if sufficient else COMPARE_INSUFFICIENT,
            citations=citations if sufficient else [],
            sufficient_context=sufficient,
            context_used=sufficient,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    def _build_chroma_filters(self, filters: dict[str, Any] | None) -> dict | None:
        if not filters:
            return None
        where: dict[str, Any] = {}
        if filters.get("court"):
            where["court"] = {"$eq": filters["court"]}
        if filters.get("case_id"):
            where["case_id"] = {"$eq": filters["case_id"]}
        return where if where else None

    @staticmethod
    def _retrieval_n_results(filters: dict[str, Any] | None) -> int:
        """A case_id filter already narrows Chroma's search to one
        judgment's own chunks, so retrieving a wider pre-rerank candidate
        pool there is cheap and lets the cross-encoder see more of that
        judgment's real content instead of an arbitrary top-12 cutoff."""
        if filters and filters.get("case_id"):
            return settings.TOP_K_RETRIEVAL_SCOPED
        return settings.TOP_K_RETRIEVAL

    @staticmethod
    def _strip_invalid_citations(answer: str, num_docs: int) -> str:
        """Remove [N] inline citations where N is outside [1, num_docs].

        Only brackets containing short (<=2 digit) numbers are treated as
        citation markers — real legal citations like "[1994] 3 SCR 1" use
        4-digit years in brackets and must be left untouched, not deleted
        as an "invalid" citation index.
        """

        def _replace(m: re.Match) -> str:
            nums = [n.strip() for n in m.group(1).split(",")]
            if any(n.isdigit() and len(n) > 2 for n in nums):
                return m.group(0)
            valid = [n for n in nums if n.isdigit() and 1 <= int(n) <= num_docs]
            return f"[{','.join(valid)}]" if valid else ""

        return re.sub(r"\[([0-9,\s]+)\]", _replace, answer)

    def _format_history(self, history: list[Any]) -> str:
        if not history:
            return "No prior conversation."
        lines = []
        for msg in history[-6:]:  # Last 3 turns
            role = getattr(msg, "role", "unknown")
            content = getattr(msg, "content", "")[:200]
            lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines)
