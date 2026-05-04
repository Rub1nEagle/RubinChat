"""In-process WebSocket connection registry.

For a single-process academic prototype this is sufficient. Multi-worker
deployments would need a pub/sub backbone (Redis, NATS, etc.).
"""
from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket

from ..schemas.message import MessageOut, MessageWS


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[user_id].add(websocket)

    async def disconnect(self, user_id: int, websocket: WebSocket) -> bool:
        """Удалить сокет пользователя.

        Возвращает True, если это было его последнее активное соединение
        (т.е. пользователь только что ушёл в офлайн).
        """
        async with self._lock:
            sockets = self._connections.get(user_id)
            if not sockets:
                return False
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(user_id, None)
                return True
            return False

    def is_online(self, user_id: int) -> bool:
        return bool(self._connections.get(user_id))

    def online_user_ids(self) -> set[int]:
        return set(self._connections.keys())

    async def _send(self, user_ids: list[int], envelope: dict) -> None:
        async with self._lock:
            sockets: list[WebSocket] = []
            for uid in user_ids:
                sockets.extend(self._connections.get(uid, set()))
        if not sockets:
            return
        await asyncio.gather(
            *(self._safe_send(ws, envelope) for ws in sockets),
            return_exceptions=True,
        )

    async def deliver(self, user_id: int, message: MessageOut) -> None:
        envelope = MessageWS(type="delivery", message=message).model_dump(mode="json")
        await self._send([user_id], envelope)

    async def broadcast_update(self, message: MessageOut) -> None:
        """Сообщение отредактировано — обновить у обеих сторон."""
        envelope = MessageWS(type="update", message=message).model_dump(mode="json")
        await self._send([message.sender_id, message.recipient_id], envelope)

    async def broadcast_delete(
        self, *, message_id: int, sender_id: int, recipient_id: int
    ) -> None:
        envelope = MessageWS(
            type="delete", message_id=message_id, peer_id=sender_id
        ).model_dump(mode="json")
        await self._send([sender_id, recipient_id], envelope)

    async def broadcast_read(self, *, reader_id: int, peer_id: int) -> None:
        """Получатель прочитал переписку — известим отправителя, чтобы его
        UI мог обновить статус."""
        envelope = MessageWS(
            type="read", peer_id=reader_id
        ).model_dump(mode="json")
        await self._send([peer_id], envelope)

    async def broadcast_presence(
        self, *, user_id: int, is_online: bool, last_seen_at: str | None = None
    ) -> None:
        """Известить ВСЕХ остальных подключённых пользователей о смене
        статуса в сети. Полезно, чтобы зелёная точка / lastSeen у
        собеседника обновлялись без перезагрузки страницы.

        ``last_seen_at`` — ISO-строка момента ухода в офлайн (или None,
        когда пользователь только что зашёл).
        """
        async with self._lock:
            sockets: list[WebSocket] = []
            for uid, conns in self._connections.items():
                if uid == user_id:
                    continue
                sockets.extend(conns)
        if not sockets:
            return
        envelope = {
            "type": "presence",
            "user_id": user_id,
            "is_online": is_online,
            "last_seen_at": last_seen_at,
        }
        await asyncio.gather(
            *(self._safe_send(ws, envelope) for ws in sockets),
            return_exceptions=True,
        )

    async def forward_typing(self, *, from_id: int, to_id: int, kind: str) -> None:
        """Перебросить эфемерный typing-сигнал второй стороне.

        Не персистится; выкидывается, если адресат офлайн. Поле `peer_id`
        в обёртке — это id того, кто печатает, чтобы клиент мог сопоставить.
        """
        if not self.is_online(to_id):
            return
        envelope = {
            "type": "typing",
            "peer_id": from_id,
            "kind": kind if kind in ("text", "image") else "text",
        }
        await self._send([to_id], envelope)

    @staticmethod
    async def _safe_send(ws: WebSocket, payload: dict) -> None:
        try:
            await ws.send_json(payload)
        except Exception:
            pass


manager = ConnectionManager()
