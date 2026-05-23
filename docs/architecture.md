# Архитектура

RubinChat разбит на тонкие, чётко выделенные слои. Каждый слой общается
только с тем, что находится непосредственно ниже; благодаря этому
криптография не «протекает» в роуты, а БД — в HTTP-обработчики.

```
┌────────────────────────────────────────────────────────────────────┐
│  Браузер (frontend/*.html, *.js)                                   │
│   • fetch для REST, WebSocket для живой доставки                   │
│   • JWT + private_key_hex в localStorage                           │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ HTTP / WS
┌──────────────────────────────▼─────────────────────────────────────┐
│  Слой роутов FastAPI (backend/app/api/)                            │
│   • схемы запроса/ответа (Pydantic)                                │
│   • JWT-зависимость, маппинг ошибок                                │
│   • не вызывает крипто напрямую                                    │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
┌──────────────────────────────▼─────────────────────────────────────┐
│  Слой сервисов (backend/app/services/)                             │
│   • auth / message / user                                          │
│   • async-функции поверх AsyncSession                              │
│   • единственное место, где вызывается CryptoProvider              │
└─────────────────┬────────────────────────────┬─────────────────────┘
                  │                            │
                  ▼                            ▼
   ┌──────────────────────────┐   ┌──────────────────────────────────┐
   │  CryptoProvider (async)  │   │  SQLAlchemy 2 / asyncpg          │
   │  backend/app/crypto/     │   │  backend/app/database/           │
   │  • generate_keypair      │   │  • async_sessionmaker            │
   │  • sign / verify         │   │  • Postgres                      │
   │  • encrypt / decrypt     │   └──────────────────────────────────┘
   │  • hash                  │
   └────────────┬─────────────┘
                │ asyncio.to_thread
                ▼
   ┌──────────────────────────────┐
   │  Реализации ГОСТ             │
   │  • gost3411/streebog.py      │
   │  • gost28147/{cipher,ctr}.py │
   │  • gost3410/{ec,signature}.py│
   └──────────────────────────────┘
```

## Зачем такие границы

* **Слой роутов не импортирует `crypto/` напрямую.** Роуты только
  валидируют формы запроса и кидают HTTP-ошибки. Логика — слоем ниже.
  Это позволяет заменить крипто-бэкенд или добавить новый транспорт
  (например, gRPC) не трогая алгоритмы.
* **Слой сервисов написан в «синхронном» стиле async** (`async def`,
  который ждёт сессию и провайдера). Здесь живут бизнес-правила:
  регистрация, проверка подписи, защита от replay, выборки переписки.
* **`CryptoProvider`** — *асинхронный фасад*. Внутри ГОСТ-алгоритмы это
  CPU-bound чистый Python, поэтому вызовы оборачиваются в
  `asyncio.to_thread`, чтобы не блокировать event loop. Это
  единственный шов между «обычным» кодом и крипто.
* **Модули алгоритмов** ничего не знают про FastAPI, async и БД. Это
  чистые функции над `bytes` / `int`, импортируемые из юнит-теста или
  из REPL без какой-либо настройки.

## Поток запроса — отправка сообщения

```
1.  Браузер  ─────POST /api/crypto/seal──────►  routes/crypto.py
                                                  └─► CryptoProvider.encrypt
                                                  └─► CryptoProvider.sign
2.  Браузер  ─────POST /api/messages/────────►  routes/messages.py
                                                  └─► services.message.store_message
                                                       ├─ проверка ГОСТ 34.10-подписи
                                                       ├─ проверка nonce в anti-replay
                                                       └─ INSERT строки
3.  Сервер   ─────WebSocket "delivery" ───────► браузеру получателя
4.  Браузер  ─────POST /api/crypto/unseal────►  routes/crypto.py
                                                  └─► CryptoProvider.decrypt + verify
```

Шаг 1 — чистая трансформация: эндпоинт `seal` не пишет в БД. Шаг 2 —
единственная запись, и в строке хранятся **только** зашифрованный
payload, подпись и nonce. Шаг 4 происходит и у получателя, и у
отправителя (отправитель тоже видит свой текст в открытом виде, так как
ключ переписки общий для обеих сторон).

При первом открытии чата клиент шлёт **`/api/crypto/unseal-batch`** на
последние 20 сообщений одной пачкой (внутри запроса сервер кеширует
публичные ключи и conversation-key), потом фоном расшифровывает
оставшийся хвост батчами по 30. При скролле вверх запрашивается ещё
один пакет старых сообщений через курсор `before_id` — и снова
unseal-batch.

## Поток запроса — отправка вложения

Под «вложением» понимается и картинка, и произвольный файл — отличие
только в политике валидации MIME и в заголовке `Content-Disposition`
при отдаче.

```
1. Браузер: для kind=image — image.js ужимает картинку до JPEG-85 / 2000 px.
            Для kind=file — берём байты как есть.
2. Браузер  ─POST /api/messages/upload (multipart, XHR + onProgress)─►
                                          routes/messages.upload_attachment
                                            ├─ kind=image: whitelist MIME
                                            ├─ kind=file:  blacklist MIME + сохраняет original_filename
                                            └─► services.attachment.create_encrypted
                                                 ├─ conversation_key()
                                                 ├─ provider.encrypt
                                                 ├─ provider.sign
                                                 └─ INSERT в attachments
3. Браузер  ─POST /api/messages/ {attachment_id}─►  обычный send-flow
                                                       └─ INSERT в messages
                                                       └─ WS-доставка
4. Получатель ─GET /api/messages/attachment/{id}──►  routes/messages.get_attachment
                                                       └─► services.attachment.decrypt
                                                            ├─ provider.verify
                                                            └─ provider.decrypt
                                                       Response с Content-Type=...
                                                       X-Signature-Valid: 0|1
                                                       X-Content-Type-Options: nosniff
                                                       Content-Disposition: inline  (image/*)
                                                                            | attachment; filename*=UTF-8''…
```

Вложение **никогда** не идёт по WebSocket. Сообщение и `attachment_id`
ссылочные.

## Модель параллелизма

* Стек целиком асинхронный. Существует ровно один синхронный «выход»:
  `bcrypt` и ГОСТ-примитивы оборачиваются в `asyncio.to_thread`.
* `ConnectionManager` хранит in-memory словарь
  `dict[user_id, set[WebSocket]]` под `asyncio.Lock`, рассылка
  параллельная через `asyncio.gather`. Дополнительно отслеживает
  «онлайн»: `is_online(user_id)` и обновляет `users.last_seen_at` при
  закрытии **последнего** сокета пользователя. Этого достаточно для
  одно-процессного учебного прототипа, но не масштабируется на
  несколько воркеров. В продакшене это заменили бы на pub/sub (Redis
  Streams и т. п.).

## Конфигурация

Настройки лежат в [`backend/app/core/config.py`](../backend/app/core/config.py).
Всё читается из переменных окружения через `pydantic-settings` —
строки подключения и секреты в коде не зашиты.

## Где чего точно нет

| Что | НЕТ в | Лежит в |
| --- | --- | --- |
| Детали крипто | `api/routes/messages.py` | `crypto/` + `services/message.py` |
| HTTP-формы | `services/` | `schemas/*` + `api/routes/*` |
| Подключения к БД | `services/` | `database/session.py` |
| Декодирование JWT | в теле роутов | `core/security.py` + `api/deps.py` |
