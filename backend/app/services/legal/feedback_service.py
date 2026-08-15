import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import SearchFeedback


class FeedbackService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID | None,
        query: str,
        message_id: uuid.UUID | None = None,
        rating: int | None = None,
        is_helpful: bool | None = None,
        comment: str | None = None,
        retrieved_doc_ids: list[str] | None = None,
        **_: Any,
    ) -> SearchFeedback:
        feedback = SearchFeedback(
            user_id=user_id,
            message_id=message_id,
            query=query,
            rating=rating,
            is_helpful=is_helpful,
            comment=comment,
            retrieved_doc_ids=(
                ",".join(retrieved_doc_ids) if retrieved_doc_ids else None
            ),
        )
        self.db.add(feedback)
        await self.db.flush()
        return feedback
