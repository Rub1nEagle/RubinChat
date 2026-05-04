"""message edit/read state

Revision ID: 0002_message_state
Revises: 0001_initial
Create Date: 2026-04-25 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_message_state"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_messages_recipient_unread",
        "messages",
        ["recipient_id", "sender_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_messages_recipient_unread", table_name="messages")
    op.drop_column("messages", "read_at")
    op.drop_column("messages", "edited_at")
