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
    rank: int
    page_number: int | None = None
    court: str | None = None
    date: str | None = None
    acts: list[str] | None = None


class RelatedCase(BaseModel):
    case_id: str
    case_name: str
    court: str | None = None
    similarity_score: float
    relationship_type: str = "similar"


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=10000)
    stream: bool = False
    top_k: int = Field(default=5, ge=1, le=20)
    filters: dict[str, Any] | None = None
    include_related_cases: bool = True


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    citations: list[Citation]
    related_cases: list[RelatedCase] = []
    query_rewritten: str | None = None
    context_used: bool = True
    sufficient_context: bool = True
    latency_ms: int
    token_count: int | None = None
    generated_at: datetime


class StreamChunk(BaseModel):
    type: str  # text | citation | done | error
    content: str | None = None
    citations: list[Citation] | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    error: str | None = None
