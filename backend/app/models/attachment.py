from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database.base import Base


class Attachment(Base):
    """Зашифрованное вложение к сообщению (картинка или произвольный файл).

    По схеме проекта сервер сам выполняет seal/unseal. Содержимое
    шифруется тем же conversation-key (Streebog от sorted user_id) и
    подписывается личным ключом отправителя — точно как текстовые
    сообщения. ``original_filename`` нужен для НЕ-картинок: клиент
    показывает его в пузыре и подставляет при скачивании.
    """

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )

    nonce: Mapped[bytes] = mapped_column(LargeBinary(8), nullable=False)
    encrypted_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    signature: Mapped[bytes] = mapped_column(LargeBinary(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])
