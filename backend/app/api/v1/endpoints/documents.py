import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.services.legal.case_service import CaseService
from app.services.ai.document_processor import DocumentProcessor

router = APIRouter()

ALLOWED_TYPES = {
    "application/pdf",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}",
        )

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit",
        )

    processor = DocumentProcessor()
    task_id = await processor.process_upload(
        content=content,
        filename=file.filename or "document",
        content_type=file.content_type,
        user_id=str(current_user.id),
    )

    return {"task_id": task_id, "message": "Document processing started"}


@router.get("/upload/status/{task_id}")
async def get_upload_status(
    task_id: str,
    current_user=Depends(get_current_user),
):
    processor = DocumentProcessor()
    return await processor.get_task_status(task_id)
