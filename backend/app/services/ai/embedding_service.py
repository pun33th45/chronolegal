"""
Embedding service using BAAI/bge-large-en-v1.5.
Handles batched encoding, caching, and ChromaDB insertion.
"""

import asyncio
import hashlib
import uuid
from functools import lru_cache
from typing import Any

import chromadb
from langchain_community.embeddings import HuggingFaceEmbeddings
from loguru import logger

from app.core.config import settings
from app.core.redis import cache


@lru_cache(maxsize=1)
def _get_embedding_model() -> HuggingFaceEmbeddings:
    logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
    return HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
        model_kwargs={"device": settings.EMBEDDING_DEVICE},
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": settings.EMBEDDING_BATCH_SIZE,
        },
    )


@lru_cache(maxsize=1)
def _get_chroma_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(
        host=settings.CHROMA_HOST,
        port=settings.CHROMA_PORT,
    )


def get_collection() -> chromadb.Collection:
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


class EmbeddingService:
    def __init__(self) -> None:
        self._model: HuggingFaceEmbeddings | None = None
        self._collection: chromadb.Collection | None = None

    @property
    def model(self) -> HuggingFaceEmbeddings:
        if self._model is None:
            self._model = _get_embedding_model()
        return self._model

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            self._collection = get_collection()
        return self._collection

    async def embed_text(self, text: str) -> list[float]:
        cache_key = f"embed:{hashlib.md5(text.encode()).hexdigest()}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(None, self.model.embed_query, text)
        await cache.set(cache_key, embedding, ttl=86400)
        return embedding

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(None, self.model.embed_documents, texts)
        return embeddings

    async def upsert_chunks(
        self,
        chunks: list[str],
        metadatas: list[dict[str, Any]],
        ids: list[str],
    ) -> None:
        if not chunks:
            return

        batch_size = settings.EMBEDDINGS_BATCH_SIZE
        for i in range(0, len(chunks), batch_size):
            batch_texts = chunks[i : i + batch_size]
            batch_meta = metadatas[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]

            embeddings = await self.embed_texts(batch_texts)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.collection.upsert(
                    documents=batch_texts,
                    embeddings=embeddings,
                    metadatas=batch_meta,
                    ids=batch_ids,
                ),
            )
            logger.debug(
                f"Upserted batch {i // batch_size + 1}: {len(batch_texts)} chunks"
            )

    async def similarity_search(
        self,
        query: str,
        n_results: int = 20,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query_embedding = await self.embed_text(query)

        loop = asyncio.get_event_loop()

        def _query():
            kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where
            return self.collection.query(**kwargs)

        results = await loop.run_in_executor(None, _query)
        return results

    async def get_collection_count(self) -> int:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.collection.count)

    async def trigger_full_reindex(self) -> str:
        task_id = str(uuid.uuid4())
        asyncio.create_task(self._reindex_all(task_id))
        return task_id

    async def _reindex_all(self, task_id: str) -> None:
        logger.info(f"Full reindex started: task_id={task_id}")
        await cache.set(f"reindex:{task_id}", {"status": "running", "progress": 0})
        try:
            from app.core.database import AsyncSessionLocal
            from app.services.legal.case_service import CaseService

            async with AsyncSessionLocal() as db:
                case_svc = CaseService(db)
                cases = await case_svc.get_unembedded(limit=10000)
                total = len(cases)
                for i, case in enumerate(cases):
                    await self._embed_case(case)
                    progress = int((i + 1) / total * 100)
                    await cache.set(
                        f"reindex:{task_id}",
                        {"status": "running", "progress": progress},
                        ttl=3600,
                    )
            await cache.set(
                f"reindex:{task_id}", {"status": "done", "progress": 100}, ttl=3600
            )
            logger.info(f"Full reindex completed: task_id={task_id}")
        except Exception as e:
            logger.error(f"Reindex failed: {e}")
            await cache.set(
                f"reindex:{task_id}", {"status": "failed", "error": str(e)}, ttl=3600
            )

    async def _embed_case(self, case: Any) -> None:
        from app.services.ai.chunker import TextChunker

        chunker = TextChunker()
        chunks = chunker.chunk(case.full_text or "")
        if not chunks:
            return

        ids = [f"{case.case_id}__chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "case_id": case.case_id,
                "case_name": case.case_name,
                "court": case.court or "",
                "date": str(case.judgment_date) if case.judgment_date else "",
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]
        await self.upsert_chunks(chunks, metadatas, ids)
