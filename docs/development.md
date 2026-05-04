# Разработка

Этот документ — для тех, кто планирует расширять проект: добавлять
эндпоинты, менять схему БД, писать тесты, заменять S-боксы и т. д.

## Окружение

См. [deployment.md](deployment.md#локальная-разработка-без-docker).

Минимум — два терминала:

**Бэкенд:**

```bash
docker-compose up -d db
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload      # → :8000
```

**Фронтенд (Vite + HMR):**

```bash
cd frontend
npm install                        # один раз
npm run dev                        # → :5173
```

Vite-конфиг проксирует `/api` и `/ws` на `:8000`, так что в браузере
открываете `http://localhost:5173` и сразу получаете HMR + живые
запросы к бэкенду.

Полезные переменные на время разработки:

```bash
export DEBUG=true                 # echo SQL и подробные трейсбеки
export JWT_TTL_MINUTES=10080      # неделя — реже выкидывает на /
```

## Структура для новых фич

Соблюдайте слои (см. [architecture.md](architecture.md)). Если новая
фича — это «добавить эндпоинт», обычно нужны:

1. Pydantic-схемы в `app/schemas/`.
2. Новый сервис или дополнения к существующему в `app/services/`.
3. Роут в `app/api/routes/`.
4. (Если меняется БД) ORM-модель в `app/models/` и Alembic-ревизия.
5. Регистрация роутера в `app/api/routes/__init__.py`.

Криптовызовы не делайте из роутов — только через
`from app.crypto.provider import provider`.

## Добавление миграции

```bash
# можно автогенерацию по diff моделей и БД
docker-compose run --rm backend \
    alembic revision --autogenerate -m "add foo column"

# или пустую и заполнить руками
docker-compose run --rm backend alembic revision -m "manual fix"
```

После генерации:

1. Просмотрите файл в `backend/alembic/versions/` — autogenerate не
   всегда видит ENUM/Index/check-constraint.
2. Прогоните `alembic upgrade head` и `alembic downgrade -1`,
   убедитесь, что миграция обратима.
3. Закомитьте файл вместе с изменениями моделей.

Соглашение об именах — `NNNN_описание.py`, например
`0002_add_message_read_state.py`.

> **Не удаляйте файлы миграций**, которые уже применялись на каком-то
> контуре. Alembic фиксирует версию в `alembic_version`, и если файла
> не окажется — на старте получите `Can't locate revision identified by
> '...'`. Если фича откачена, оставьте старую миграцию как
> «no-op-плейсхолдер» (или с раскрытыми обратными `op.execute("ALTER ...
> IF EXISTS")`) и добавьте новую с восстанавливающей логикой. См.
> историю `0005_user_avatar`/`0006_drop_user_avatar`/`0007_restore_user_avatar`
> для рабочего примера.

## Тесты

В прототипе нет полноценного тест-сьюта, но проще всего запускать
быстрые проверки крипто-кода прямо из REPL или коротким `python -c`.
Рекомендуемый минимум для PR'а — добавить:

* юнит-тесты на новый код (например, `pytest`);
* round-trip для крипто (хеш детерминирован; encrypt/decrypt
  совпадают; sign/verify проходят и валятся при искажении).

Пример быстрого smoke-теста для крипто:

```python
import asyncio
from app.crypto.provider import provider

async def main():
    priv, pub = await provider.generate_keypair()
    sig = await provider.sign(b"hi", priv)
    assert await provider.verify(b"hi", sig, pub)
    assert not await provider.verify(b"hi!", sig, pub)
    print("ok")

asyncio.run(main())
```

Для добавления полноценных тестов:

```bash
pip install pytest pytest-asyncio httpx
pytest backend/tests
```

Каркас можно положить в `backend/tests/`; точкой входа — `conftest.py`
с фикстурой `async_client` поверх `httpx.AsyncClient(app=app)`.

## Полезные команды

```bash
# принудительно пересобрать backend без перезапуска БД
docker-compose build backend && docker-compose up -d backend

# логи бэкенда
docker-compose logs -f backend

# запустить shell в контейнере
docker-compose exec backend bash

# обнулить БД
docker-compose down -v && docker-compose up --build

# проверить, что код импортируется чисто
python -c "import app.main"
```

## Стиль кода

Проект придерживается «современного» Python:

* `from __future__ import annotations` в каждом файле, type hints
  везде;
* `pydantic` v2 с `ConfigDict`/`model_config`;
* `SQLAlchemy 2` с `Mapped[T]`/`mapped_column`;
* короткие docstring'и сверху модуля, минимум inline-комментариев.

Форматтер не зашит, но `black`/`ruff` на дефолтных настройках работают
без замечаний.

## Как заменить криптопараметры

* **Другой набор ГОСТ-кривых.** Допишите в
  [`crypto/gost3410/curves.py`](../backend/app/crypto/gost3410/curves.py)
  свой `Curve(...)` и поменяйте `provider.curve` (либо передавайте
  явно). Размер скаляра вычисляется автоматически из `q.bit_length()`.
* **Другие S-боксы для ГОСТ 28147.** Поменяйте таблицу в
  [`crypto/gost28147/sboxes.py`](../backend/app/crypto/gost28147/sboxes.py).
  Никаких других правок не нужно.
* **Streebog-512 вместо 256.** Уже реализован в
  [`gost3411/streebog.py`](../backend/app/crypto/gost3411/streebog.py)
  как `streebog_512`. Чтобы переключить подпись на 512-битный хеш,
  поменяйте вызов в [`gost3410/signature.py`](../backend/app/crypto/gost3410/signature.py)
  и используйте `paramSetA` 512-битной кривой (нужно будет добавить).

## Коммиты и ветки

Прототип одиночный, поэтому жёстких правил нет. Один разумный приём:

* `feat:` / `fix:` / `docs:` в заголовке коммита,
* одна логическая правка на коммит,
* PR-описание на 1–2 фразы — что и зачем.

## Куда смотреть, если что-то не работает

| Симптом | Куда смотреть |
| --- | --- |
| Падает регистрация | `services/auth.py`, проверка bcrypt и `_wrap_private_key` |
| Подпись не валидна | `crypto/gost3410/signature.py`, конкретно `_digest_to_alpha` (e=0) |
| После рестарта БД ошибки | возможно изменилась схема — `alembic upgrade head` |
| WebSocket соединение отваливается сразу | проверьте, что `?token=` корректный JWT |
| Сообщение пришло, но текст — hex | ключ беседы выводится не из той пары — проверьте, что `unseal` получает обе пары `sender_id` и `recipient_id` |
| Чат внезапно показывает только часть истории | в БД больше сообщений, чем `INITIAL_LIMIT`. Проверьте, что `list_for_user` использует `desc().limit()` и что фронт реализует подгрузку через `before_id` |
| Картинка приходит, но не показывается | смотрите `AttachmentImage.svelte` и заголовок `X-Signature-Valid` — если `0`, проверьте подпись в `attachments.signature` |
| Бэкенд не стартует после правки `crypto/` | Self-test ГОСТ-оптимизаций не прошёл — на консоли `RuntimeError: ... diverges from reference`. Восстановите код примитивов или дополните `_self_test` новыми кейсами |
