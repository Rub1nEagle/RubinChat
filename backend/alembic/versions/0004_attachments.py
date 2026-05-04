"""attachments table + messages.attachment_id

Revision ID: 0004_attachments
Revises: 0003_user_profile
Create Date: 2026-04-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_attachments"
down_revision: Union[str, None] = "0003_user_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(length=8), nullable=False),
        sa.Column("encrypted_data", sa.LargeBinary(), nullable=False),
        sa.Column("signature", sa.LargeBinary(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_attachments_sender_id", "attachments", ["sender_id"])
    op.create_index("ix_attachments_recipient_id", "attachments", ["recipient_id"])

    op.add_column(
        "messages",
        sa.Column(
            "attachment_id",
            sa.Integer(),
            sa.ForeignKey("attachments.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_messages_attachment_id", "messages", ["attachment_id"])


def downgrade() -> None:
    op.drop_index("ix_messages_attachment_id", table_name="messages")
    op.drop_column("messages", "attachment_id")
    op.drop_index("ix_attachments_recipient_id", table_name="attachments")
    op.drop_index("ix_attachments_sender_id", table_name="attachments")
    op.drop_table("attachments")
