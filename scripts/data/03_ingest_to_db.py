#!/usr/bin/env python3
"""
Ingest preprocessed JSONL cases into PostgreSQL.

Usage:
    python scripts/data/03_ingest_to_db.py \
        --input /data/processed/cases.jsonl \
        --batch-size 100
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))


async def ingest(input_path: str, batch_size: int) -> None:
    from app.core.database import AsyncSessionLocal, create_all_tables
    from app.models.case import LegalCase
    from sqlalchemy import select

    await create_all_tables()

    inp = Path(input_path)
    if not inp.exists():
        print(f"File not found: {inp}")
        sys.exit(1)

    with open(inp, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    print(f"Loading {len(lines)} cases into PostgreSQL...")

    async with AsyncSessionLocal() as db:
        batch = []
        inserted = 0
        skipped = 0

        for i, data in enumerate(lines, 1):
            # Check if already exists
            result = await db.execute(
                select(LegalCase).where(LegalCase.case_id == data["case_id"])
            )
            if result.scalar_one_or_none():
                skipped += 1
                continue

            full_text = data.get("full_text", "")
            case = LegalCase(
                case_id=data["case_id"],
                case_name=data.get("case_name", ""),
                case_number=data.get("case_number"),
                petitioner=data.get("petitioner"),
                respondent=data.get("respondent"),
                court=data.get("court"),
                bench=data.get("bench"),
                judges=data.get("judges") or None,
                judgment_date=data.get("judgment_date"),
                acts=data.get("acts") or None,
                sections=data.get("sections") or None,
                keywords=data.get("keywords") or None,
                full_text=full_text,
                summary=data.get("summary"),
                headnotes=data.get("headnotes"),
                decision_type=data.get("decision_type"),
                outcome=data.get("outcome"),
                cited_cases=data.get("cited_cases") or None,
                source_url=data.get("source_url"),
                text_length=len(full_text) if full_text else 0,
            )
            batch.append(case)
            inserted += 1

            if len(batch) >= batch_size:
                db.add_all(batch)
                await db.commit()
                batch = []
                print(f"  Inserted {inserted}/{len(lines)}...", end="\r")

        if batch:
            db.add_all(batch)
            await db.commit()

    print(f"\nDone. Inserted: {inserted}, Skipped (duplicate): {skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="/data/processed/cases.jsonl")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    asyncio.run(ingest(args.input, args.batch_size))
