import uuid
from datetime import datetime

from pydantic import BaseModel


class SearchLogRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    query: str
    rewritten_query: str | None = None
    result_count: int | None = None
    top_score: float | None = None
    latency_ms: int | None = None
    search_type: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TopItem(BaseModel):
    name: str
    count: int


class CaseTrend(BaseModel):
    year: int
    count: int


class CourtDistribution(BaseModel):
    court: str
    count: int
    percentage: float


class DecisionTypeStats(BaseModel):
    decision_type: str
    count: int
    percentage: float


class AnalyticsDashboard(BaseModel):
    total_cases: int
    total_embeddings: int
    total_users: int
    total_searches: int
    top_acts: list[TopItem]
    top_courts: list[CourtDistribution]
    top_judges: list[TopItem]
    top_keywords: list[TopItem]
    case_trends: list[CaseTrend]
    decision_types: list[DecisionTypeStats]
    avg_text_length: float
    avg_search_latency_ms: float
    storage_used_mb: float


class AdminStats(BaseModel):
    total_cases: int
    embedded_cases: int
    pending_embedding: int
    total_chunks: int
    chroma_collection_count: int
    total_users: int
    active_users_today: int
    total_searches_today: int
    avg_latency_ms: float
    cache_hit_rate: float
    storage_used_mb: float
