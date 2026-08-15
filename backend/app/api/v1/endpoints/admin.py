from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_admin
from app.core.database import get_db
from app.schemas.analytics import AdminStats
from app.services.legal.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    current_admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(db)
    return await svc.get_admin_stats()


@router.get("/search-logs")
async def get_search_logs(
    page: int = 1,
    page_size: int = 50,
    current_admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.legal.search_log_service import SearchLogService

    svc = SearchLogService(db)
    return await svc.get_all(page=page, page_size=page_size)


@router.post("/reindex")
async def trigger_reindex(
    current_admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.ai.embedding_service import EmbeddingService

    svc = EmbeddingService()
    task_id = await svc.trigger_full_reindex()
    return {"task_id": task_id, "message": "Reindexing started in background"}


@router.get("/users")
async def list_users(
    page: int = 1,
    page_size: int = 50,
    current_admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.legal.user_service import UserService

    svc = UserService(db)
    return await svc.list_all(page=page, page_size=page_size)
