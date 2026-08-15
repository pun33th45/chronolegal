import uuid
from datetime import date
from typing import Any

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class LegalCase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_cases"

    # Core identifiers
    case_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    case_name: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    case_number: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    # Parties
    petitioner: Mapped[str | None] = mapped_column(Text, nullable=True)
    respondent: Mapped[str | None] = mapped_column(Text, nullable=True)
    parties: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    # Court info
    court: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    bench: Mapped[str | None] = mapped_column(Text, nullable=True)
    judges: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    # Date
    judgment_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    date_raw: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Legal references
    acts: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    sections: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    # Full text
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    headnotes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Decision
    decision_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Analytics
    text_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cited_cases: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    citation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Source metadata
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Embedding status
    is_embedded: Mapped[bool] = mapped_column(default=False, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    chunks: Mapped[list["CaseChunk"]] = relationship(
        "CaseChunk",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<LegalCase id={self.id} name={self.case_name[:50]}>"


class CaseChunk(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "case_chunks"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chroma_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    start_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    case: Mapped[LegalCase] = relationship("LegalCase", back_populates="chunks")

    def __repr__(self) -> str:
        return (
            f"<CaseChunk id={self.id} case_id={self.case_id} index={self.chunk_index}>"
        )
