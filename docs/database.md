# База данных

Хранилище — PostgreSQL. SQLAlchemy 2 в асинхронном режиме на драйвере
`asyncpg`. Миграции — через Alembic (тоже в асинхронном `env.py`).

## Подключение

Строка подключения берётся из переменной окружения `DATABASE_URL`.
По умолчанию (см. [`docker-compose.yml`](../docker-compose.yml)):

```
postgresql+asyncpg://messenger:messenger@db:5432/messenger
```

Async-движок и `async_sessionmaker` создаются один раз в
[`backend/app/database/session.py`](../backend/app/database/session.py).
FastAPI получает сессию через зависимость `get_db()`, которая входит и
выходит как `async with`.

## Схема

Три таблицы. Базовый класс — `DeclarativeBase`
([`database/base.py`](../backend/app/database/base.py)).

### `users`

| Колонка | Тип | Описание |
| --- | --- | --- |
| `id` | `INTEGER PK` | автоинкремент |
| `username` | `VARCHAR(64) UNIQUE` | имя для входа |
| `password_hash` | `VARCHAR(128)` | bcrypt-хеш |
| `public_key` | `BYTEA(64)` | публичный ключ ГОСТ 34.10 (`x \|\| y`) |
| `encrypted_private_key` | `BYTEA(40)` | `nonce(8) \|\| GOST-28147-CTR(priv, key=Streebog-256(password))` |
| `display_name` | `VARCHAR(120) NULL` | отображаемое имя; пусто → используется `username` |
| `bio` | `VARCHAR(500) NULL` | свободный текст профиля |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT now()` |
| `last_seen_at` | `TIMESTAMPTZ NULL` | момент последнего разрыва WebSocket; пока пользователь онлайн — не обновляется |
| `avatar_data` | `BYTEA NULL` | сырое изображение (jpeg/png/webp), до 2 МБ |
| `avatar_mime` | `VARCHAR(64) NULL` | MIME-тип аватара |
| `avatar_version` | `INTEGER NOT NULL DEFAULT 0` | инкрементируется при каждом обновлении/удалении — для cache-busting на клиенте |

Аватары хранятся **в открытом виде**: они публичны (видны всем
контактам) и общего ключа для них нет. Это сознательный
учебный компромисс — см. [`security.md`](security.md).

Индексы: `ix_users_username` (уникальный, для быстрого `WHERE username=...`).

### `messages`

| Колонка | Тип | Описание |
| --- | --- | --- |
| `id` | `INTEGER PK` | автоинкремент; используется как курсор пагинации (`before_id`) |
| `sender_id` | `FK users.id ON DELETE CASCADE` | отправитель |
| `recipient_id` | `FK users.id ON DELETE CASCADE` | получатель |
| `encrypted_payload` | `BYTEA` | шифртекст ГОСТ 28147 (CTR) |
| `nonce` | `BYTEA(8)` | nonce CTR |
| `signature` | `BYTEA(64)` | подпись `(payload \|\| nonce)` ГОСТ 34.10 |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT now()` |
| `edited_at` | `TIMESTAMPTZ NULL` | момент последнего `PATCH /api/messages/{id}` |
| `read_at` | `TIMESTAMPTZ NULL` | момент чтения получателем (`POST /api/messages/read`) |
| `attachment_id` | `FK attachments.id ON DELETE SET NULL` | опциональная картинка |

Индексы:
* `ix_messages_recipient_id_created_at` — `(recipient_id, created_at DESC)`,
  ускоряет «последние сообщения для получателя».
* `ix_messages_recipient_unread` — частичный индекс
  `(recipient_id, sender_id) WHERE read_at IS NULL`,
  для подсчёта непрочитанных.
* `ix_messages_attachment_id` — для каскадного `SET NULL`.

### `attachments`

Зашифрованные картинки. Содержимое запечатано тем же conversation-key,
что и текстовые сообщения (см. [`crypto.md`](crypto.md)).

| Колонка | Тип | Описание |
| --- | --- | --- |
| `id` | `INTEGER PK` | автоинкремент |
| `sender_id` | `FK users.id ON DELETE CASCADE` | отправитель |
| `recipient_id` | `FK users.id ON DELETE CASCADE` | получатель |
| `mime_type` | `VARCHAR(64)` | один из allow-list: jpeg/png/webp/gif |
| `size_bytes` | `INTEGER` | размер исходного открытого файла |
| `nonce` | `BYTEA(8)` | nonce CTR |
| `encrypted_data` | `BYTEA` | шифртекст |
| `signature` | `BYTEA(64)` | подпись `(encrypted_data \|\| nonce)` |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT now()` |

Индексы: `ix_attachments_sender_id`, `ix_attachments_recipient_id`.

«Orphan-вложения» (загруженные, но не прилинкованные к сообщению)
живут в БД до тех пор, пока создавший их пользователь не удалится —
TTL-cleanup'а в учебном прототипе нет.

### Что НЕ хранит сервер

* открытый текст сообщений;
* сессионные ключи беседы (выводятся детерминированно «на лету»);
* nonce за пределами anti-replay окна;
* пароль (только bcrypt-хеш);
* приватный ключ в открытом виде (только зашифрованный паролем).

## Защита от replay

`services/message.py` ведёт небольшой in-process кеш `_NonceCache`:
`OrderedDict[bytes, float]`. Каждый принятый nonce запоминается с меткой
времени. Перед сохранением сервер:

1. вычищает записи старше `nonce_window_seconds` (по умолчанию 300 с);
2. отвергает пакет, если такой nonce уже виден.

Кеш живёт только в памяти процесса. После рестарта сервер пропустит
повтор, но в учебных целях это допустимо. Для продакшена кеш заменили
бы на Redis.

## Миграции

### Структура каталога

```
backend/
├── alembic.ini
└── alembic/
    ├── env.py
    ├── script.py.mako
    └── versions/
        ├── 0001_initial.py
        ├── 0002_message_state.py
        ├── 0003_user_profile.py
        ├── 0004_attachments.py
        ├── 0005_user_avatar.py
        ├── 0006_drop_user_avatar.py
        └── 0007_restore_user_avatar.py
```

### env.py

Особенности:

* DSN читается из `pydantic-settings` (`get_settings().database_url`),
  если не задан в `alembic.ini` — это значит, что миграции и приложение
  всегда смотрят на одну и ту же БД.
* `async_engine_from_config` + `connection.run_sync(do_run_migrations)`
  даёт честно асинхронные миграции.
* Импортируется `app.models`, чтобы все модели зарегистрировались в
  `Base.metadata` ещё до запуска миграции.

### Команды

Внутри контейнера или локально (`cd backend`):

```bash
# применить все миграции
alembic upgrade head

# откатить всё
alembic downgrade base

# откатить на одну ревизию
alembic downgrade -1

# создать новую ревизию по diff моделей
alembic revision --autogenerate -m "сообщение"

# создать пустую ревизию
alembic revision -m "сообщение"
```

Через Compose это удобно делать так:

```bash
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend alembic revision --autogenerate -m "..."
```

В Docker-образе `alembic upgrade head` запускается автоматически при
старте контейнера (см. CMD в `backend/Dockerfile`).

### История ревизий

| Ревизия | Что делает |
| --- | --- |
| `0001_initial` | создаёт `users`, `messages` и базовые индексы/FK |
| `0002_message_state` | добавляет `messages.edited_at`, `messages.read_at` и частичный индекс `ix_messages_recipient_unread` |
| `0003_user_profile` | добавляет `users.display_name`, `users.bio`, `users.last_seen_at` |
| `0004_attachments` | создаёт таблицу `attachments` + колонку `messages.attachment_id` |
| `0005_user_avatar` | добавляет `users.avatar_data`, `avatar_mime`, `avatar_version` |
| `0006_drop_user_avatar` | (исторический артефакт) дроп аватарных колонок — феномен «фича была откачена и вернулась» |
| `0007_restore_user_avatar` | возвращает аватарные колонки через `ADD COLUMN IF NOT EXISTS`; идемпотентен на любом контуре |

## Сессии

`async_sessionmaker(expire_on_commit=False)` — это значит, что
SQLAlchemy после `commit()` не сбрасывает атрибуты ORM-объектов, и их
можно безопасно сериализовать в Pydantic-схему сразу после записи.

Сервисы на каждый запрос получают свою сессию, что соответствует
шаблону «request-scoped session». WebSocket-роут открывает сессию
вручную (`async with async_session_maker()`), потому что зависимости
FastAPI там работать не будут.

Жадная загрузка вложений: чтобы при сериализации `MessageOut` не
было N+1 SELECT'ов, `services/message.py` вызывает SQLAlchemy с
`selectinload(Message.attachment)` — один дополнительный запрос
на партию сообщений вместо запроса на каждое.
