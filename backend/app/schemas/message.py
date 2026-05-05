from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AttachmentSummary(BaseModel):
    """Метаданные вложения, которые видит клиент в составе сообщения."""

    id: int
    mime_type: str
    size_bytes: int
    # Для картинок не задан — превью рисуется по mime_type. Для файлов
    # клиент использует это имя в баббле и при «Сохранить как».
    original_filename: str | None = None


class MessageCreate(BaseModel):
    """Payload for POST /messages.

    The server treats every field as opaque bytes (hex-encoded on the
    wire). It never sees plaintext.
    """

    recipient_id: int
    # Текст и/или вложение. Если только картинка — клиент шлёт
    # «пустую» seal'ку (текст из одного пробела) ради простоты.
    # 64 000 hex = 32 КБ шифртекста ≈ 16 000 кириллических символов запаса.
    encrypted_payload_hex: str = Field(min_length=2, max_length=64000)
    nonce_hex: str = Field(min_length=16, max_length=16)         # 8 bytes
    signature_hex: str = Field(min_length=128, max_length=128)   # 64 bytes
    attachment_id: int | None = None


class MessageEdit(BaseModel):
    """Payload for PATCH /messages/{id}.

    The whole sealed envelope is replaced — the client re-encrypts and
    re-signs the new plaintext, the server only checks the signature.
    """

    encrypted_payload_hex: str = Field(min_length=2, max_length=64000)
    nonce_hex: str = Field(min_length=16, max_length=16)
    signature_hex: str = Field(min_length=128, max_length=128)


class MessageOut(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    encrypted_payload_hex: str
    nonce_hex: str
    signature_hex: str
    created_at: datetime
    edited_at: datetime | None = None
    read_at: datetime | None = None
    attachment: AttachmentSummary | None = None


class ConversationSummary(BaseModel):
    peer_id: int
    last_message: MessageOut | None = None
    unread_count: int = 0


class MessageWS(BaseModel):
    """WebSocket envelope used both for inbound sends and outbound deliveries."""

    # "send" | "delivery" | "ack" | "update" | "delete" | "read" | "error"
    type: str
    message: MessageOut | None = None
    message_id: int | None = None
    peer_id: int | None = None
    error: str | None = None
