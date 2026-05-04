"""user profile fields (display_name / bio / last_seen_at)

Revision ID: 0003_user_profile
Revises: 0002_message_state
Create Date: 2026-04-25 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_user_profile"
down_revision: Union[str, None] = "0002_message_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("bio", sa.String(length=500), nullable=True))
    op.add_column(
        "users",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_seen_at")
    op.drop_column("users", "bio")
    op.drop_column("users", "display_name")
