"""
Hybrid search: semantic (ChromaDB) + keyword (BM25) with fusion.
"""

import time

from app.core.redis import cache
from app.schemas.search import SearchFilters, SearchResponse, SearchResult
from app.services.ai.embedding_service import EmbeddingService
from app.services.ai.query_rewriter import rewrite_query
from app.services.ai.reranker import Reranker


class SearchService:
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

    async def search(
        self,
        query: str,
        filters: SearchFilters | None = None,
        top_k: int = 10,
        search_type: str = "hybrid",
    ) -> SearchResponse:
        start = time.perf_counter()

        rewritten = await rewrite_query(query)
        chroma_where = self._filters_to_chroma(filters)

        raw = await self.embedder.similarity_search(
            query=rewritten,
            n_results=min(top_k * 3, 50),
            where=chroma_where,
        )

        documents = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]

        if not documents:
            return SearchResponse(
                query=query,
                rewritten_query=rewritten,
                results=[],
                total_results=0,
                search_type=search_type,
                latency_ms=int((time.perf_counter() - start) * 1000),
                filters_applied=filters,
            )

        reranked = await self.reranker.rerank(rewritten, documents, top_k=top_k)

        results = []
        for rank, (orig_idx, rerank_score) in enumerate(reranked):
            meta = metadatas[orig_idx] if orig_idx < len(metadatas) else {}
            semantic_score = 1 - (
                distances[orig_idx] if orig_idx < len(distances) else 0
            )

            results.append(
                SearchResult(
                    case_id=meta.get("case_id", ""),
                    case_name=meta.get("case_name", "Unknown"),
                    court=meta.get("court"),
                    judges=None,
                    judgment_date=meta.get("date"),
                    acts=None,
                    chunk_content=documents[orig_idx],
                    similarity_score=round(semantic_score, 4),
                    rank=rank + 1,
                    chunk_id=f"{meta.get('case_id', '')}__chunk_{meta.get('chunk_index', 0)}",
                )
            )

        return SearchResponse(
            query=query,
            rewritten_query=rewritten,
            results=results,
            total_results=len(results),
            search_type=search_type,
            latency_ms=int((time.perf_counter() - start) * 1000),
            filters_applied=filters,
        )

    async def get_suggestions(self, prefix: str, limit: int = 5) -> list[str]:
        cache_key = f"suggest:{prefix.lower()}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        raw = await self.embedder.similarity_search(query=prefix, n_results=limit * 2)
        metas = raw.get("metadatas", [[]])[0]
        seen = set()
        suggestions = []
        for meta in metas:
            name = meta.get("case_name", "")
            if name and name not in seen:
                seen.add(name)
                suggestions.append(name)
            if len(suggestions) >= limit:
                break

        await cache.set(cache_key, suggestions, ttl=300)
        return suggestions

    async def find_similar_cases(
        self, case_id: str, case_name: str, top_k: int = 5
    ) -> list[dict]:
        raw = await self.embedder.similarity_search(
            query=case_name, n_results=top_k + 5
        )
        metas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]

        seen_cases: set[str] = set()
        results = []
        for meta, dist in zip(metas, distances):
            cid = meta.get("case_id", "")
            if cid == case_id or cid in seen_cases:
                continue
            seen_cases.add(cid)
            results.append(
                {
                    "case_id": cid,
                    "case_name": meta.get("case_name", "Unknown"),
                    "court": meta.get("court"),
                    "similarity_score": round(1 - dist, 4),
                }
            )
            if len(results) >= top_k:
                break

        return results

    def _filters_to_chroma(self, filters: SearchFilters | None) -> dict | None:
        if not filters:
            return None
        conditions = []
        if filters.court:
            conditions.append({"court": {"$eq": filters.court}})
        if not conditions:
            return None
        return {"$and": conditions} if len(conditions) > 1 else conditions[0]
