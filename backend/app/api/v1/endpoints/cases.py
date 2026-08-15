import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.schemas.case import LegalCaseRead, LegalCaseSummary, CaseChunkRead
from app.services.legal.case_service import CaseService

router = APIRouter()


@router.get("/", response_model=list[LegalCaseSummary])
async def list_cases(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    court: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    act: str | None = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseService(db)
    return await svc.list_cases(
        page=page,
        page_size=page_size,
        court=court,
        date_from=date_from,
        date_to=date_to,
        act=act,
    )


@router.get("/{case_id}", response_model=LegalCaseRead)
async def get_case(
    case_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseService(db)
    case = await svc.get_by_case_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.get("/{case_id}/chunks", response_model=list[CaseChunkRead])
async def get_case_chunks(
    case_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseService(db)
    case = await svc.get_by_case_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return await svc.get_chunks(case.id)


@router.get("/{case_id}/similar", response_model=list[LegalCaseSummary])
async def get_similar_cases(
    case_id: str,
    top_k: int = Query(default=5, ge=1, le=20),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.ai.search_service import SearchService

    svc = CaseService(db)
    case = await svc.get_by_case_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    search_svc = SearchService()
    return await search_svc.find_similar_cases(
        case_id=case_id, case_name=case.case_name, top_k=top_k
    )
