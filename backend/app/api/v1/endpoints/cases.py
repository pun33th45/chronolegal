import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.schemas.case import (
    CaseChunkRead,
    CasePassageRead,
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
    cases = await svc.list_cases(
        page=page,
        page_size=page_size,
        court=court,
        date_from=date_from,
        date_to=date_to,
        act=act,
        q=q,
        sort_by=sort_by,
    )
    return [
        LegalCaseSummary.model_validate(c).model_copy(
            update={"can_delete": _can_delete(c.case_id, current_user)}
        )
        for c in cases
    ]


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
    return LegalCaseRead.model_validate(case).model_copy(
        update={"can_delete": _can_delete(case.case_id, current_user)}
    )


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


@router.get("/{case_id}/passages/{chunk_index}", response_model=CasePassageRead)
async def get_case_passage(
    case_id: str,
    chunk_index: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The exact passage a citation points to (citation chunk_id is
    "{case_id}__chunk_{chunk_index}"). Uploaded judgments have it in
    case_chunks; seeded cases were embedded straight into the vector index,
    so fall back to reading that same passage from Chroma by its id."""
    import asyncio

    svc = CaseService(db)
    case = await svc.get_by_case_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    chunk = await svc.get_chunk_by_index(case.id, chunk_index)
    if chunk is not None:
        return CasePassageRead(
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            section_header=(chunk.chunk_metadata or {}).get("section_header"),
            page_number=chunk.page_number,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
        )

    from app.services.ai.embedding_service import get_collection

    try:
        collection = get_collection()
        found = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: collection.get(
                ids=[f"{case_id}__chunk_{chunk_index}"],
                include=["documents", "metadatas"],
            ),
        )
    except Exception as e:
        logger.warning(f"Passage lookup failed for case_id={case_id}: {e}")
        found = {"documents": []}
    if not found.get("documents"):
        raise HTTPException(status_code=404, detail="Source passage unavailable")
    meta = (found.get("metadatas") or [{}])[0] or {}
    return CasePassageRead(
        chunk_index=chunk_index,
        content=found["documents"][0],
        section_header=meta.get("section_header"),
        start_char=meta.get("start_char"),
        end_char=meta.get("end_char"),
    )


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
    """Deletes a judgment, its chunks and its vectors as one unit.

    Order: the Postgres rows are deleted inside the open transaction (case
    row + case_chunks via ON DELETE CASCADE) and flushed but NOT committed;
    then the judgment's Chroma vectors are removed; only then is the
    transaction committed. If the vector delete fails, the transaction is
    rolled back and nothing is deleted — no half-deleted judgment and no
    orphaned vectors that RAG could still retrieve.

    A judgment with no vectors (e.g. an older upload whose indexing never
    completed) or no chunks is still deletable: Chroma's filtered delete is
    a no-op when nothing matches.
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

    try:
        await svc.delete_case(case)
        await db.flush()
    except Exception as e:
        await db.rollback()
        logger.error(f"Postgres deletion failed for case_id={case_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to delete this judgment. Please try again.",
        )

    loop = asyncio.get_event_loop()
    try:
        collection = get_collection()
        await loop.run_in_executor(
            None, lambda: collection.delete(where={"case_id": case_id})
        )
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Chroma deletion failed for case_id={case_id}; database changes "
            f"rolled back, nothing was deleted: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to delete this judgment. Please try again.",
        )

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Commit failed for case_id={case_id} after its vectors were "
            f"removed; the case record remains and deleting it again will "
            f"complete cleanly: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to delete this judgment. Please try again.",
        )
    logger.info(f"Deleted judgment case_id={case_id}")

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
