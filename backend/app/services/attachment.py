"""Encrypted-attachment lifecycle (upload, fetch, decrypt).

По схеме проекта сервер делает seal/unseal сам — клиент шлёт plaintext-
байты файла плюс свой приватный ключ; сервер шифрует на conversation-key,
подписывает личным ключом отправителя и складывает в БД.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..crypto.conversation import conversation_key
from ..crypto.provider import provider
from ..models import Attachment, User
from ..services import user as user_service


class AttachmentError(Exception):
    """Validation, signing, or authorization failure."""


# Картинки — узкий белый список: фронт уже сжимает превью в JPEG,
# а пузырь с превью не должен внезапно стать SVG-инъекцией или EXE.
ALLOWED_IMAGE_MIME = frozenset({
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
})

# Файлы — чёрный список потенциально опасных типов. Всё остальное
# разрешено: пользователи присылают друг другу pdf/docx/zip/архивы и
# т.п. Сервер не исполняет содержимое, но клиент скачивает blob, и
# нам не нужны cross-site script-инъекции через свой же домен.
DENIED_FILE_MIME = frozenset({
    "text/html",
    "application/xhtml+xml",
    "application/javascript",
    "text/javascript",
    "application/x-msdownload",
    "application/x-msdos-program",
    "application/x-sh",
})

MAX_BYTES = 5 * 1024 * 1024  # 5 МБ


def _validate_image_mime(mime_type: str) -> None:
    if mime_type not in ALLOWED_IMAGE_MIME:
        raise AttachmentError("mime type not allowed")


def _validate_file_mime(mime_type: str) -> None:
    if not mime_type:
        raise AttachmentError("mime type required")
    if mime_type in DENIED_FILE_MIME:
        raise AttachmentError("mime type not allowed")


async def create_encrypted(
    session: AsyncSession,
    sender: User,
    recipient_id: int,
    plaintext: bytes,
    mime_type: str,
    sender_private_key_hex: str,
    *,
    kind: str = "image",
    original_filename: str | None = None,
) -> Attachment:
    if recipient_id == sender.id:
        raise AttachmentError("cannot send to self")
    if kind == "image":
        _validate_image_mime(mime_type)
    elif kind == "file":
        _validate_file_mime(mime_type)
    else:
        raise AttachmentError("unknown attachment kind")
    if not plaintext:
        raise AttachmentError("empty file")
    if len(plaintext) > MAX_BYTES:
        raise AttachmentError(f"file too large (max {MAX_BYTES} bytes)")

    recipient = await user_service.get_by_id(session, recipient_id)
    if recipient is None:
        raise AttachmentError("recipient not found")

    try:
        priv = bytes.fromhex(sender_private_key_hex)
    except ValueError as exc:
        raise AttachmentError("bad private key") from exc

    key = await conversation_key(sender.id, recipient.id)
    nonce = provider.random_nonce()
    encrypted = await provider.encrypt(plaintext, key, nonce)
    signature = await provider.sign(encrypted + nonce, priv)

    # Имя файла полезно только для не-картинок. Имя обрезаем до длины
    # колонки — длинные имена вроде «final_FINAL_v2 (1).pdf» спокойно
    # вмещаются, очень длинные мы не пытаемся хранить целиком.
    stored_filename = None
    if kind == "file" and original_filename:
        stored_filename = original_filename[:255]

    att = Attachment(
        sender_id=sender.id,
        recipient_id=recipient.id,
        mime_type=mime_type,
        size_bytes=len(plaintext),
        original_filename=stored_filename,
        nonce=nonce,
        encrypted_data=encrypted,
        signature=signature,
    )
    session.add(att)
    await session.commit()
    await session.refresh(att)
    return att


async def get_for_user(
    session: AsyncSession,
    attachment_id: int,
    me_id: int,
) -> Attachment | None:
    att = await session.get(Attachment, attachment_id)
    if att is None:
        return None
    if me_id not in (att.sender_id, att.recipient_id):
        return None
    return att


async def decrypt(
    session: AsyncSession,
    attachment: Attachment,
) -> tuple[bytes, bool]:
    """Возвращает (plaintext, signature_valid)."""
    sender = await user_service.get_by_id(session, attachment.sender_id)
    if sender is None:
        raise AttachmentError("sender not found")

    valid = await provider.verify(
        attachment.encrypted_data + attachment.nonce,
        attachment.signature,
        sender.public_key,
    )
    key = await conversation_key(attachment.sender_id, attachment.recipient_id)
    plaintext = await provider.decrypt(attachment.encrypted_data, key, attachment.nonce)
    return plaintext, valid
