"""Add users.google_subject_id for Google Sign-In

Stores the OpenID Connect `sub` claim of a linked Google account — Google's
permanent account identifier. Additive and nullable: every existing user
keeps working unchanged with google_subject_id = NULL.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-06 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("google_subject_id", sa.String(255), nullable=True)
    )
    op.create_index(
        "ix_users_google_subject_id", "users", ["google_subject_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_users_google_subject_id", table_name="users")
    op.drop_column("users", "google_subject_id")
