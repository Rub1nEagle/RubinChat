# WebSocket

WebSocket-эндпоинт нужен для двустороннего общения в реальном времени:
сервер пушит новые сообщения по мере их прихода, а клиент при желании
может слать через тот же сокет, не делая отдельный POST.

Адрес:

```
ws://<host>:8000/ws?token=<JWT>
```

Токен передаётся параметром строки запроса — стандартного механизма
Authorization-заголовка для WebSocket в браузерах нет.

## Жизненный цикл

```
Client                         Server
  │  WS handshake (?token=...) │
  ├──────────────────────────►│
  │                            ├─ декодирует JWT
  │                            ├─ если OK — accept; иначе close 1008
  │                            └─ регистрирует сокет в ConnectionManager
  │                            │
  │                            │  ... жизнь сокета ...
  │  {type:"send", payload:..} │
  ├──────────────────────────►│
  │                            ├─ валидирует MessageCreate
  │                            ├─ проверяет подпись и nonce
  │                            ├─ INSERT в БД
  │                            ├─ {"type":"ack", message:...}
  │◄──────────────────────────┤
  │                            │
  │                            │  message получателю:
  │                            ├─ {"type":"delivery", message:...}
  │◄──────────────────────────┤  (на сокете получателя)
  │                            │
  │                            │  при ошибке валидации/подписи:
  │  {"type":"error", error:..}│
  │◄──────────────────────────┤
```

При закрытии вкладки или потере связи сервер удалит сокет из
`ConnectionManager` в блоке `finally`. Если это было **последнее**
активное соединение пользователя, в БД обновляется `users.last_seen_at`,
чтобы у собеседников показалось «был N минут назад».

## Конверт сообщения

Часть сообщений валидируется Pydantic-схемой `MessageWS` (всё, что
связано с самими сообщениями); часть — эфемерные индикаторы — идёт
свободным JSON-объектом, чтобы не разбухать схема ради двух полей.

Схема `MessageWS`:

```ts
type MessageWS = {
    type: "send" | "ack" | "delivery" | "update" | "delete" | "read" | "error";
    message?: MessageOut;   // у ack / delivery / update
    message_id?: number;    // у delete
    peer_id?: number;       // у delete (sender_id) и read (id прочитавшего)
    error?: string;         // у error
};
```

Эфемерные обёртки:

```ts
type Typing = {
    type: "typing";
    peer_id: number;        // у клиент→сервер — куда печатают, у сервер→клиент — кто печатает
    kind: "text" | "image"; // что именно: текст или вложение
};

type Presence = {
    type: "presence";
    user_id: number;
    is_online: boolean;
    last_seen_at: string | null;  // ISO; null, если пользователь только что зашёл
};
```

`MessageOut` совпадает по форме с REST-эндпоинтом
[`GET /api/messages/`](api.md#сообщения).

### Клиент → Сервер

Клиент шлёт два типа кадров:

* **`type: "send"`** — обычная отправка сообщения:

  ```json
  {
    "type": "send",
    "payload": {
      "recipient_id": 2,
      "encrypted_payload_hex": "...",
      "nonce_hex": "...",
      "signature_hex": "...",
      "attachment_id": 42
    }
  }
  ```

  `payload` — это в точности `MessageCreate` (тот же, что у POST
  `/api/messages/`); `attachment_id` опционален.

* **`type: "typing"`** — индикатор «печатает / отправляет вложение».
  Не персистится, не валидирует подпись, отправляется второй стороне
  только если та сейчас в онлайне.

  ```json
  { "type": "typing", "peer_id": 2, "kind": "text" }
  ```

  Клиент сам дросселирует «typing» (не чаще раза в 2.5 с), чтобы не
  спамить WS на каждый нажатый символ.

Любой другой `type` от клиента приводит к ответу
`{"type":"error","error":"unsupported message type"}`.

### Сервер → Клиент

| `type` | Когда | Поля |
| --- | --- | --- |
| `ack` | После успешного `send` от того же клиента | `message` |
| `delivery` | Когда другому клиенту пришло сообщение | `message` |
| `update` | После `PATCH /api/messages/{id}` (рассылается обеим сторонам) | `message` |
| `delete` | После `DELETE /api/messages/{id}` (рассылается обеим сторонам) | `message_id`, `peer_id = sender_id` |
| `read` | Когда собеседник пометил все наши сообщения прочитанными | `peer_id` = id того, кто прочитал |
| `typing` | Собеседник набирает текст или отправляет вложение | `peer_id` = id того, кто печатает; `kind` = `"text"` или `"image"` |
| `presence` | Один из пользователей зашёл / вышел | `user_id`, `is_online`, `last_seen_at` (ISO или `null`) |
| `error` | Невалидный конверт, плохая подпись, replay-nonce | `error` |

`update` / `delete` / `read` приходят и через WS-канал, и могут быть
получены, даже если их вызвал REST-запрос соседней вкладки того же
пользователя.

`presence` рассылается всем подключённым пользователям, кроме самого
виновника события — этого хватает, чтобы зелёная точка / «был N минут
назад» обновлялись у собеседников без перезагрузки страницы. Снимок
`is_online` в `UserProfile` приходит из того же `ConnectionManager`,
который рассылает `presence`.

## Реализация на сервере

* [`backend/app/websocket/router.py`](../backend/app/websocket/router.py) —
  принимает соединение, читает по одному JSON-сообщению, передаёт в
  сервис `message`, шлёт ack/error. На разрыве — `manager.disconnect`,
  и если сокет был последним — `user_service.touch_last_seen`.
* [`backend/app/websocket/manager.py`](../backend/app/websocket/manager.py) —
  `ConnectionManager`: словарь `dict[user_id, set[WebSocket]]` под
  `asyncio.Lock`, рассылка через `asyncio.gather`. Один пользователь
  может держать несколько вкладок — все они получат `delivery` /
  `update` / `delete` / `read`.

## Реализация на клиенте

См. [`frontend/src/lib/ws.js`](../frontend/src/lib/ws.js):

* при загрузке `Chat.svelte` вызывается `ws.connect()` — открывается
  `WebSocket` с токеном из стора `session`;
* `addListener(fn)` подписывает обработчик; `Chat.svelte → handleWs`
  обновляет соответствующие состояния (массив сообщений, превью в
  левой панели, статус прочтения);
* при `close` запускается реконнект через 2 секунды;
* отправка через `ws.send({type:"send", payload})`. Если сокет закрыт
  (возвращает `false`) — фронт делает обычный `POST /api/messages/` и
  сам подмешивает ответ в стор.

## Что протокол **не** делает

* Не сжимает.
* Не дробит длинные сообщения — лимит длины задаётся в Pydantic-схеме
  `MessageCreate` и проверяется до записи.
* Не транспортирует вложения по WS — картинка/файл сначала загружается
  через `POST /api/messages/upload` (получаем `attachment_id`), и
  только потом WS-`send` ссылается на этот id.
* Не реализует heartbeat: разрыв детектится самим WebSocket-уровнем, и
  клиент пытается переподключиться.
* Не реализует offline-очередь: пока пользователь не подключён,
  `typing` и `presence`-события до него просто не доезжают.
