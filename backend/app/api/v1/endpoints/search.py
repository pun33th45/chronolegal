import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.schemas.search import SearchRequest, SearchResponse
from app.services.ai.search_service import SearchService
from app.services.legal.search_log_service import SearchLogService

router = APIRouter()


@router.post("/", response_model=SearchResponse)
async def semantic_search(
    payload: SearchRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start = time.perf_counter()
    svc = SearchService()
    results = await svc.search(
        query=payload.query,
        filters=payload.filters,
        top_k=payload.top_k,
        search_type=payload.search_type,
    )
    latency_ms = int((time.perf_counter() - start) * 1000)

    # Log the search
    log_svc = SearchLogService(db)
    await log_svc.log(
        user_id=current_user.id,
        query=payload.query,
        rewritten_query=results.rewritten_query,
        result_count=results.total_results,
        top_score=results.results[0].similarity_score if results.results else None,
        latency_ms=latency_ms,
        search_type=payload.search_type,
    )

    results.latency_ms = latency_ms
    return results


@router.get("/suggestions")
async def search_suggestions(
    q: str = Query(min_length=2),
    limit: int = Query(default=5, le=10),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = SearchService()
    return await svc.get_suggestions(q, limit=limit)


@router.get("/filters")
async def get_available_filters(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.legal.case_service import CaseService

    svc = CaseService(db)
    return {
        "courts": await svc.get_distinct_courts(),
        "judges": await svc.get_distinct_judges(),
        "acts": await svc.get_distinct_acts(),
        "decision_types": await svc.get_distinct_decision_types(),
    }
