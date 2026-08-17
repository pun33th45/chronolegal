"""Integration tests for the CHROMA_MODE=embedded demo-data bootstrap
(app.main._ensure_demo_data_ready) against a real PostgreSQL database (see
tests/conftest.py's db/db_engine fixtures). EmbeddingService's actual
Chroma/embedding calls are mocked — this exercises the seed/reconciliation
SQL logic, not the embedding pipeline itself, which has no local coverage
without a running Chroma server or network access.

Uses a session factory bound to the per-test db_engine fixture (not the
app's global AsyncSessionLocal/engine): that global engine is a
process-wide singleton bound to whichever event loop first used it, which
breaks under pytest-asyncio's one-event-loop-per-test-function default —
the same reason conftest.py's own db/client fixtures build a fresh engine
per test instead of reusing the app's.
"""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import _ensure_demo_data_ready
from app.models.case import LegalCase
from app.services.ai.embedding_service import EmbeddingService


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )


async def _collection_count(value):
    async def _inner(self):
        return value

    return _inner


@pytest.mark.asyncio
async def test_seeds_sample_cases_when_table_is_empty(session_factory, monkeypatch):
    monkeypatch.setattr(
        EmbeddingService, "get_collection_count", await _collection_count(1)
    )

    await _ensure_demo_data_ready(session_factory=session_factory)

    async with session_factory() as verify_db:
        count = (
            await verify_db.execute(text("SELECT COUNT(*) FROM legal_cases"))
        ).scalar_one()
    assert count > 0


@pytest.mark.asyncio
async def test_does_not_reseed_when_cases_already_exist(
    db, session_factory, monkeypatch
):
    db.add(LegalCase(case_id="existing-case", case_name="Existing Case", full_text="x"))
    await db.commit()

    monkeypatch.setattr(
        EmbeddingService, "get_collection_count", await _collection_count(1)
    )

    await _ensure_demo_data_ready(session_factory=session_factory)

    async with session_factory() as verify_db:
        count = (
            await verify_db.execute(text("SELECT COUNT(*) FROM legal_cases"))
        ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_reembeds_all_cases_when_vector_collection_is_empty(
    db, session_factory, monkeypatch
):
    db.add(
        LegalCase(
            case_id="demo-1",
            case_name="Demo Case",
            full_text="some judgment text",
            is_embedded=True,
            chunk_count=5,
        )
    )
    await db.commit()

    embedded_case_ids = []

    async def _fake_embed_case(self, case):
        embedded_case_ids.append(case.case_id)
        return 3

    monkeypatch.setattr(
        EmbeddingService, "get_collection_count", await _collection_count(0)
    )
    monkeypatch.setattr(EmbeddingService, "_embed_case", _fake_embed_case)

    await _ensure_demo_data_ready(session_factory=session_factory)

    assert embedded_case_ids == ["demo-1"]
    async with session_factory() as verify_db:
        row = (
            await verify_db.execute(
                text(
                    "SELECT is_embedded, chunk_count FROM legal_cases WHERE case_id = 'demo-1'"
                )
            )
        ).one()
    assert row.is_embedded is True
    assert row.chunk_count == 3


@pytest.mark.asyncio
async def test_skips_reembedding_when_vector_collection_is_populated(
    db, session_factory, monkeypatch
):
    db.add(
        LegalCase(
            case_id="demo-2",
            case_name="Demo Case 2",
            full_text="some judgment text",
            is_embedded=True,
            chunk_count=5,
        )
    )
    await db.commit()

    embed_calls = []

    async def _fake_embed_case(self, case):
        embed_calls.append(case.case_id)
        return 1

    monkeypatch.setattr(
        EmbeddingService, "get_collection_count", await _collection_count(42)
    )
    monkeypatch.setattr(EmbeddingService, "_embed_case", _fake_embed_case)

    await _ensure_demo_data_ready(session_factory=session_factory)

    assert embed_calls == []
    async with session_factory() as verify_db:
        row = (
            await verify_db.execute(
                text(
                    "SELECT is_embedded, chunk_count FROM legal_cases WHERE case_id = 'demo-2'"
                )
            )
        ).one()
    assert row.is_embedded is True
    assert row.chunk_count == 5
