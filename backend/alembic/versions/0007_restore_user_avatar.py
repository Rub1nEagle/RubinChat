"""restore user avatar columns

Revision ID: 0007_restore_user_avatar
Revises: 0006_drop_user_avatar
Create Date: 2026-04-30 20:00:00.000000

После merge фича аватаров вернулась в код, а 0006 успел дропнуть колонки
на боевом контуре. Эта миграция возвращает их обратно. Идемпотентна:
``ADD COLUMN IF NOT EXISTS`` корректно отрабатывает и там, где 0006
не применялся (колонки уже стоят с 0005).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007_restore_user_avatar"
down_revision: Union[str, None] = "0006_drop_user_avatar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_data BYTEA")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_mime VARCHAR(64)")
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_version INTEGER "
        "NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS avatar_version")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS avatar_mime")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS avatar_data")
