"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("is_verified", sa.Boolean, nullable=False, default=False),
        sa.Column("is_admin", sa.Boolean, nullable=False, default=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])

    # conversations
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False, default="New Conversation"),
        sa.Column("is_archived", sa.Boolean, nullable=False, default=False),
        sa.Column("message_count", sa.Integer, nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    # messages
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("citations", postgresql.JSONB, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # legal_cases
    op.create_table(
        "legal_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", sa.String(255), nullable=False, unique=True),
        sa.Column("case_name", sa.String(1000), nullable=False),
        sa.Column("case_number", sa.String(255), nullable=True),
        sa.Column("petitioner", sa.Text, nullable=True),
        sa.Column("respondent", sa.Text, nullable=True),
        sa.Column("parties", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("court", sa.String(500), nullable=True),
        sa.Column("bench", sa.Text, nullable=True),
        sa.Column("judges", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("judgment_date", sa.Date, nullable=True),
        sa.Column("date_raw", sa.String(100), nullable=True),
        sa.Column("acts", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("sections", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("full_text", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("headnotes", sa.Text, nullable=True),
        sa.Column("decision_type", sa.String(100), nullable=True),
        sa.Column("outcome", sa.String(500), nullable=True),
        sa.Column("text_length", sa.Integer, nullable=True),
        sa.Column("cited_cases", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("citation_count", sa.Integer, nullable=False, default=0),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("source_file", sa.String(500), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB, nullable=True),
        sa.Column("is_embedded", sa.Boolean, nullable=False, default=False),
        sa.Column("chunk_count", sa.Integer, nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_legal_cases_case_id", "legal_cases", ["case_id"])
    op.create_index("ix_legal_cases_case_name", "legal_cases", ["case_name"])
    op.create_index("ix_legal_cases_court", "legal_cases", ["court"])
    op.create_index("ix_legal_cases_judgment_date", "legal_cases", ["judgment_date"])

    # case_chunks
    op.create_table(
        "case_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("chroma_id", sa.String(255), nullable=True),
        sa.Column("start_char", sa.Integer, nullable=True),
        sa.Column("end_char", sa.Integer, nullable=True),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("chunk_metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_case_chunks_case_id", "case_chunks", ["case_id"])
    op.create_index("ix_case_chunks_chroma_id", "case_chunks", ["chroma_id"])

    # search_logs
    op.create_table(
        "search_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("rewritten_query", sa.Text, nullable=True),
        sa.Column("result_count", sa.Integer, nullable=True),
        sa.Column("top_score", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("search_type", sa.String(50), nullable=True),
        sa.Column("filters_used", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_search_logs_user_id", "search_logs", ["user_id"])

    # search_feedback
    op.create_table(
        "search_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("is_helpful", sa.Boolean, nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("retrieved_doc_ids", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("search_feedback")
    op.drop_table("search_logs")
    op.drop_table("case_chunks")
    op.drop_table("legal_cases")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("users")
