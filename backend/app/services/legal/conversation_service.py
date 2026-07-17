import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation, Message
from app.schemas.conversation import ConversationCreate, ConversationUpdate


class ConversationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, payload: ConversationCreate, user_id: uuid.UUID) -> Conversation:
        conv = Conversation(user_id=user_id, title=payload.title)
        self.db.add(conv)
        await self.db.flush()
        await self.db.refresh(conv)
        return conv

    async def get(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_with_messages(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> list[Conversation]:
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.is_archived == False,
            )
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all())

    async def update(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: ConversationUpdate,
    ) -> Conversation | None:
        conv = await self.get(conversation_id, user_id)
        if not conv:
            return None
        updates = payload.model_dump(exclude_none=True)
        if updates:
            await self.db.execute(
                update(Conversation)
                .where(Conversation.id == conversation_id)
                .values(**updates)
            )
            await self.db.refresh(conv)
        return conv

    async def delete(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        conv = await self.get(conversation_id, user_id)
        if not conv:
            return False
        await self.db.delete(conv)
        return True

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        citations: list[Any] | None = None,
        latency_ms: int | None = None,
    ) -> Message:
        citations_data = None
        if citations:
            citations_data = [
                c.model_dump() if hasattr(c, "model_dump") else c for c in citations
            ]

        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations_data,
            latency_ms=latency_ms,
        )
        self.db.add(msg)
        await self.db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(message_count=Conversation.message_count + 1)
        )
        await self.db.flush()
        await self.db.refresh(msg)
        return msg

    async def get_messages(
        self, conversation_id: uuid.UUID, limit: int = 20
    ) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        return list(reversed(messages))
