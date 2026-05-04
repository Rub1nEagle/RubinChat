# RubinChat

Учебный прототип полностью асинхронного защищённого мессенджера, построенный
вокруг **самостоятельных реализаций криптографических алгоритмов ГОСТ**.

| Стандарт | Модуль | Назначение |
| --- | --- | --- |
| ГОСТ 34.11-2012 («Стрибог») | [`backend/app/crypto/gost3411/`](backend/app/crypto/gost3411/) | Хеш 256/512 бит |
| ГОСТ 28147-89 (S-боксы Magma) | [`backend/app/crypto/gost28147/`](backend/app/crypto/gost28147/) | Блочный шифр + режим CTR |
| ГОСТ 34.10-2012 | [`backend/app/crypto/gost3410/`](backend/app/crypto/gost3410/) | ЭЦП на ЭК `paramSetA` |

**Стек.** FastAPI + SQLAlchemy 2 + asyncpg + Alembic на бэкенде,
**Svelte 4 + Vite + Tailwind CSS** на фронтенде, Postgres под капотом.
Всё запускается одной командой через Docker Compose.

> **Только для учебных целей.** Код не защищён от атак по времени, не
> проходил аудит и не пригоден для защиты реальных данных.

---

## Быстрый старт (Docker)

```bash
cp .env.example .env
docker-compose up --build
```

Multi-stage Docker-сборка сначала компилирует фронтенд через Vite,
затем кладёт получившийся `dist/` в backend-контейнер. После старта:

* http://localhost:8000/         — вход
* http://localhost:8000/register — регистрация
* http://localhost:8000/chat     — чат (после входа)
* http://localhost:8000/docs     — обозреватель OpenAPI

Контейнер бэкенда автоматически выполняет `alembic upgrade head` перед
тем, как начать обслуживать запросы. Если вы ранее запускали другой
проект на Postgres 15, удалите старый том командой `docker-compose down -v`.

---

## Локальная разработка

Фронт и бэк удобно запускать раздельно — Vite даёт hot-reload, FastAPI
работает с `--reload`.

**Бэкенд** (один раз поднять Postgres):

```bash
docker-compose up -d db

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL=postgresql+asyncpg://messenger:messenger@localhost:5432/messenger
alembic upgrade head
uvicorn app.main:app --reload     # → http://localhost:8000
```

**Фронтенд** в отдельном терминале:

```bash
cd frontend
npm install
npm run dev                       # → http://localhost:5173
```

Vite-конфиг проксирует `/api` и `/ws` на `http://localhost:8000`, так
что разработка ничем не отличается от работы внутри контейнера.

Перед коммитом — `npm run build`, чтобы убедиться, что прод-сборка
проходит чисто.

---

## Структура проекта

```
RubinChat/
├── backend/                FastAPI + SQLAlchemy 2 (async)
│   ├── app/
│   │   ├── api/routes/     auth / users / messages / crypto-хелперы
│   │   ├── services/       бизнес-логика (auth, message, user, attachment)
│   │   ├── crypto/         реализации ГОСТ + общий conversation-key + async-фасад
│   │   │   ├── gost3411/      Стрибог с T-таблицами + self-test
│   │   │   ├── gost28147/     блочный шифр + CTR (заинлайненный Feistel)
│   │   │   ├── gost3410/      ЭЦП на ЭК (paramSetA)
│   │   │   ├── conversation.py   общий ключ беседы из sorted user_id
│   │   │   └── provider.py    единая точка вызова из сервисов
│   │   ├── models/         User / Message / Attachment
│   │   ├── schemas/        модели Pydantic
│   │   ├── core/           настройки, JWT, bcrypt
│   │   ├── database/       async-движок и фабрика сессий
│   │   ├── websocket/      менеджер соединений и эндпоинт
│   │   └── main.py         фабрика приложения FastAPI + SPA fallback
│   ├── alembic/            асинхронные миграции (0001..0007)
│   ├── requirements.txt
│   └── Dockerfile          multi-stage: Node + Python
├── frontend/               Svelte 4 + Vite + Tailwind CSS, рубиновая палитра
│   ├── src/
│   │   ├── routes/         Login / Register / Chat
│   │   ├── components/     Avatar, ContactList, MessageList/Bubble/Menu,
│   │   │                   Composer, AttachmentImage, SendingAttachments,
│   │   │                   PasswordInput, ConfirmDialog, ChatHeader,
│   │   │                   ProfileModal, MessageInfoModal, AuthLayout
│   │   ├── lib/            api / ws / stores / router / format / image
│   │   ├── App.svelte
│   │   ├── main.js         ранняя установка темы + --app-height (mobile)
│   │   └── app.css         Tailwind + рубиновые токены, темы dark/light
│   ├── index.html
│   ├── tailwind.config.js
│   ├── vite.config.js
│   └── package.json
├── docs/                   полная документация проекта
├── docker-compose.yml      backend + Postgres
└── .env.example
```

## Что внутри прототипа

* Регистрация / логин / смена пароля / удаление аккаунта.
* Профиль с display_name, био, аватаркой, last_seen, статусом
  «в сети».
* Контакты с поиском по всей базе пользователей; в основном списке —
  только активные переписки.
* Текстовые сообщения с шифрованием ГОСТ 28147 + ЭЦП ГОСТ 34.10.
* **Картинки** — сжимаются в браузере, шифруются и подписываются на
  сервере по той же схеме; передаются по `attachment_id`.
* **Бесконечная подгрузка** старых сообщений при скролле вверх через
  курсор `before_id`.
* **Совместный safety-number** (как в Signal): хеш Стрибог-256 от
  отсортированных pubkey'ев — защита от подмены ключей в профиле.
* Редактирование, удаление, статус «прочитано» через WebSocket-события
  `update` / `delete` / `read`.
* Тёмная и светлая темы с CSS-переменными.

---

## Документация

Полная документация лежит в каталоге [`docs/`](docs/). Начните с
оглавления и переходите к нужному разделу:

| Документ | О чём |
| --- | --- |
| [docs/index.md](docs/index.md) | Оглавление документации |
| [docs/architecture.md](docs/architecture.md) | Слои, потоки запросов, дизайн |
| [docs/crypto.md](docs/crypto.md) | Внутреннее устройство ГОСТ 34.11 / 28147 / 34.10 |
| [docs/api.md](docs/api.md) | REST-эндпоинты с примерами `curl` |
| [docs/websocket.md](docs/websocket.md) | Протокол сообщений WebSocket |
| [docs/database.md](docs/database.md) | Схема БД, миграции, anti-replay |
| [docs/frontend.md](docs/frontend.md) | Svelte-приложение, Tailwind, анимации |
| [docs/security.md](docs/security.md) | Модель угроз, что **не** защищено |
| [docs/deployment.md](docs/deployment.md) | Docker, переменные окружения, multi-stage |
| [docs/development.md](docs/development.md) | Как развивать / мигрировать / тестировать |

---

## Лицензия и дисклеймер

Это курсовой прототип. Не используйте его для защиты чего-либо реально
ценного. См. [docs/security.md](docs/security.md) — там перечислены все
учебные упрощения и их последствия.
