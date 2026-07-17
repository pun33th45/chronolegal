from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.schemas.case import LegalEntityExtraction
from app.services.ai.ner_service import NERService
from app.services.legal.case_service import CaseService

router = APIRouter()


class NERRequest(BaseModel):
    text: str | None = None
    case_id: str | None = None


@router.post("/", response_model=LegalEntityExtraction)
async def extract_entities(
    payload: NERRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not payload.text and not payload.case_id:
        raise HTTPException(status_code=400, detail="Provide either text or case_id")

    text = payload.text
    if payload.case_id:
        svc = CaseService(db)
        case = await svc.get_by_case_id(payload.case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        text = case.full_text or case.summary or ""

    if not text:
        raise HTTPException(status_code=422, detail="No text available for NER")

    ner_svc = NERService()
    return await ner_svc.extract(text)
