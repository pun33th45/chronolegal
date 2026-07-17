import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    case_id: str
    case_name: str
    chunk_id: str
    content: str
    similarity_score: float
    page_number: int | None = None
    court: str | None = None
    date: str | None = None


class MessageCreate(BaseModel):
    role: str = Field(pattern=r"^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=32000)


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    citations: list[Citation] | None = None
    token_count: int | None = None
    latency_ms: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    title: str = Field(default="New Conversation", max_length=500)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    is_archived: bool | None = None


class ConversationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    is_archived: bool
    message_count: int
    created_at: datetime
    updated_at: datetime
    last_message: MessageRead | None = None

    model_config = {"from_attributes": True}


class ConversationWithMessages(ConversationRead):
    messages: list[MessageRead] = []
