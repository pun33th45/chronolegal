from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.schemas.case import SummaryRequest, SummaryResponse
from app.services.ai.summary_service import SummaryService
from app.services.legal.case_service import CaseService

router = APIRouter()


@router.post("/", response_model=SummaryResponse)
async def generate_summary(
    payload: SummaryRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    case_svc = CaseService(db)
    case = await case_svc.get_by_case_id(payload.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    summary_svc = SummaryService()
    result = await summary_svc.generate(
        case=case,
        summary_type=payload.summary_type,
        max_length=payload.max_length,
    )
    return result
