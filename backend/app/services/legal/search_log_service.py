import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.search_log import SearchLog


class SearchLogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log(
        self,
        user_id: uuid.UUID | None,
        query: str,
        rewritten_query: str | None = None,
        result_count: int | None = None,
        top_score: float | None = None,
        latency_ms: int | None = None,
        search_type: str | None = None,
        filters_used: str | None = None,
    ) -> None:
        entry = SearchLog(
            user_id=user_id,
            query=query,
            rewritten_query=rewritten_query,
            result_count=result_count,
            top_score=top_score,
            latency_ms=latency_ms,
            search_type=search_type,
            filters_used=filters_used,
        )
        self.db.add(entry)
        await self.db.flush()

    async def get_all(self, page: int = 1, page_size: int = 50) -> list[SearchLog]:
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(SearchLog)
            .order_by(SearchLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all())
