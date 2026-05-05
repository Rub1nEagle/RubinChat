"""Message persistence + signature verification + replay protection.

We never decrypt the payload; we only verify the signature over
(encrypted_payload || nonce) using the sender's stored public key, and
reject duplicate nonces within a sliding window.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.config import get_settings
from ..crypto.provider import provider
from ..models import Attachment, Message, User
from ..schemas.message import (
    AttachmentSummary,
    ConversationSummary,
    MessageCreate,
    MessageEdit,
    MessageOut,
)


class MessageError(Exception):
    """Raised on validation, signature, or authorization failure."""


class _NonceCache:
    """Tiny in-memory anti-replay cache, sliding by wall clock."""

    def __init__(self) -> None:
        self._seen: OrderedDict[bytes, float] = OrderedDict()

    def remember(self, nonce: bytes) -> bool:
        ttl = get_settings().nonce_window_seconds
        now = datetime.now(timezone.utc).timestamp()
        while self._seen:
            key, ts = next(iter(self._seen.items()))
            if now - ts > ttl:
                self._seen.popitem(last=False)
            else:
                break
        if nonce in self._seen:
            return False
        self._seen[nonce] = now
        return True


_nonce_cache = _NonceCache()


def _attachment_summary(att: Attachment | None) -> AttachmentSummary | None:
    if att is None:
        return None
    return AttachmentSummary(
        id=att.id,
        mime_type=att.mime_type,
        size_bytes=att.size_bytes,
        original_filename=att.original_filename,
    )


def _to_out(msg: Message, attachment: Attachment | None = None) -> MessageOut:
    return MessageOut(
        id=msg.id,
        sender_id=msg.sender_id,
        recipient_id=msg.recipient_id,
        encrypted_payload_hex=msg.encrypted_payload.hex(),
        nonce_hex=msg.nonce.hex(),
        signature_hex=msg.signature.hex(),
        created_at=msg.created_at,
        edited_at=msg.edited_at,
        read_at=msg.read_at,
        attachment=_attachment_summary(attachment),
    )


def _decode_envelope(
    payload_hex: str, nonce_hex: str, signature_hex: str
) -> tuple[bytes, bytes, bytes]:
    try:
        encrypted = bytes.fromhex(payload_hex)
        nonce = bytes.fromhex(nonce_hex)
        signature = bytes.fromhex(signature_hex)
    except ValueError as exc:
        raise MessageError("invalid hex payload") from exc
    if len(nonce) != 8:
        raise MessageError("nonce must decode to 8 bytes")
    if len(signature) != 64:
        raise MessageError("signature must decode to 64 bytes")
    if not encrypted:
        raise MessageError("encrypted_payload must not be empty")
    return encrypted, nonce, signature


async def store_message(
    session: AsyncSession,
    sender: User,
    payload: MessageCreate,
) -> MessageOut:
    encrypted, nonce, signature = _decode_envelope(
        payload.encrypted_payload_hex, payload.nonce_hex, payload.signature_hex
    )

    if not _nonce_cache.remember(nonce):
        raise MessageError("nonce replay detected")

    recipient = await session.get(User, payload.recipient_id)
    if recipient is None:
        raise MessageError("recipient does not exist")

    if not await provider.verify(encrypted + nonce, signature, sender.public_key):
        raise MessageError("signature verification failed")

    attachment: Attachment | None = None
    if payload.attachment_id is not None:
        attachment = await session.get(Attachment, payload.attachment_id)
        if attachment is None:
            raise MessageError("attachment not found")
        if attachment.sender_id != sender.id or attachment.recipient_id != recipient.id:
            raise MessageError("attachment does not belong to this conversation")

    msg = Message(
        sender_id=sender.id,
        recipient_id=recipient.id,
        encrypted_payload=encrypted,
        nonce=nonce,
        signature=signature,
        attachment_id=attachment.id if attachment is not None else None,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return _to_out(msg, attachment)


async def edit_message(
    session: AsyncSession,
    sender: User,
    message_id: int,
    payload: MessageEdit,
) -> MessageOut:
    msg = await session.get(Message, message_id)
    if msg is None:
        raise MessageError("message not found")
    if msg.sender_id != sender.id:
        raise MessageError("only the sender can edit this message")

    encrypted, nonce, signature = _decode_envelope(
        payload.encrypted_payload_hex, payload.nonce_hex, payload.signature_hex
    )

    if not _nonce_cache.remember(nonce):
        raise MessageError("nonce replay detected")

    if not await provider.verify(encrypted + nonce, signature, sender.public_key):
        raise MessageError("signature verification failed")

    msg.encrypted_payload = encrypted
    msg.nonce = nonce
    msg.signature = signature
    msg.edited_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(msg)
    attachment = None
    if msg.attachment_id is not None:
        attachment = await session.get(Attachment, msg.attachment_id)
    return _to_out(msg, attachment)


async def delete_message(
    session: AsyncSession,
    user: User,
    message_id: int,
) -> Message:
    msg = await session.get(Message, message_id)
    if msg is None:
        raise MessageError("message not found")
    if msg.sender_id != user.id:
        raise MessageError("only the sender can delete this message")
    snapshot = msg
    recipient_id = msg.recipient_id
    sender_id = msg.sender_id
    await session.delete(msg)
    await session.commit()
    # Возвращаем «снимок» с уже удалённой записи — поля доступны до конца сессии.
    snapshot.recipient_id = recipient_id
    snapshot.sender_id = sender_id
    return snapshot


async def mark_conversation_read(
    session: AsyncSession,
    user_id: int,
    peer_id: int,
) -> int:
    """Помечает все непрочитанные сообщения от peer как прочитанные.
    Возвращает число затронутых строк.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        update(Message)
        .where(
            Message.recipient_id == user_id,
            Message.sender_id == peer_id,
            Message.read_at.is_(None),
        )
        .values(read_at=now)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


async def list_for_user(
    session: AsyncSession,
    user_id: int,
    peer_id: int | None = None,
    limit: int = 100,
    before_id: int | None = None,
) -> list[MessageOut]:
    """Возвращает последние ``limit`` сообщений в хронологическом порядке.

    Поддержка пагинации скроллом вверх: если задан ``before_id`` — отдаём
    последние ``limit`` сообщений со строго меньшим id (т.е. более старые
    относительно курсора). Без курсора — самые свежие N.

    Сортировка: внутри SQL берём ``desc().limit()`` (чтобы PostgreSQL
    использовал индекс по created_at и дёргал только нужный хвост), затем
    разворачиваем результат в Python — UI ожидает asc.
    """
    stmt = select(Message).where(
        or_(Message.recipient_id == user_id, Message.sender_id == user_id)
    )
    if peer_id is not None:
        stmt = stmt.where(
            or_(
                and_(Message.sender_id == user_id, Message.recipient_id == peer_id),
                and_(Message.sender_id == peer_id, Message.recipient_id == user_id),
            )
        )
    if before_id is not None:
        stmt = stmt.where(Message.id < before_id)
    # `id.desc()` — стабильный tiebreaker: при одинаковом created_at
    # (рапид-инсёрты в одну миллисекунду в SQLite/тестах) сортировка по
    # одному только времени даёт неопределённый порядок и срезает не тот
    # хвост.
    stmt = (
        stmt.options(selectinload(Message.attachment))
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    msgs = list(result.scalars().all())
    msgs.reverse()  # asc для UI
    return [_to_out(m, m.attachment) for m in msgs]


async def list_conversations(
    session: AsyncSession,
    user_id: int,
) -> list[ConversationSummary]:
    """Сводка по перепискам: с кем общались, последнее сообщение, непрочитанные."""
    stmt = (
        select(Message)
        .where(or_(Message.sender_id == user_id, Message.recipient_id == user_id))
        .options(selectinload(Message.attachment))
        .order_by(Message.created_at.asc())
    )
    result = await session.execute(stmt)

    summary: dict[int, dict] = {}
    for m in result.scalars():
        peer = m.recipient_id if m.sender_id == user_id else m.sender_id
        s = summary.setdefault(peer, {"last": None, "unread": 0})
        s["last"] = m
        if m.recipient_id == user_id and m.read_at is None:
            s["unread"] += 1

    return [
        ConversationSummary(
            peer_id=peer,
            last_message=_to_out(s["last"], s["last"].attachment) if s["last"] is not None else None,
            unread_count=s["unread"],
        )
        for peer, s in summary.items()
    ]


def serialize_messages(messages: Iterable[Message]) -> list[MessageOut]:
    # Внимание: вызывающий код должен заранее подгрузить attachment'ы
    # (через selectinload), иначе будет lazy-load в async-контексте.
    return [_to_out(m, getattr(m, "attachment", None)) for m in messages]
