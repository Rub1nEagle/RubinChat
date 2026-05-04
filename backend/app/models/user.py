from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))

    # 64-byte raw public key (x || y).
    public_key: Mapped[bytes] = mapped_column(LargeBinary(64))

    # 40-byte blob: nonce(8) || ciphertext(32) — приватный ключ, зашифрованный паролем.
    encrypted_private_key: Mapped[bytes] = mapped_column(LargeBinary(40))

    # Профиль (заполняется самим пользователем).
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True, default=None)
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)

    # Аватар. Хранится в открытом виде — он публичен по смыслу
    # (виден всем контактам), шифровать нечем (нет общего ключа).
    avatar_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, default=None)
    avatar_mime: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    # Версия — инкрементируется при каждом обновлении/удалении, чтобы
    # клиенты могли делать кеш-баст: GET /users/{id}/avatar?v=N.
    avatar_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
