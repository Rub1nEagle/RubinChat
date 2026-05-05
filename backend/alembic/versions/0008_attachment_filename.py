"""attachments.original_filename + расширение mime_type до 128

Revision ID: 0008_attachment_filename
Revises: 0007_restore_user_avatar
Create Date: 2026-05-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_attachment_filename"
down_revision: Union[str, None] = "0007_restore_user_avatar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Имя файла нужно только для не-картинок; nullable, чтобы старые
    # вложения-картинки прошли миграцию без backfill'а.
    op.add_column(
        "attachments",
        sa.Column("original_filename", sa.String(length=255), nullable=True),
    )
    # Раньше колонка была String(64) — для длинных мимов вроде
    # `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
    # (71 символ) тесно. 128 — с запасом.
    op.alter_column(
        "attachments",
        "mime_type",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "attachments",
        "mime_type",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.drop_column("attachments", "original_filename")
