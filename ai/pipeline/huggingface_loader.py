"""
Loads the ChronoLegal dataset from HuggingFace and ingests it into PostgreSQL + ChromaDB.

Usage:
    python -m ai.pipeline.huggingface_loader
    python -m ai.pipeline.huggingface_loader --limit 500 --batch-size 32
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import os
from datetime import datetime
from typing import Any

from loguru import logger

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


DATASET_NAME = "ChronoLegal/ChronoLegal"
SPLIT = "train"


async def _embed_case(case_row: dict[str, Any], db_session: Any, embedder: Any) -> None:
    from app.models.case import LegalCase, CaseChunk
    from app.services.ai.chunker import TextChunker
    from app.utils.text import clean_legal_text

    case_id = str(case_row.get("id") or case_row.get("case_id") or "")[:200]
    if not case_id:
        return

    # Map dataset fields to model fields
    full_text = case_row.get("judgment") or case_row.get("text") or case_row.get("full_text") or ""
    full_text = clean_legal_text(full_text)

    existing = await db_session.execute(
        __import__("sqlalchemy", fromlist=["select"]).select(LegalCase).where(LegalCase.case_id == case_id)
    )
    if existing.scalar_one_or_none():
        logger.debug(f"Skipping existing case: {case_id}")
        return

    legal_case = LegalCase(
        case_id=case_id,
        case_name=str(case_row.get("case_name") or case_row.get("title") or case_id)[:500],
        case_number=str(case_row.get("case_number") or "")[:100] or None,
        court=str(case_row.get("court") or "")[:200] or None,
        petitioner=str(case_row.get("petitioner") or "")[:500] or None,
        respondent=str(case_row.get("respondent") or "")[:500] or None,
        judges=[str(j) for j in (case_row.get("judges") or [])][:10] or None,
        acts=[str(a) for a in (case_row.get("acts") or [])][:20] or None,
        sections=[str(s) for s in (case_row.get("sections") or [])][:30] or None,
        keywords=[str(k) for k in (case_row.get("keywords") or [])][:50] or None,
        full_text=full_text[:1_000_000] if full_text else None,
        summary=str(case_row.get("summary") or "")[:5000] or None,
        decision_type=str(case_row.get("decision_type") or "")[:100] or None,
        text_length=len(full_text) if full_text else 0,
    )

    # Parse judgment date
    raw_date = case_row.get("date") or case_row.get("judgment_date")
    if raw_date:
        try:
            from app.utils.date_parser import parse_date
            legal_case.judgment_date = parse_date(str(raw_date))
        except Exception:
            pass

    db_session.add(legal_case)
    await db_session.flush()
    await db_session.refresh(legal_case)

    # Chunk and embed
    if full_text:
        chunker = TextChunker()
        chunk_meta_pairs = chunker.chunk_with_metadata(
            full_text,
            {
                "case_id": case_id,
                "case_name": legal_case.case_name,
                "court": legal_case.court or "",
                "date": str(raw_date or ""),
            },
        )

        chunk_texts = [c for c, _ in chunk_meta_pairs]
        metadatas = [m for _, m in chunk_meta_pairs]
        ids = [f"{case_id}__chunk_{i}" for i in range(len(chunk_texts))]

        await embedder.upsert_chunks(chunk_texts, metadatas, ids)

        # Persist chunk records
        for i, (chunk_text, _) in enumerate(chunk_meta_pairs):
            db_chunk = CaseChunk(
                case_id=legal_case.id,
                chunk_index=i,
                content=chunk_text,
                chroma_id=ids[i],
                chunk_size=len(chunk_text),
            )
            db_session.add(db_chunk)

        legal_case.is_embedded = True
        legal_case.chunk_count = len(chunk_texts)

    await db_session.flush()


async def load_dataset(limit: int = 0, batch_size: int = 16) -> None:
    from datasets import load_dataset as hf_load
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.core.config import settings
    from app.services.ai.embedding_service import EmbeddingService

    logger.info(f"Loading ChronoLegal dataset from HuggingFace (limit={limit or 'all'})…")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    embedder = EmbeddingService()

    ds = hf_load(DATASET_NAME, split=SPLIT, streaming=True)
    count = 0

    async with SessionLocal() as session:
        batch: list[dict] = []
        async for row in _async_iter(ds):
            batch.append(row)
            if len(batch) >= batch_size:
                for case_row in batch:
                    try:
                        await _embed_case(case_row, session, embedder)
                    except Exception as e:
                        logger.warning(f"Case failed: {e}")
                await session.commit()
                count += len(batch)
                logger.info(f"Ingested {count} cases…")
                batch = []

            if limit and count >= limit:
                break

        # Flush remainder
        for case_row in batch:
            try:
                await _embed_case(case_row, session, embedder)
            except Exception as e:
                logger.warning(f"Case failed: {e}")
        await session.commit()
        count += len(batch)

    await engine.dispose()
    logger.success(f"Ingestion complete. Total cases ingested: {count}")


async def _async_iter(ds: Any):
    loop = asyncio.get_event_loop()
    it = iter(ds)
    while True:
        try:
            row = await loop.run_in_executor(None, next, it)
            yield row
        except StopIteration:
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load ChronoLegal dataset into the platform")
    parser.add_argument("--limit", type=int, default=0, help="Max cases to load (0=all)")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size per DB flush")
    args = parser.parse_args()

    asyncio.run(load_dataset(limit=args.limit, batch_size=args.batch_size))
