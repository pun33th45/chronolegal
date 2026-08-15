import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse, StreamChunk
from app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    ConversationWithMessages,
)
from app.services.legal.conversation_service import ConversationService
from app.services.ai.rag_pipeline import RAGPipeline

router = APIRouter()


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

    # Save user message
    history = await conv_svc.get_messages(conversation.id, limit=10)
    await conv_svc.add_message(conversation.id, role="user", content=payload.message)

    # Run RAG pipeline
    result = await rag.run(
        query=payload.message,
        conversation_history=history,
        top_k=payload.top_k,
        filters=payload.filters,
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
    if conversation.message_count == 0:
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
    await conv_svc.add_message(conversation.id, role="user", content=payload.message)

    async def event_generator():
        full_answer = ""
        citations = []
        try:
            async for chunk in rag.stream(
                query=payload.message,
                conversation_history=history,
                top_k=payload.top_k,
                filters=payload.filters,
            ):
                if chunk.type == "text":
                    full_answer += chunk.content or ""
                elif chunk.type == "citation":
                    citations = chunk.citations or []

                data = chunk.model_dump_json()
                yield f"data: {data}\n\n"

            # Persist final answer
            await conv_svc.add_message(
                conversation_id=conversation.id,
                role="assistant",
                content=full_answer,
                citations=citations,
            )

            done_chunk = StreamChunk(
                type="done",
                conversation_id=str(conversation.id),
            )
            yield f"data: {done_chunk.model_dump_json()}\n\n"

        except Exception as e:
            error_chunk = StreamChunk(type="error", error=str(e))
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
    page: int = 1,
    page_size: int = 20,
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
