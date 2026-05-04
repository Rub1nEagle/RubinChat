from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # Шифртекст (server never sees plaintext).
    encrypted_payload: Mapped[bytes] = mapped_column(LargeBinary)
    nonce: Mapped[bytes] = mapped_column(LargeBinary(8))
    signature: Mapped[bytes] = mapped_column(LargeBinary(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Опциональная ссылка на вложение (картинку). Пусто = чисто-текстовое.
    attachment_id: Mapped[int | None] = mapped_column(
        ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )

    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])
    attachment = relationship("Attachment", foreign_keys=[attachment_id])


Index("ix_messages_recipient_id_created_at", Message.recipient_id, Message.created_at.desc())
Index(
    "ix_messages_recipient_unread",
    Message.recipient_id,
    Message.sender_id,
    postgresql_where=Message.read_at.is_(None),
)
