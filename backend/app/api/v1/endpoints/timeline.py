from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.schemas.case import TimelineEvent
from app.services.ai.timeline_service import TimelineService
from app.services.legal.case_service import CaseService

router = APIRouter()


@router.get("/{case_id}", response_model=list[TimelineEvent])
async def get_case_timeline(
    case_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseService(db)
    case = await svc.get_by_case_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    timeline_svc = TimelineService()
    return await timeline_svc.generate(case)
