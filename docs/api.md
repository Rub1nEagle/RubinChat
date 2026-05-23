# REST API

Все REST-эндпоинты лежат под префиксом `/api`. Запросы и ответы — в
JSON. Аутентификация по Bearer-JWT, токен выдаётся при регистрации и
логине. Документация в формате OpenAPI доступна по
http://localhost:8000/docs.

В примерах ниже предполагается:

```bash
TOKEN="<значение access_token>"
```

## Конвенции

* Все байтовые значения передаются как hex-строки в нижнем регистре.
* Длины hex-строк фиксированы:

  | Что | Длина hex |
  | --- | --- |
  | Приватный ключ ГОСТ 34.10 | 64 |
  | Публичный ключ ГОСТ 34.10 (`x \|\| y`) | 128 |
  | Подпись (`r \|\| s`) | 128 |
  | Nonce ГОСТ 28147 (CTR) | 16 |
  | Хеш Стрибог-256 | 64 |
* Ошибки возвращаются как `{"detail": "..."}` и имеют разумный HTTP-код:
  `400` — невалидные данные, `401` — нет/плохой токен, `403` — не
  участник переписки, `404` — сущность не найдена, `413` — слишком
  большой файл.

---

## Аутентификация

### `POST /api/auth/register`

Создаёт пользователя, генерирует пару ключей ГОСТ 34.10, шифрует
приватный ключ паролем (`Streebog-256(password) → GOST 28147 CTR`) и
возвращает токен + расшифрованный приватный ключ для текущей сессии.

**Тело запроса**

```json
{ "username": "alice", "password": "correct-horse" }
```

* `username` — 3..64 символа, `[A-Za-z0-9_.-]`.
* `password` — 8..128 символов.

**Ответ** (`201 Created`):

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user_id": 1,
  "username": "alice",
  "private_key_hex": "f3b1...e9"
}
```

### `POST /api/auth/login`

Проверяет пароль (bcrypt), расшифровывает приватный ключ и возвращает
его клиенту той же формой, что у `/register`.

### `POST /api/auth/change-password`

Меняет пароль; перешифровывает приватный ключ новым паролем; возвращает
новый JWT и расшифрованный приватный ключ (старый перестаёт
расшифровываться).

**Тело запроса**

```json
{ "current_password": "old-pass", "new_password": "new-pass" }
```

**Ответ** — той же формы, что у `/register` (новый `access_token` +
`private_key_hex`).

### `POST /api/auth/delete-account`

Удаляет аккаунт текущего пользователя. Каскадно удаляются все его
сообщения и вложения. Требует подтверждения паролем.

**Тело запроса** — `{ "password": "..." }`. **Ответ** — `204 No Content`.

---

## Пользователи

Все эндпоинты ниже требуют `Authorization: Bearer $TOKEN`.

Форма `UserProfile`:

```json
{
  "user_id": 2,
  "username": "bob",
  "display_name": "Bob the Builder",
  "bio": "строитель",
  "public_key_hex": "1234...abcd",
  "created_at": "2026-04-25T12:00:00Z",
  "last_seen_at": "2026-04-30T09:15:42Z",
  "is_online": false,
  "has_avatar": true,
  "avatar_version": 3
}
```

`is_online` вычисляется на лету из `ConnectionManager` (есть ли
открытый WebSocket); `last_seen_at` — момент последнего разрыва.
`avatar_version` инкрементируется при каждой загрузке/удалении
аватара — клиент использует его для cache-busting.

### `GET /api/users/`

Список всех пользователей кроме текущего.

### `GET /api/users/me`

Свой профиль (всегда `is_online: true`).

### `PATCH /api/users/me`

Изменяет редактируемые поля профиля.

**Тело** — `{ "display_name": "...", "bio": "..." }`. Оба поля
опциональны, `null` сбрасывает значение.

### `GET /api/users/{user_id}`

Профиль произвольного пользователя.

### `GET /api/users/{user_id}/public-key`

Совместимый эндпоинт; отдаёт ту же `UserProfile` целиком (исторически
возвращал только `public_key_hex`).

### Аватары

Изображение аватара хранится в открытом виде (он публичен по смыслу —
виден всем контактам). Допустимые форматы: `image/jpeg`, `image/png`,
`image/webp`. Лимит 2 МБ.

* `POST /api/users/me/avatar` — `multipart/form-data` с полем `file`.
  Возвращает обновлённый `UserProfile` (с инкрементированным
  `avatar_version`).
* `DELETE /api/users/me/avatar` — снимает аватар.
* `GET /api/users/{user_id}/avatar` — возвращает байты аватара
  (`Content-Type: image/...`); `404`, если не задан. Браузер не умеет
  слать `Authorization` через `<img src=...>`, поэтому фронт качает
  blob через `fetch` и кеширует `URL.createObjectURL` по
  `(user_id, avatar_version)`.

---

## Крипто-хелперы

Эти эндпоинты — чистые трансформации без записи в БД. Они существуют,
чтобы фронтенд мог пользоваться ГОСТ-примитивами без собственной
реализации в JS. Подробнее про модель — см.
[`security.md`](security.md).

### `POST /api/crypto/seal`

Зашифровать и подписать открытый текст. Сервер выводит ключ беседы
детерминированно из пары `(me, recipient)` через `Streebog-256` (см.
[`backend/app/crypto/conversation.py`](../backend/app/crypto/conversation.py)).

**Тело запроса**

```json
{
  "recipient_id": 2,
  "plaintext": "привет, боб",
  "sender_private_key_hex": "f3b1...e9"
}
```

`plaintext` — 1..8000 символов.

**Ответ**

```json
{
  "encrypted_payload_hex": "...",
  "nonce_hex": "0011223344556677",
  "signature_hex": "<128 hex>"
}
```

### `POST /api/crypto/unseal`

Расшифровать и проверить подпись. Текущий пользователь обязан быть либо
отправителем, либо получателем — иначе `403`.

**Ответ**

```json
{ "plaintext": "привет, боб", "signature_valid": true }
```

Если расшифровка вернула не-UTF-8, поле `plaintext` отдаётся как hex.

### `POST /api/crypto/unseal-batch`

Расшифровка пачки сообщений одним запросом. До 200 элементов в
`items`. Внутри запроса кешируются публичные ключи отправителей и
ключи беседы — заметно быстрее серии вызовов `/unseal` при загрузке
истории.

**Тело запроса**

```json
{
  "items": [
    { "sender_id": 2, "recipient_id": 1, "encrypted_payload_hex": "...",
      "nonce_hex": "...", "signature_hex": "..." }
  ]
}
```

**Ответ** — `{ "results": [ { "plaintext": "...", "signature_valid": true } ] }`.

### `GET /api/crypto/fingerprint/{peer_id}`

Совместный safety-number разговора (как в Signal): хеш Стрибог-256 от
отсортированных hex-строк публичных ключей обеих сторон. Один и тот
же код у Алисы и Боба — если он совпадает голосом / по другому
каналу, MITM нет.

**Ответ** — `{ "fingerprint_hex": "<64 hex>" }`.

---

## Сообщения

Форма `MessageOut`:

```json
{
  "id": 17,
  "sender_id": 1,
  "recipient_id": 2,
  "encrypted_payload_hex": "...",
  "nonce_hex": "...",
  "signature_hex": "...",
  "created_at": "2026-04-25T12:34:56Z",
  "edited_at": null,
  "read_at": null,
  "attachment": null
}
```

Если у сообщения есть вложение, `attachment` имеет вид

```json
{
  "id": 42,
  "mime_type": "image/jpeg",
  "size_bytes": 245678,
  "original_filename": null
}
```

`original_filename` равен `null` у картинок (имя клиенту не нужно — превью
рисуется по `mime_type`) и непустой у произвольных файлов (`kind=file`),
например `"quarterly-report.pdf"`. Имя обрезается до 255 символов.

### `POST /api/messages/`

Сохраняет уже зашифрованный пакет. Сервер делает четыре проверки:

1. nonce 8 байт, подпись 64 байта, encrypted_payload не пустой;
2. nonce не встречался в пределах окна `nonce_window_seconds`
   (по умолчанию 300 с) — защита от replay;
3. подпись `(encrypted_payload || nonce)` валидна для публичного ключа
   отправителя;
4. если задан `attachment_id` — вложение существует и принадлежит паре
   `(sender, recipient)`.

После записи сервер пытается доставить сообщение получателю по
WebSocket, если тот в онлайне.

**Тело запроса**

```json
{
  "recipient_id": 2,
  "encrypted_payload_hex": "...",
  "nonce_hex": "...",
  "signature_hex": "...",
  "attachment_id": 42
}
```

`attachment_id` опционален. Для сообщения «только вложение, без
текста» клиент шлёт seal'ку от строки из одного пробела (Pydantic
требует непустой шифртекст).

**Ответ** — `201 Created`, тело `MessageOut`.

### `GET /api/messages/`

Возвращает **последние** сообщения текущего пользователя в
хронологическом порядке (старые → свежие).

| Параметр | Назначение |
| --- | --- |
| `peer_id` | если указан — только переписка с этим пользователем |
| `limit` | максимум 500, по умолчанию 100 |
| `before_id` | курсор для скролла вверх: вернуть `limit` сообщений со строго меньшим id (более старые относительно курсора) |

Пагинация: фронт делает первичный `limit=200`. Когда пользователь
доскроллил почти до верха ленты, повторно зовёт `before_id =
oldest_message.id`, `limit=100` и подклеивает результат сверху.

```bash
# первый экран — последние 200 сообщений переписки
curl -s "http://localhost:8000/api/messages/?peer_id=2&limit=200" \
    -H "Authorization: Bearer $TOKEN"

# подгрузка ранее
curl -s "http://localhost:8000/api/messages/?peer_id=2&limit=100&before_id=842" \
    -H "Authorization: Bearer $TOKEN"
```

### `PATCH /api/messages/{id}`

Редактировать сообщение. Только отправитель. Шифртекст и подпись
заменяются целиком (клиент перешифровывает заново). После записи
выставляется `edited_at`, и через WebSocket обеим сторонам
рассылается событие `update`.

**Тело** — то же, что в `POST /messages/`, но без `recipient_id` и
`attachment_id`.

### `DELETE /api/messages/{id}`

Удаляет сообщение и каскадно вложение, если было. Только отправитель.
По WebSocket обеим сторонам летит `delete`. Ответ — `204 No Content`.

### `POST /api/messages/read?peer_id={id}`

Помечает все непрочитанные сообщения от `peer_id` к текущему
пользователю как прочитанные. Возвращает `{ "updated": <int> }`. Если
что-то поменялось — отправителю `peer_id` по WS летит событие `read`,
чтобы у него обновились галочки.

### `GET /api/messages/conversations`

Сводка по перепискам для левой панели. Возвращает массив
`ConversationSummary`:

```json
[
  { "peer_id": 2, "last_message": { "..." }, "unread_count": 3 }
]
```

`last_message` — последний `MessageOut` в переписке (может быть
`null`, если переписки ещё не было).

---

## Вложения

Вложения бывают двух видов — картинки и произвольные файлы. И те, и
другие шифруются и подписываются на сервере по той же схеме, что и
текст: GOST 28147-89 в CTR + ГОСТ 34.10 над `(encrypted || nonce)`.
Хранятся в одной таблице `attachments`. Чтобы отправить вложение, клиент:

1. Загружает файл через `POST /api/messages/upload` — получает
   `attachment_id`.
2. Делает обычный `POST /api/messages/` с `attachment_id` (и
   опционально текстом-подписью).

Виды различаются полем `kind` в форме загрузки:

| `kind` | Разрешённые mime | Что хранит |
| --- | --- | --- |
| `image` | белый список `image/jpeg`, `image/png`, `image/webp`, `image/gif` | без `original_filename`; превью рисуется по mime |
| `file` | всё, **кроме** чёрного списка (`text/html`, `application/xhtml+xml`, `application/javascript`, `text/javascript`, `application/x-msdownload`, `application/x-msdos-program`, `application/x-sh`) | сохраняет `original_filename` (до 255 символов) и подставляет его в `Content-Disposition` при отдаче |

Лимит — 5 МБ для обоих видов. На клиенте перед отправкой большие фото
сжимаются до JPEG 85 % / 2000 px по большей стороне (см.
[`frontend/src/lib/image.js`](../frontend/src/lib/image.js)) — это
снижает нагрузку на CPU-bound шифрование на сервере. Файлы (`kind=file`)
уходят как есть.

### `POST /api/messages/upload`

`multipart/form-data` с полями:

* `recipient_id` — `int`
* `sender_private_key_hex` — `str` (32 байта в hex)
* `kind` — `"image"` (по умолчанию) или `"file"`
* `file` — бинарь

Если `Content-Type` у файла не задан (например, curl без `-H` или
редкое расширение) — сервер подставляет `application/octet-stream`,
чтобы валидация не отрезала валидную загрузку. Имя файла
(`file.filename`) сохраняется в `original_filename` **только** для
`kind=file`; у картинок оно игнорируется.

**Ответ** — `AttachmentSummary` (`id`, `mime_type`, `size_bytes`,
`original_filename`). До линковки с сообщением вложение остаётся
«orphan'ом» в БД, на ttl-cleanup не рассчитан.

Пример загрузки файла через curl:

```bash
curl -X POST "http://localhost:8000/api/messages/upload" \
    -H "Authorization: Bearer $TOKEN" \
    -F "recipient_id=2" \
    -F "sender_private_key_hex=$PRIV" \
    -F "kind=file" \
    -F "file=@./quarterly-report.pdf"
```

### `GET /api/messages/attachment/{attachment_id}`

Возвращает расшифрованные байты вложения (`Content-Type` соответствует
mime). Доступно только участникам разговора (sender или recipient).

Заголовки ответа:

| Заголовок | Значение |
| --- | --- |
| `Content-Type` | сохранённый `mime_type` вложения |
| `Cache-Control` | `private, max-age=86400` |
| `X-Signature-Valid` | `1` — подпись валидна, `0` — нет (контент всё равно отдаётся; клиент рисует ⚠) |
| `X-Content-Type-Options` | `nosniff` — запрещает браузеру угадывать тип; иначе старый Edge/IE мог бы интерпретировать blob с HTML-тегами как `text/html` в обход `Content-Disposition` |
| `Content-Disposition` | `inline` для `image/*`; `attachment; filename="…"; filename*=UTF-8''…` для всего остального — RFC 5987 кодировка имени, чтобы кириллица доехала до диалога «Сохранить как» |

Браузер не умеет передавать `Authorization` через `<img src=...>`, так
что фронт качает blob через `fetch` и использует `URL.createObjectURL`
(для картинок — через [`AttachmentImage.svelte`](../frontend/src/components/AttachmentImage.svelte),
для файлов — через [`AttachmentFile.svelte`](../frontend/src/components/AttachmentFile.svelte)).

---

## Прочее

### `GET /health`

Простейший «пинг» для оркестратора:

```json
{ "status": "ok" }
```
