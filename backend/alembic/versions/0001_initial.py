"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("public_key", sa.LargeBinary(length=64), nullable=False),
        sa.Column("encrypted_private_key", sa.LargeBinary(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("encrypted_payload", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(length=8), nullable=False),
        sa.Column("signature", sa.LargeBinary(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_messages_recipient_id_created_at",
        "messages",
        ["recipient_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_recipient_id_created_at", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
