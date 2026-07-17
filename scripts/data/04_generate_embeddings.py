#!/usr/bin/env python3
"""
Chunk all cases and generate embeddings into ChromaDB.

Usage:
    python scripts/data/04_generate_embeddings.py \
        --batch-size 64 \
        --limit 0
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))


async def embed_all(batch_size: int, limit: int) -> None:
    from app.core.database import AsyncSessionLocal, create_all_tables
    from app.models.case import CaseChunk, LegalCase
    from app.services.ai.chunker import TextChunker
    from app.services.ai.embedding_service import EmbeddingService
    from sqlalchemy import select, update

    await create_all_tables()

    embedder = EmbeddingService()
    chunker = TextChunker()

    async with AsyncSessionLocal() as db:
        query = select(LegalCase).where(LegalCase.is_embedded == False)
        if limit:
            query = query.limit(limit)
        result = await db.execute(query)
        cases = list(result.scalars().all())

    print(f"Embedding {len(cases)} cases...")

    for i, case in enumerate(cases, 1):
        text = case.full_text or ""
        if not text.strip():
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(LegalCase)
                    .where(LegalCase.id == case.id)
                    .values(is_embedded=True, chunk_count=0)
                )
                await db.commit()
            continue

        chunks_with_meta = chunker.chunk_with_metadata(
            text,
            base_metadata={
                "case_id": case.case_id,
                "case_name": case.case_name,
                "court": case.court or "",
                "date": str(case.judgment_date) if case.judgment_date else "",
                "judges": ",".join(case.judges or []),
                "acts": ",".join(case.acts or []),
            },
        )

        chunk_texts = [c for c, _ in chunks_with_meta]
        chunk_metas = [m for _, m in chunks_with_meta]
        chunk_ids = [f"{case.case_id}__chunk_{m['chunk_index']}" for m in chunk_metas]

        # Embed into ChromaDB
        for b in range(0, len(chunk_texts), batch_size):
            await embedder.upsert_chunks(
                chunk_texts[b:b + batch_size],
                chunk_metas[b:b + batch_size],
                chunk_ids[b:b + batch_size],
            )

        # Save chunks to PostgreSQL
        async with AsyncSessionLocal() as db:
            db_chunks = [
                CaseChunk(
                    case_id=case.id,
                    chunk_index=m["chunk_index"],
                    content=text,
                    chroma_id=cid,
                    start_char=m.get("start_char"),
                    end_char=m.get("end_char"),
                )
                for text, m, cid in zip(chunk_texts, chunk_metas, chunk_ids)
            ]
            db.add_all(db_chunks)
            await db.execute(
                update(LegalCase)
                .where(LegalCase.id == case.id)
                .values(is_embedded=True, chunk_count=len(chunk_texts))
            )
            await db.commit()

        print(f"  [{i}/{len(cases)}] {case.case_name[:60]} — {len(chunk_texts)} chunks", end="\r")

    print(f"\nEmbedding complete. {len(cases)} cases processed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    asyncio.run(embed_all(args.batch_size, args.limit))
