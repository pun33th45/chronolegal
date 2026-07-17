import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.services.legal.feedback_service import FeedbackService

router = APIRouter()


class FeedbackCreate(BaseModel):
    message_id: uuid.UUID | None = None
    query: str
    rating: int | None = Field(default=None, ge=1, le=5)
    is_helpful: bool | None = None
    comment: str | None = None
    retrieved_doc_ids: list[str] | None = None


@router.post("/", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = FeedbackService(db)
    await svc.create(user_id=current_user.id, **payload.model_dump())
    return {"message": "Feedback submitted successfully"}
