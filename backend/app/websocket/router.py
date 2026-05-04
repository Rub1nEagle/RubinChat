"""WebSocket endpoint for real-time message delivery.

The client opens ``/ws?token=<JWT>``. After authentication the server
keeps the socket and pushes ``MessageWS`` envelopes whenever a new
message lands for that user. The client may also use the same socket
to send messages by posting a JSON ``MessageCreate`` payload with
``type=\"send\"``.
"""
from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from ..api.deps import user_from_token
from ..database.session import async_session_maker
from ..schemas.message import MessageCreate, MessageWS
from ..services import message as message_service
from ..services import user as user_service
from ..services.message import MessageError
from .manager import manager

ws_router = APIRouter()


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)) -> None:
    async with async_session_maker() as session:
        user = await user_from_token(token, session)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Был ли это первый сокет пользователя ДО connect? Если да —
    # после connect он стал онлайн, и надо известить остальных.
    was_offline = not manager.is_online(user.id)
    await manager.connect(user.id, websocket)
    if was_offline:
        await manager.broadcast_presence(
            user_id=user.id, is_online=True, last_seen_at=None
        )
    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type")

            if msg_type == "typing":
                # Эфемерный сигнал — без БД, без подписей.
                peer_id = raw.get("peer_id")
                kind = raw.get("kind", "text")
                if isinstance(peer_id, int) and peer_id != user.id:
                    await manager.forward_typing(
                        from_id=user.id, to_id=peer_id, kind=kind
                    )
                continue

            if msg_type != "send":
                await websocket.send_json(
                    MessageWS(type="error", error="unsupported message type").model_dump(mode="json")
                )
                continue
            try:
                payload = MessageCreate(**raw.get("payload", {}))
            except ValidationError as exc:
                await websocket.send_json(
                    MessageWS(type="error", error=str(exc)).model_dump(mode="json")
                )
                continue

            async with async_session_maker() as session:
                # Re-fetch the user so we always sign-check with the freshest key.
                fresh = await user_from_token(token, session)
                if fresh is None:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return
                try:
                    msg = await message_service.store_message(session, fresh, payload)
                except MessageError as exc:
                    await websocket.send_json(
                        MessageWS(type="error", error=str(exc)).model_dump(mode="json")
                    )
                    continue

            await websocket.send_json(MessageWS(type="ack", message=msg).model_dump(mode="json"))
            await manager.deliver(msg.recipient_id, msg)
    except WebSocketDisconnect:
        pass
    finally:
        was_last = await manager.disconnect(user.id, websocket)
        if was_last:
            last_seen_iso: str | None = None
            try:
                async with async_session_maker() as session:
                    fresh = await user_service.touch_last_seen(session, user.id)
                    if fresh is not None and fresh.last_seen_at is not None:
                        last_seen_iso = fresh.last_seen_at.isoformat()
            except Exception:
                # Не падаем из-за невозможности записать last_seen.
                pass
            # Известим остальных, что пользователь ушёл в офлайн.
            await manager.broadcast_presence(
                user_id=user.id, is_online=False, last_seen_at=last_seen_iso
            )
