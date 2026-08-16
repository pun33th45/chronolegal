"""
Cross-encoder reranker — scores query-document pairs for precise ranking.
"""

import asyncio
from functools import lru_cache

import torch
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

        # sentence-transformers' documented CrossEncoder.predict usage is
        # exactly list[list[str]] pairs; the stub's Union is too narrow due
        # to List's invariance (mypy itself suggests Sequence instead).
        #
        # activation_fn=torch.sigmoid maps this model's raw, unbounded
        # logits onto [0, 1] so the score is comparable to
        # settings.SIMILARITY_THRESHOLD (designed for a 0-1 similarity
        # scale elsewhere in the pipeline) — without it, a threshold of
        # 0.6 against raw logits (roughly -11..+11 for this model) has no
        # calibrated meaning and silently misclassifies relevant results
        # as "insufficient context". Sigmoid is monotonic, so ranking
        # order (top_k selection below) is unaffected.
        def _predict():
            return self.model.predict(  # type: ignore[arg-type]
                pairs,
                batch_size=16,
                show_progress_bar=False,
                activation_fn=torch.sigmoid,
            )

        scores = await loop.run_in_executor(None, _predict)

        indexed = sorted(enumerate(scores.tolist()), key=lambda x: x[1], reverse=True)
        if top_k:
            indexed = indexed[:top_k]
        return indexed
