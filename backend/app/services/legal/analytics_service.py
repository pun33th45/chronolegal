from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import LegalCase
from app.models.search_log import SearchLog
from app.models.user import User
from app.schemas.case import UNKNOWN_COURT
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
        """Same figures as before, fetched with far fewer sequential round
        trips: Supabase is ~300ms away per round trip from this backend, and
        this used to run ~15 queries one after another (6-10s). The scalar
        figures now come from one query, and the independent list queries
        run concurrently, each on its own pooled connection."""
        import asyncio

        from app.core.database import AsyncSessionLocal

        async def in_own_session(method, **kwargs):
            async with AsyncSessionLocal() as session:
                return await getattr(AnalyticsService(session), method)(**kwargs)

        embedder = EmbeddingService()
        (
            scalars,
            top_acts,
            top_courts,
            top_judges,
            top_keywords,
            case_trends,
            decision_types,
            total_embeddings,
        ) = await asyncio.gather(
            self._dashboard_scalars(),
            in_own_session("get_top_acts", limit=10),
            in_own_session("get_top_courts", limit=10),
            in_own_session("get_top_judges", limit=10),
            in_own_session("get_top_keywords", limit=20),
            # The corpus is historical (landmark judgments from the 1970s
            # on), so the dashboard timeline covers every recorded year.
            in_own_session("get_case_trends", years=None),
            in_own_session("get_decision_type_stats"),
            embedder.get_collection_count(),
        )

        return AnalyticsDashboard(
            total_cases=scalars.total_cases,
            total_embeddings=total_embeddings,
            total_users=scalars.total_users,
            total_searches=scalars.total_searches,
            top_acts=top_acts,
            top_courts=top_courts,
            top_judges=top_judges,
            top_keywords=top_keywords,
            case_trends=case_trends,
            decision_types=decision_types,
            cases_without_court=scalars.cases_without_court,
            cases_without_date=scalars.cases_without_date,
            avg_text_length=float(scalars.avg_text_length or 0),
            avg_search_latency_ms=float(scalars.avg_latency or 0),
            storage_used_mb=0.0,
        )

    async def _dashboard_scalars(self):
        """All single-number dashboard figures in one round trip."""
        result = await self.db.execute(
            text(
                """
                SELECT
                  (SELECT COUNT(*) FROM legal_cases) AS total_cases,
                  (SELECT COUNT(*) FROM users) AS total_users,
                  (SELECT COUNT(*) FROM search_logs) AS total_searches,
                  (SELECT COUNT(*) FROM legal_cases
                     WHERE court IS NULL OR court = :unknown_court) AS cases_without_court,
                  (SELECT COUNT(*) FROM legal_cases
                     WHERE judgment_date IS NULL) AS cases_without_date,
                  (SELECT AVG(text_length) FROM legal_cases
                     WHERE text_length IS NOT NULL) AS avg_text_length,
                  (SELECT AVG(latency_ms) FROM search_logs
                     WHERE latency_ms IS NOT NULL) AS avg_latency
                """
            ),
            {"unknown_court": UNKNOWN_COURT},
        )
        return result.one()

    async def get_top_acts(self, limit: int = 20) -> list[TopItem]:
        result = await self.db.execute(
            text(
                """
                SELECT unnest(acts) AS act, COUNT(*) AS cnt
                FROM legal_cases
                WHERE acts IS NOT NULL
                GROUP BY act
                ORDER BY cnt DESC
                LIMIT :limit
            """
            ),
            {"limit": limit},
        )
        return [TopItem(name=row.act, count=row.cnt) for row in result.all()]

    async def get_top_courts(self, limit: int = 20) -> list[CourtDistribution]:
        total = await self._count(LegalCase)
        result = await self.db.execute(
            select(LegalCase.court, func.count(LegalCase.id).label("cnt"))
            .where(LegalCase.court.isnot(None), LegalCase.court != UNKNOWN_COURT)
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
            text(
                """
                SELECT unnest(judges) AS judge, COUNT(*) AS cnt
                FROM legal_cases
                WHERE judges IS NOT NULL
                GROUP BY judge
                ORDER BY cnt DESC
                LIMIT :limit
            """
            ),
            {"limit": limit},
        )
        return [TopItem(name=row.judge, count=row.cnt) for row in result.all()]

    async def get_top_keywords(self, limit: int = 20) -> list[TopItem]:
        result = await self.db.execute(
            text(
                """
                SELECT unnest(keywords) AS kw, COUNT(*) AS cnt
                FROM legal_cases
                WHERE keywords IS NOT NULL
                GROUP BY kw
                ORDER BY cnt DESC
                LIMIT :limit
            """
            ),
            {"limit": limit},
        )
        return [TopItem(name=row.kw, count=row.cnt) for row in result.all()]

    async def get_case_trends(self, years: int | None = 20) -> list[CaseTrend]:
        """Judgments per year; `years=None` covers all recorded years."""
        result = await self.db.execute(
            text(
                """
                SELECT EXTRACT(YEAR FROM judgment_date)::int AS year, COUNT(*) AS cnt
                FROM legal_cases
                WHERE judgment_date IS NOT NULL
                  AND (CAST(:years AS int) IS NULL
                       OR EXTRACT(YEAR FROM judgment_date) >= EXTRACT(YEAR FROM NOW()) - :years)
                GROUP BY year
                ORDER BY year
            """
            ),
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
            select(func.count(LegalCase.id)).where(
                LegalCase.is_embedded
                == True  # noqa: E712 -- SQLAlchemy column, not a bool
            )
        )
        embedded = embedded_result.scalar_one() or 0

        from app.models.case import CaseChunk

        total_chunks = await self._count(CaseChunk)
        total_users = await self._count(User)
        total_searches = await self._count(SearchLog)

        embedder = EmbeddingService()
        chroma_count = await embedder.get_collection_count()

        avg_latency_result = await self.db.execute(
            select(func.avg(SearchLog.latency_ms)).where(
                SearchLog.latency_ms.isnot(None)
            )
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

    async def _count_where(self, condition) -> int:
        result = await self.db.execute(select(func.count(LegalCase.id)).where(condition))
        return result.scalar_one() or 0
