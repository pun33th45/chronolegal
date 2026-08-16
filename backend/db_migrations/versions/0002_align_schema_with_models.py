"""Align schema with models — case_number index + timestamp NOT NULL

Corrects two confirmed discrepancies between 0001_initial.py and the ORM
models (see backend/tests/integration/test_migration_schema.py):

1. LegalCase.case_number is declared index=True on the model, but
   0001_initial.py never created ix_legal_cases_case_number.
2. TimestampMixin declares created_at/updated_at as nullable=False, but
   0001_initial.py's raw sa.Column(...) calls omit NOT NULL, leaving both
   columns nullable on every table.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every table in 0001_initial.py has created_at/updated_at via TimestampMixin.
_TIMESTAMPED_TABLES = (
    "users",
    "conversations",
    "messages",
    "legal_cases",
    "case_chunks",
    "search_logs",
    "search_feedback",
)


def upgrade() -> None:
    op.create_index(
        "ix_legal_cases_case_number",
        "legal_cases",
        ["case_number"],
        unique=False,
    )

    # Both columns carry server_default=now() and no application code
    # anywhere assigns them explicitly, so no legitimate existing row
    # should have NULL here. This backfill is a defensive, zero-cost
    # safety net (a no-op UPDATE if no NULL rows exist) reusing the exact
    # same now() expression as the column's own server_default, applied
    # before the NOT NULL constraint so an existing, already-migrated
    # production database can't fail this upgrade.
    for table in _TIMESTAMPED_TABLES:
        op.execute(f"UPDATE {table} SET created_at = now() WHERE created_at IS NULL")
        op.execute(f"UPDATE {table} SET updated_at = now() WHERE updated_at IS NULL")
        op.alter_column(
            table,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_server_default=sa.func.now(),
            nullable=False,
        )
        op.alter_column(
            table,
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_server_default=sa.func.now(),
            nullable=False,
        )


def downgrade() -> None:
    for table in _TIMESTAMPED_TABLES:
        op.alter_column(
            table,
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_server_default=sa.func.now(),
            nullable=True,
        )
        op.alter_column(
            table,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_server_default=sa.func.now(),
            nullable=True,
        )

    op.drop_index("ix_legal_cases_case_number", table_name="legal_cases")
