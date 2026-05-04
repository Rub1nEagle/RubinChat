"""user avatar (avatar_data + mime + version)

Revision ID: 0005_user_avatar
Revises: 0004_attachments
Create Date: 2026-04-30 12:00:00.000000

Note: фича аватаров в коде удалена, но если миграцию успели применить —
в БД остались колонки и сама ревизия в ``alembic_version``. Этот файл
существует только чтобы Alembic знал такую ревизию (иначе на старте
``Can't locate revision identified by '0005_user_avatar'``). Реальная
очистка колонок — в следующей миграции 0006.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_user_avatar"
down_revision: Union[str, None] = "0004_attachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_data", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("avatar_mime", sa.String(length=64), nullable=True))
    op.add_column(
        "users",
        sa.Column("avatar_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_version")
    op.drop_column("users", "avatar_mime")
    op.drop_column("users", "avatar_data")
