"""
Cross-encoder reranker — scores query-document pairs for precise ranking.
"""

import asyncio
from functools import lru_cache

from loguru import logger
from sentence_transformers import CrossEncoder

from app.core.config import settings


@lru_cache(maxsize=1)
def _get_cross_encoder() -> CrossEncoder:
    logger.info(f"Loading reranker: {settings.RERANKER_MODEL}")
    return CrossEncoder(settings.RERANKER_MODEL, max_length=512)


class Reranker:
    def __init__(self) -> None:
        self._model: CrossEncoder | None = None

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            self._model = _get_cross_encoder()
        return self._model

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        """Returns (original_index, score) sorted by score descending."""
        if not documents:
            return []

        pairs = [[query, doc] for doc in documents]

        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            None,
            lambda: self.model.predict(pairs, batch_size=16, show_progress_bar=False),
        )

        indexed = sorted(enumerate(scores.tolist()), key=lambda x: x[1], reverse=True)
        if top_k:
            indexed = indexed[:top_k]
        return indexed
