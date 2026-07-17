from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.schemas.analytics import AnalyticsDashboard
from app.services.legal.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/dashboard", response_model=AnalyticsDashboard)
async def get_analytics_dashboard(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(db)
    return await svc.get_dashboard()


@router.get("/top-acts")
async def get_top_acts(
    limit: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(db)
    return await svc.get_top_acts(limit=limit)


@router.get("/top-courts")
async def get_top_courts(
    limit: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(db)
    return await svc.get_top_courts(limit=limit)


@router.get("/case-trends")
async def get_case_trends(
    years: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(db)
    return await svc.get_case_trends(years=years)


@router.get("/decision-types")
async def get_decision_type_stats(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(db)
    return await svc.get_decision_type_stats()
