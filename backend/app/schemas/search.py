from datetime import date

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    court: str | None = None
    judge: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    acts: list[str] | None = None
    sections: list[str] | None = None
    decision_type: str | None = None
    min_similarity: float = Field(default=0.6, ge=0.0, le=1.0)


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    filters: SearchFilters | None = None
    top_k: int = Field(default=10, ge=1, le=50)
    search_type: str = Field(default="hybrid", pattern=r"^(semantic|hybrid|keyword)$")
    include_full_text: bool = False


class SearchResult(BaseModel):
    case_id: str
    case_name: str
    court: str | None = None
    judges: list[str] | None = None
    judgment_date: str | None = None
    acts: list[str] | None = None
    chunk_content: str
    similarity_score: float
    rank: int
    highlights: list[str] = []
    chunk_id: str | None = None
    page_number: int | None = None


class SearchResponse(BaseModel):
    query: str
    rewritten_query: str | None = None
    results: list[SearchResult]
    total_results: int
    search_type: str
    latency_ms: int
    filters_applied: SearchFilters | None = None
