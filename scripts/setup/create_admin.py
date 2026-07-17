#!/usr/bin/env python3
"""
Create the first admin user.

Usage:
    python scripts/setup/create_admin.py \
        --email admin@chronolegal.ai \
        --username admin \
        --password Admin123!
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))


async def create_admin(email: str, username: str, password: str) -> None:
    from app.core.database import AsyncSessionLocal, create_all_tables
    from app.core.security import hash_password
    from app.models.user import User
    from sqlalchemy import select

    await create_all_tables()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            print(f"User {email} already exists.")
            return

        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            is_active=True,
            is_verified=True,
            is_admin=True,
            full_name="System Admin",
        )
        db.add(user)
        await db.commit()
        print(f"Admin user created: {email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default="admin@chronolegal.ai")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="Admin123!")
    args = parser.parse_args()
    asyncio.run(create_admin(args.email, args.username, args.password))
