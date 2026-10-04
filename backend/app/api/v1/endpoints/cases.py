import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.schemas.case import (
    CaseChunkRead,
    LegalCaseRead,
    LegalCaseSummary,
    SimilarCaseResult,
)
from app.services.legal.case_service import CaseService

router = APIRouter()

# Uploaded cases are id'd as f"upload_{user_id}_{task_id_prefix}" at
# creation time (app/services/ai/document_processor.py) — there is no
# separate ownership column on LegalCase, so this prefix *is* the existing
# ownership record. Seeded/demo cases (e.g. "kesavananda-bharati-1973")
# never match it and have no individual owner.
_UPLOAD_CASE_ID_RE = re.compile(r"^upload_([0-9a-fA-F-]{36})_")


def _can_delete(case_id: str, current_user) -> bool:
    if current_user.is_admin:
        return True
    m = _UPLOAD_CASE_ID_RE.match(case_id)
    return bool(m) and m.group(1) == str(current_user.id)


@router.get("/", response_model=list[LegalCaseSummary])
async def list_cases(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    court: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    act: str | None = None,
    q: str | None = Query(default=None, description="Case name search"),
    sort_by: str | None = Query(default=None, pattern="^(recent|name|chunks)$"),
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
        q=q,
        sort_by=sort_by,
    )


@router.get("/count")
async def count_cases(
    court: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    act: str | None = None,
    q: str | None = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseService(db)
    total = await svc.count_cases(
        court=court, date_from=date_from, date_to=date_to, act=act, q=q
    )
    return {"total": total}


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
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseService(db)
    case = await svc.get_by_case_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return await svc.get_chunks(case.id, page=page, page_size=page_size)


@router.get("/{case_id}/similar", response_model=list[SimilarCaseResult])
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


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deletes a judgment's Chroma vectors first, then its Postgres record
    (chunks cascade). Chroma is deleted first deliberately: if anything
    fails partway, the worst case is a Postgres row with no vectors behind
    it (visible but inert — safe, and fixable by deleting it again), rather
    than the reverse order's failure mode of Chroma vectors with no
    Postgres record, which RAG could still retrieve despite the case no
    longer appearing anywhere in the app — exactly the "orphaned knowledge"
    this must not produce.
    """
    import asyncio

    svc = CaseService(db)
    case = await svc.get_by_case_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if not _can_delete(case_id, current_user):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to delete this judgment",
        )

    from app.services.ai.embedding_service import get_collection

    loop = asyncio.get_event_loop()
    try:
        collection = get_collection()
        await loop.run_in_executor(
            None, lambda: collection.delete(where={"case_id": case_id})
        )
    except Exception as e:
        logger.error(f"Chroma deletion failed for case_id={case_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to delete this judgment. Please try again.",
        )

    try:
        await svc.delete_case(case)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Postgres deletion failed for case_id={case_id} after its "
            f"Chroma vectors were already removed — the case record "
            f"remains but its indexed knowledge is gone. Deleting it "
            f"again will complete cleanly since Chroma has nothing left "
            f"to remove: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "This judgment's indexed knowledge was removed, but "
                "finishing the deletion failed. Please try deleting it "
                "again."
            ),
        )

    # The RAG answer cache is keyed by a hash of (query, filters) — a
    # question identical to one asked before this deletion would otherwise
    # still resolve to its cached pre-deletion answer, even though the
    # underlying Chroma vectors are now genuinely gone. Clearing the whole
    # namespace (not just this case_id, which isn't recoverable from an
    # opaque hash) is cheap: it only costs the next asker one real
    # round-trip instead of a cache hit.
    from app.core.redis import cache

    await cache.delete_pattern("rag:*")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
