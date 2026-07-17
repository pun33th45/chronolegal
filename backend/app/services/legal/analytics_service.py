from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import LegalCase
from app.models.search_log import SearchLog
from app.models.user import User
from app.schemas.analytics import (
    AdminStats,
    AnalyticsDashboard,
    CaseTrend,
    CourtDistribution,
    DecisionTypeStats,
    TopItem,
)
from app.services.ai.embedding_service import EmbeddingService


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_dashboard(self) -> AnalyticsDashboard:
        total_cases = await self._count(LegalCase)
        total_users = await self._count(User)
        total_searches = await self._count(SearchLog)

        embedder = EmbeddingService()
        total_embeddings = await embedder.get_collection_count()

        top_acts = await self.get_top_acts(limit=10)
        top_courts = await self.get_top_courts(limit=10)
        top_judges = await self.get_top_judges(limit=10)
        top_keywords = await self.get_top_keywords(limit=20)
        case_trends = await self.get_case_trends(years=20)
        decision_types = await self.get_decision_type_stats()

        avg_length_result = await self.db.execute(
            select(func.avg(LegalCase.text_length)).where(LegalCase.text_length.isnot(None))
        )
        avg_text_length = float(avg_length_result.scalar_one() or 0)

        avg_latency_result = await self.db.execute(
            select(func.avg(SearchLog.latency_ms)).where(SearchLog.latency_ms.isnot(None))
        )
        avg_latency = float(avg_latency_result.scalar_one() or 0)

        return AnalyticsDashboard(
            total_cases=total_cases,
            total_embeddings=total_embeddings,
            total_users=total_users,
            total_searches=total_searches,
            top_acts=top_acts,
            top_courts=top_courts,
            top_judges=top_judges,
            top_keywords=top_keywords,
            case_trends=case_trends,
            decision_types=decision_types,
            avg_text_length=avg_text_length,
            avg_search_latency_ms=avg_latency,
            storage_used_mb=0.0,
        )

    async def get_top_acts(self, limit: int = 20) -> list[TopItem]:
        result = await self.db.execute(
            text("""
                SELECT unnest(acts) AS act, COUNT(*) AS cnt
                FROM legal_cases
                WHERE acts IS NOT NULL
                GROUP BY act
                ORDER BY cnt DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        return [TopItem(name=row.act, count=row.cnt) for row in result.all()]

    async def get_top_courts(self, limit: int = 20) -> list[CourtDistribution]:
        total = await self._count(LegalCase)
        result = await self.db.execute(
            select(LegalCase.court, func.count(LegalCase.id).label("cnt"))
            .where(LegalCase.court.isnot(None))
            .group_by(LegalCase.court)
            .order_by(func.count(LegalCase.id).desc())
            .limit(limit)
        )
        rows = result.all()
        return [
            CourtDistribution(
                court=row.court,
                count=row.cnt,
                percentage=round(row.cnt / total * 100, 2) if total else 0,
            )
            for row in rows
        ]

    async def get_top_judges(self, limit: int = 20) -> list[TopItem]:
        result = await self.db.execute(
            text("""
                SELECT unnest(judges) AS judge, COUNT(*) AS cnt
                FROM legal_cases
                WHERE judges IS NOT NULL
                GROUP BY judge
                ORDER BY cnt DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        return [TopItem(name=row.judge, count=row.cnt) for row in result.all()]

    async def get_top_keywords(self, limit: int = 20) -> list[TopItem]:
        result = await self.db.execute(
            text("""
                SELECT unnest(keywords) AS kw, COUNT(*) AS cnt
                FROM legal_cases
                WHERE keywords IS NOT NULL
                GROUP BY kw
                ORDER BY cnt DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        return [TopItem(name=row.kw, count=row.cnt) for row in result.all()]

    async def get_case_trends(self, years: int = 20) -> list[CaseTrend]:
        result = await self.db.execute(
            text("""
                SELECT EXTRACT(YEAR FROM judgment_date)::int AS year, COUNT(*) AS cnt
                FROM legal_cases
                WHERE judgment_date IS NOT NULL
                  AND EXTRACT(YEAR FROM judgment_date) >= EXTRACT(YEAR FROM NOW()) - :years
                GROUP BY year
                ORDER BY year
            """),
            {"years": years},
        )
        return [CaseTrend(year=row.year, count=row.cnt) for row in result.all()]

    async def get_decision_type_stats(self) -> list[DecisionTypeStats]:
        total = await self._count(LegalCase)
        result = await self.db.execute(
            select(LegalCase.decision_type, func.count(LegalCase.id).label("cnt"))
            .where(LegalCase.decision_type.isnot(None))
            .group_by(LegalCase.decision_type)
            .order_by(func.count(LegalCase.id).desc())
        )
        return [
            DecisionTypeStats(
                decision_type=row.decision_type,
                count=row.cnt,
                percentage=round(row.cnt / total * 100, 2) if total else 0,
            )
            for row in result.all()
        ]

    async def get_admin_stats(self) -> AdminStats:
        total_cases = await self._count(LegalCase)
        embedded_result = await self.db.execute(
            select(func.count(LegalCase.id)).where(LegalCase.is_embedded == True)
        )
        embedded = embedded_result.scalar_one() or 0

        from app.models.case import CaseChunk
        total_chunks = await self._count(CaseChunk)
        total_users = await self._count(User)
        total_searches = await self._count(SearchLog)

        embedder = EmbeddingService()
        chroma_count = await embedder.get_collection_count()

        avg_latency_result = await self.db.execute(
            select(func.avg(SearchLog.latency_ms)).where(SearchLog.latency_ms.isnot(None))
        )
        avg_latency = float(avg_latency_result.scalar_one() or 0)

        return AdminStats(
            total_cases=total_cases,
            embedded_cases=embedded,
            pending_embedding=total_cases - embedded,
            total_chunks=total_chunks,
            chroma_collection_count=chroma_count,
            total_users=total_users,
            active_users_today=0,
            total_searches_today=total_searches,
            avg_latency_ms=avg_latency,
            cache_hit_rate=0.0,
            storage_used_mb=0.0,
        )

    async def _count(self, model) -> int:
        result = await self.db.execute(select(func.count(model.id)))
        return result.scalar_one() or 0
