import uuid

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class SearchFeedback(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "search_feedback"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    is_helpful: Mapped[bool | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_doc_ids: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<SearchFeedback id={self.id} rating={self.rating}>"
