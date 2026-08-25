import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import AsyncSessionLocal, get_db
from app.schemas.chat import ChatRequest, ChatResponse, StreamChunk
from app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    ConversationWithMessages,
)
from app.services.ai.rag_pipeline import RAGPipeline
from app.services.legal.case_service import CaseService
from app.services.legal.conversation_service import ConversationService

router = APIRouter()


async def _resolve_case_name(filters: dict | None, db: AsyncSession) -> str | None:
    """When a question is scoped to one case, look up its real name so the
    query rewriter has something concrete to substitute for "this case" /
    "this judgment" instead of inventing a placeholder — real, per-request
    data, not a hardcoded case name."""
    if not filters or not filters.get("case_id"):
        return None
    case = await CaseService(db).get_by_case_id(filters["case_id"])
    return case.case_name if case else None


@router.post("/", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv_svc = ConversationService(db)
    rag = RAGPipeline()

    if payload.stream:
        raise HTTPException(
            status_code=400,
            detail="Use /chat/stream for streaming responses",
        )

    # Create or fetch conversation
    if payload.conversation_id:
        conversation = await conv_svc.get(payload.conversation_id, current_user.id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = await conv_svc.create(
            ConversationCreate(title="New Conversation"), current_user.id
        )

    # Save user message. is_first_message must be read before add_message():
    # its bulk UPDATE gets synchronized back into this in-memory `conversation`
    # object, so checking message_count afterwards always sees the
    # post-increment value.
    history = await conv_svc.get_messages(conversation.id, limit=10)
    is_first_message = conversation.message_count == 0
    await conv_svc.add_message(conversation.id, role="user", content=payload.message)

    # Run RAG pipeline
    case_name = await _resolve_case_name(payload.filters, db)
    result = await rag.run(
        query=payload.message,
        conversation_history=history,
        top_k=payload.top_k,
        filters=payload.filters,
        case_name=case_name,
    )

    # Save assistant message
    message = await conv_svc.add_message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.answer,
        citations=result.citations,
        latency_ms=result.latency_ms,
    )

    # Auto-title conversation from first message
    if is_first_message:
        title = payload.message[:80] + ("..." if len(payload.message) > 80 else "")
        await conv_svc.update(
            conversation.id, current_user.id, ConversationUpdate(title=title)
        )

    return ChatResponse(
        conversation_id=conversation.id,
        message_id=message.id,
        answer=result.answer,
        citations=result.citations,
        related_cases=result.related_cases,
        query_rewritten=result.rewritten_query,
        context_used=result.context_used,
        sufficient_context=result.sufficient_context,
        latency_ms=result.latency_ms,
        token_count=result.token_count,
        generated_at=datetime.now(timezone.utc),
    )


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv_svc = ConversationService(db)
    rag = RAGPipeline()

    if payload.conversation_id:
        conversation = await conv_svc.get(payload.conversation_id, current_user.id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = await conv_svc.create(
            ConversationCreate(title="New Conversation"), current_user.id
        )

    history = await conv_svc.get_messages(conversation.id, limit=10)
    # Must read message_count before add_message(): its bulk UPDATE
    # (`message_count = message_count + 1`) gets synchronized back into this
    # same in-memory `conversation` object by SQLAlchemy's session-sync
    # evaluator, so checking afterwards would always see the post-increment
    # value and never detect "this was the first message".
    is_first_message = conversation.message_count == 0
    case_name = await _resolve_case_name(payload.filters, db)
    await conv_svc.add_message(conversation.id, role="user", content=payload.message)
    await db.commit()

    async def event_generator():
        full_answer = ""
        citations = []
        try:
            async for chunk in rag.stream(
                query=payload.message,
                conversation_history=history,
                top_k=payload.top_k,
                filters=payload.filters,
                case_name=case_name,
            ):
                if chunk.type == "text":
                    full_answer += chunk.content or ""
                elif chunk.type == "citation":
                    citations = chunk.citations or []

                data = chunk.model_dump_json()
                yield f"data: {data}\n\n"

            # Persist final answer using a fresh session: by the time this
            # generator runs, FastAPI has already torn down the request-scoped
            # `db` (get_db commits + closes it as soon as the endpoint function
            # returns the StreamingResponse object, well before the streamed
            # body — and this generator — actually finish). Writes through the
            # closed `db` silently never commit instead of raising, which is
            # what let the assistant's answer vanish from conversation history
            # on reload without ever surfacing as an error.
            async with AsyncSessionLocal() as fresh_db:
                fresh_conv_svc = ConversationService(fresh_db)
                await fresh_conv_svc.add_message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_answer,
                    citations=citations,
                )
                if is_first_message:
                    title = payload.message[:80] + (
                        "..." if len(payload.message) > 80 else ""
                    )
                    await fresh_conv_svc.update(
                        conversation.id,
                        current_user.id,
                        ConversationUpdate(title=title),
                    )
                await fresh_db.commit()

            done_chunk = StreamChunk(
                type="done",
                conversation_id=str(conversation.id),
            )
            yield f"data: {done_chunk.model_dump_json()}\n\n"

        except Exception as e:
            logger.error(
                f"Chat stream failed: conversation_id={conversation.id}, error={e}"
            )
            error_chunk = StreamChunk(
                type="error",
                error="An internal error occurred while generating the response.",
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ConversationService(db)
    return await svc.list_for_user(current_user.id, page=page, page_size=page_size)


@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ConversationService(db)
    conversation = await svc.get_with_messages(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.patch("/conversations/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ConversationService(db)
    updated = await svc.update(conversation_id, current_user.id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return updated


@router.delete(
    "/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ConversationService(db)
    deleted = await svc.delete(conversation_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
