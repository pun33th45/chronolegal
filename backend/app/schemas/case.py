import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class LegalEntityExtraction(BaseModel):
    judges: list[str] = []
    courts: list[str] = []
    acts: list[str] = []
    sections: list[str] = []
    lawyers: list[str] = []
    organizations: list[str] = []
    dates: list[str] = []
    locations: list[str] = []
    parties: list[str] = []


class TimelineEvent(BaseModel):
    date: str
    event: str
    description: str | None = None


class CaseChunkRead(BaseModel):
    id: uuid.UUID
    chunk_index: int
    content: str
    page_number: int | None = None
    chroma_id: str | None = None

    model_config = {"from_attributes": True}


class LegalCaseSummary(BaseModel):
    id: uuid.UUID
    case_id: str
    case_name: str
    court: str | None = None
    judges: list[str] | None = None
    judgment_date: date | None = None
    acts: list[str] | None = None
    decision_type: str | None = None
    summary: str | None = None
    citation_count: int = 0

    model_config = {"from_attributes": True}


class LegalCaseRead(BaseModel):
    id: uuid.UUID
    case_id: str
    case_name: str
    case_number: str | None = None
    petitioner: str | None = None
    respondent: str | None = None
    parties: list[str] | None = None
    court: str | None = None
    bench: str | None = None
    judges: list[str] | None = None
    judgment_date: date | None = None
    acts: list[str] | None = None
    sections: list[str] | None = None
    keywords: list[str] | None = None
    full_text: str | None = None
    summary: str | None = None
    headnotes: str | None = None
    decision_type: str | None = None
    outcome: str | None = None
    text_length: int | None = None
    cited_cases: list[str] | None = None
    citation_count: int = 0
    chunk_count: int = 0
    is_embedded: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class SummaryRequest(BaseModel):
    case_id: str
    summary_type: str = Field(
        default="concise",
        pattern=r"^(concise|detailed|bullet)$",
    )
    max_length: int = Field(default=500, ge=100, le=3000)


class SummaryResponse(BaseModel):
    case_id: str
    case_name: str
    summary_type: str
    summary: str
    generated_at: datetime
