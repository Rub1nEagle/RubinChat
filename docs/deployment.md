# Деплой

Прототип запускается одной командой `docker compose up --build` (или
`docker-compose up --build` со старым CLI). Этого хватит и для лекции,
и для локальной разработки.

## Состав стека

В [`docker-compose.yml`](../docker-compose.yml) описаны два сервиса:

| Сервис | Образ | Порт хоста | Назначение |
| --- | --- | --- | --- |
| `db` | `postgres:16-alpine` | `5432` | Postgres с health-check'ом |
| `backend` | сборка из `./backend` | `8000` | FastAPI + миграции на старте |

Том `pgdata` хранит данные Postgres между перезапусками.

`backend` поднимается только после того, как `db` перешла в healthy
(`pg_isready`).

## Dockerfile

[`backend/Dockerfile`](../backend/Dockerfile) — **multi-stage**:

1. **Stage `frontend` (`node:20-alpine`)**
   * `npm install` для каталога `frontend/`;
   * `npm run build` через Vite → `/frontend/dist`.
2. **Stage backend (`python:3.11-slim`)**
   * ставит `gcc` и `libpq-dev` (нужны для `psycopg2`, который тянет
     Alembic в качестве «синхронного» fallback'а);
   * `pip install -r backend/requirements.txt`;
   * копирует `backend/` в `/app`;
   * `COPY --from=frontend /frontend/dist /frontend/dist` — кладёт
     собранную статику рядом с приложением;
   * `CMD: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`.

Миграции применяются автоматически перед запуском Uvicorn — отдельный
шаг не нужен.

Контекст сборки в `docker-compose.yml` — корень репозитория, чтобы
Dockerfile видел и `backend/`, и `frontend/`:

```yaml
build:
  context: .
  dockerfile: backend/Dockerfile
```

## Переменные окружения

Файл [`.env.example`](../.env.example) — шаблон. Скопируйте в `.env`
перед первым `docker-compose up`.

| Переменная | По умолчанию | Где читается |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://messenger:messenger@db:5432/messenger` | `core/config.py` |
| `SYNC_DATABASE_URL` | `postgresql+psycopg2://messenger:messenger@db:5432/messenger` | резерв для Alembic |
| `JWT_SECRET` | `change-me-in-production` | подпись JWT |
| `JWT_ALGORITHM` | `HS256` | алгоритм подписи JWT |
| `JWT_TTL_MINUTES` | `1440` | срок жизни токена |
| `BCRYPT_ROUNDS` | `12` | стоимость bcrypt |
| `NONCE_WINDOW_SECONDS` | `300` | окно anti-replay |
| `DEBUG` | `false` | echo SQL и подробные ошибки |

В `docker-compose.yml` `JWT_SECRET` пробрасывается из `.env` хоста через
`${JWT_SECRET:-change-me-in-production}`.

## Объёмы и persistence

* `pgdata` — данные Postgres, переживают перезапуск контейнера.
  Удалить: `docker-compose down -v`.
* Bind-маунтов исходников **больше нет** — фронтенд запекается в образ
  через Vite на этапе сборки. Для hot-reload разработки используйте
  локальный запуск (см. ниже).

## Локальная разработка без Docker

Удобный режим для отладки: бэкенд через `uvicorn --reload`, фронт через
Vite dev-сервер.

```bash
# поднять только Postgres
docker-compose up -d db

# Бэкенд — в одном терминале
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://messenger:messenger@localhost:5432/messenger
alembic upgrade head
uvicorn app.main:app --reload                  # → :8000

# Фронт — в другом
cd frontend
npm install
npm run dev                                    # → :5173 с HMR
```

`vite.config.js` проксирует `/api` и `/ws` с :5173 на :8000, так что
открывать достаточно `http://localhost:5173`.

Если хочется собрать прод-версию и отдавать её с того же бэкенда:

```bash
cd frontend && npm run build
# теперь FastAPI на :8000 сам отдаёт frontend/dist
```

`backend/app/main.py` ищет `dist/` в двух местах:
`/frontend/dist` (внутри Docker) и `<repo>/frontend/dist` (локально).

## Порты и сетевые настройки

* **8000** — FastAPI (REST, WebSocket, статический фронтенд).
* **5432** — Postgres (для удобной отладки прокинут наружу; в проде
  закройте).

Между сервисами Compose использует внутреннюю DNS — `backend` обращается
к БД по имени `db`.

## Здоровье

* `GET /health` отвечает `{"status":"ok"}` — удобно для readiness-проб
  оркестратора.
* Healthcheck для Postgres описан внутри `docker-compose.yml`.

## Типичные проблемы

| Симптом | Что не так | Что делать |
| --- | --- | --- |
| `database files are incompatible with server` | Том `pgdata` остался от Postgres 15, а образ — 16 | `docker compose down -v` (потеряете данные) или поменять образ обратно на `postgres:15-alpine` |
| `connect: connection refused` при первом запуске | Backend стартовал быстрее, чем БД дошла до healthy | повторите `docker compose up`; depends_on с health уже настроен, так что обычно не нужно |
| `Can't locate revision identified by '00XX_...'` | В БД зафиксирована ревизия Alembic'а, файл которой удалили (например, после rebase/отката фичи) | Восстановите файл миграции либо вручную обновите запись в `alembic_version` |
| Перестали приходить сообщения по WS | Не перезапустился контейнер после правки `.env` | `docker compose restart backend` |
| Alembic при `revision --autogenerate` не видит изменений | Не импортированы модели в `env.py` | проверьте `from app import models` в [`alembic/env.py`](../backend/alembic/env.py) |
| Открывается белый экран на :8000 | `frontend/dist` не собран | `cd frontend && npm install && npm run build` или `docker compose up --build` |
| `/api/...` отдаёт HTML (SPA fallback) | Запрос ушёл не на тот бэкенд | проверьте, что Vite dev-сервер видит `/api` через proxy, или ходите напрямую на :8000 |
| Бэкенд падает на старте с `Streebog optimized hash diverges from reference` | Self-test ГОСТ-крипто не сошёлся — кто-то неаккуратно правил `streebog.py` или `cipher.py` | Откатить правки в `crypto/`; self-test работает специально как страховка |

## Чего нет в Compose

* TLS-терминирования. Поставьте перед стеком nginx/Caddy/Traefik.
* Pgbouncer'а — для одного процесса не нужен.
* Прометеус-метрик — не реализованы; FastAPI вернёт 404 на `/metrics`.
