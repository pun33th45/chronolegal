from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.schemas.chat import Citation
from app.services.ai.rag_pipeline import RAGPipeline
from app.services.legal.case_service import CaseService

router = APIRouter()

_DEFAULT_QUESTION = (
    "What legal issues, constitutional principles and holdings does each "
    "judgment address, and how do the two judgments relate to or differ from "
    "each other?"
)


class CompareRequest(BaseModel):
    case_a: str = Field(min_length=1, max_length=255)
    case_b: str = Field(min_length=1, max_length=255)
    question: str | None = Field(default=None, max_length=500)


class CompareResponse(BaseModel):
    case_a: str
    case_b: str
    question: str
    answer: str
    sufficient_context: bool
    citations: list[Citation]
    latency_ms: int


@router.post("/", response_model=CompareResponse)
async def compare_cases(
    payload: CompareRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Grounded comparison of two judgments already in the knowledge base.
    Reuses the RAG pipeline (case-scoped retrieval, BM25+RRF, reranking,
    evidence threshold) — nothing is re-uploaded or re-embedded."""
    if payload.case_a == payload.case_b:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select two different judgments to compare.",
        )

    svc = CaseService(db)
    cases = []
    for case_id in (payload.case_a, payload.case_b):
        case = await svc.get_by_case_id(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Judgment not found.")
        if not case.is_embedded:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"“{case.case_name}” is still being indexed. Try again shortly.",
            )
        cases.append({"case_id": case.case_id, "case_name": case.case_name})

    question = (payload.question or "").strip() or _DEFAULT_QUESTION
    result = await RAGPipeline().compare(cases[0], cases[1], question)
    return CompareResponse(
        case_a=payload.case_a,
        case_b=payload.case_b,
        question=question,
        answer=result.answer,
        sufficient_context=result.sufficient_context,
        citations=result.citations,
        latency_ms=result.latency_ms,
    )
