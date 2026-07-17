#!/usr/bin/env python3
"""
Seed the database with sample landmark cases for development.

Usage:
    python scripts/setup/seed_db.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))


async def seed() -> None:
    from sqlalchemy import text
    from app.core.database import AsyncSessionLocal, create_all_tables

    await create_all_tables()

    seed_file = Path(__file__).resolve().parents[2] / "database" / "seeds" / "01_sample_cases.sql"
    if not seed_file.exists():
        print(f"Seed file not found: {seed_file}")
        return

    sql = seed_file.read_text(encoding="utf-8")

    async with AsyncSessionLocal() as db:
        # Check if already seeded
        result = await db.execute(text("SELECT COUNT(*) FROM legal_cases"))
        count = result.scalar_one()
        if count > 0:
            print(f"Database already has {count} cases. Skipping seed.")
            return

        await db.execute(text(sql))
        await db.commit()

    result_after = None
    async with AsyncSessionLocal() as db:
        result_after = await db.execute(text("SELECT COUNT(*) FROM legal_cases"))
        final_count = result_after.scalar_one()

    print(f"Seeded {final_count} landmark cases.")


if __name__ == "__main__":
    asyncio.run(seed())
