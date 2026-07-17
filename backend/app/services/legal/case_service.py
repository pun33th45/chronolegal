import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import CaseChunk, LegalCase


class CaseService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_case_id(self, case_id: str) -> LegalCase | None:
        result = await self.db.execute(
            select(LegalCase).where(LegalCase.case_id == case_id)
        )
        return result.scalar_one_or_none()

    async def get_by_db_id(self, db_id: uuid.UUID) -> LegalCase | None:
        result = await self.db.execute(
            select(LegalCase).where(LegalCase.id == db_id)
        )
        return result.scalar_one_or_none()

    async def list_cases(
        self,
        page: int = 1,
        page_size: int = 20,
        court: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        act: str | None = None,
    ) -> list[LegalCase]:
        query = select(LegalCase)
        if court:
            query = query.where(LegalCase.court == court)
        if date_from:
            query = query.where(LegalCase.judgment_date >= date_from)
        if date_to:
            query = query.where(LegalCase.judgment_date <= date_to)
        if act:
            query = query.where(LegalCase.acts.any(act))

        offset = (page - 1) * page_size
        query = query.order_by(LegalCase.judgment_date.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_chunks(self, case_db_id: uuid.UUID) -> list[CaseChunk]:
        result = await self.db.execute(
            select(CaseChunk)
            .where(CaseChunk.case_id == case_db_id)
            .order_by(CaseChunk.chunk_index)
        )
        return list(result.scalars().all())

    async def get_unembedded(self, limit: int = 1000) -> list[LegalCase]:
        result = await self.db.execute(
            select(LegalCase)
            .where(LegalCase.is_embedded == False)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_distinct_courts(self) -> list[str]:
        result = await self.db.execute(
            select(LegalCase.court)
            .where(LegalCase.court.isnot(None))
            .distinct()
            .order_by(LegalCase.court)
        )
        return [r[0] for r in result.all() if r[0]]

    async def get_distinct_judges(self) -> list[str]:
        result = await self.db.execute(
            select(func.unnest(LegalCase.judges).label("judge"))
            .where(LegalCase.judges.isnot(None))
            .distinct()
            .order_by("judge")
            .limit(500)
        )
        return [r[0] for r in result.all() if r[0]]

    async def get_distinct_acts(self) -> list[str]:
        result = await self.db.execute(
            select(func.unnest(LegalCase.acts).label("act"))
            .where(LegalCase.acts.isnot(None))
            .distinct()
            .order_by("act")
            .limit(500)
        )
        return [r[0] for r in result.all() if r[0]]

    async def get_distinct_decision_types(self) -> list[str]:
        result = await self.db.execute(
            select(LegalCase.decision_type)
            .where(LegalCase.decision_type.isnot(None))
            .distinct()
            .order_by(LegalCase.decision_type)
        )
        return [r[0] for r in result.all() if r[0]]

    async def total_count(self) -> int:
        result = await self.db.execute(select(func.count(LegalCase.id)))
        return result.scalar_one() or 0
