"""drop user avatar columns (transient — restored by 0007)

Revision ID: 0006_drop_user_avatar
Revises: 0005_user_avatar
Create Date: 2026-04-30 18:00:00.000000

История: эта миграция была создана в момент, когда фича аватаров была
временно вырезана из кода. Потом фича вернулась через merge, и колонки
снова стали нужны. Файл оставлен только для того, чтобы Alembic мог
найти ревизию у тех, кто 0006 успел применить (иначе на старте
``Can't locate revision identified by '0006_drop_user_avatar'``).
Восстановление колонок — в 0007.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006_drop_user_avatar"
down_revision: Union[str, None] = "0005_user_avatar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS avatar_version")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS avatar_mime")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS avatar_data")


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column("users", sa.Column("avatar_data", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("avatar_mime", sa.String(length=64), nullable=True))
    op.add_column(
        "users",
        sa.Column("avatar_version", sa.Integer(), nullable=False, server_default="0"),
    )
