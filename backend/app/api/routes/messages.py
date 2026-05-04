from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...database.session import get_db
from ...models import User
from ...schemas.message import (
    AttachmentSummary,
    ConversationSummary,
    MessageCreate,
    MessageEdit,
    MessageOut,
)
from ...services import attachment as attachment_service
from ...services import message as message_service
from ...services.attachment import AttachmentError
from ...services.message import MessageError
from ...websocket.manager import manager
from ..deps import current_user

router = APIRouter()


@router.post("/", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def send_message(
    payload: MessageCreate,
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> MessageOut:
    try:
        msg = await message_service.store_message(session, me, payload)
    except MessageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await manager.deliver(msg.recipient_id, msg)
    return msg


@router.get("/", response_model=list[MessageOut])
async def list_messages(
    peer_id: int | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    before_id: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> list[MessageOut]:
    """``before_id`` — курсор для пагинации скроллом вверх: отдать ``limit``
    сообщений строго старше указанного id. Без курсора — последние N."""
    return await message_service.list_for_user(
        session, me.id, peer_id=peer_id, limit=limit, before_id=before_id
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> list[ConversationSummary]:
    return await message_service.list_conversations(session, me.id)


def _http_from_message_error(exc: MessageError) -> HTTPException:
    text = str(exc)
    if "not found" in text:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=text)
    if "only the sender" in text:
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=text)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=text)


@router.patch("/{message_id}", response_model=MessageOut)
async def edit_message(
    message_id: int,
    payload: MessageEdit,
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> MessageOut:
    try:
        msg = await message_service.edit_message(session, me, message_id, payload)
    except MessageError as exc:
        raise _http_from_message_error(exc) from exc
    await manager.broadcast_update(msg)
    return msg


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: int,
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> Response:
    try:
        snapshot = await message_service.delete_message(session, me, message_id)
    except MessageError as exc:
        raise _http_from_message_error(exc) from exc

    await manager.broadcast_delete(
        message_id=snapshot.id,
        sender_id=snapshot.sender_id,
        recipient_id=snapshot.recipient_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/read", status_code=status.HTTP_200_OK)
async def mark_read(
    peer_id: int = Query(...),
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> dict[str, int]:
    affected = await message_service.mark_conversation_read(session, me.id, peer_id)
    if affected:
        await manager.broadcast_read(reader_id=me.id, peer_id=peer_id)
    return {"updated": affected}


# ─────────────────────── attachments (картинки) ────────────────────────

@router.post("/upload", response_model=AttachmentSummary, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    recipient_id: int = Form(...),
    sender_private_key_hex: str = Form(..., min_length=64, max_length=64),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> AttachmentSummary:
    """Загружает картинку, шифрует и подписывает на стороне сервера.

    Возвращает идентификатор созданного вложения. Чтобы прикрепить
    картинку к сообщению, клиент шлёт обычный POST /messages/ с
    `attachment_id` в теле.
    """
    data = await file.read()
    if len(data) > attachment_service.MAX_BYTES + 1024:
        # запасной щит — основная проверка в сервисе
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="file too large",
        )
    mime = file.content_type or ""
    try:
        att = await attachment_service.create_encrypted(
            session,
            me,
            recipient_id,
            data,
            mime,
            sender_private_key_hex,
        )
    except AttachmentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AttachmentSummary(id=att.id, mime_type=att.mime_type, size_bytes=att.size_bytes)


@router.get("/attachment/{attachment_id}")
async def get_attachment(
    attachment_id: int,
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> Response:
    """Возвращает расшифрованный blob картинки.

    Сервер проверяет подпись; если она невалидна, отдаёт 409 — клиент
    должен показать предупреждение, но контент всё равно может прийти.
    """
    att = await attachment_service.get_for_user(session, attachment_id, me.id)
    if att is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attachment not found")
    try:
        plaintext, valid = await attachment_service.decrypt(session, att)
    except AttachmentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    headers = {
        "Cache-Control": "private, max-age=86400",
        "X-Signature-Valid": "1" if valid else "0",
    }
    return Response(content=plaintext, media_type=att.mime_type, headers=headers)
