"""Test infrastructure.

Set environment variables BEFORE any application import — pydantic-settings
caches `Settings()` on first call, so the env must be ready by then.
"""
from __future__ import annotations

import os

# ── env ───────────────────────────────────────────────────────────────────
# SQLite-backed test DB. The app's engine itself is created against this
# URL (so import-time `create_async_engine` doesn't try to talk to Postgres),
# but every test then swaps in its own in-memory engine via fixtures below.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SYNC_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-not-used-in-prod")
# Lower bcrypt cost so the auth flows don't dominate the test runtime.
os.environ.setdefault("BCRYPT_ROUNDS", "4")

# ── imports (after env is ready) ─────────────────────────────────────────
from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database.base import Base  # noqa: E402
from app.database import session as db_session_mod  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import message as message_service_mod  # noqa: E402
from app.websocket.manager import manager as ws_manager  # noqa: E402
from app.websocket import router as ws_router_mod  # noqa: E402
# Importing models registers them on Base.metadata so create_all sees them.
from app import models  # noqa: F401, E402


# ── DB fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_engine():
    """Per-test in-memory SQLite engine with a single shared connection.

    StaticPool keeps every session bound to the same underlying connection
    so ``:memory:`` (which is per-connection) is actually shared across
    requests within one test.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_sessionmaker(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(autouse=True)
def _patch_db(monkeypatch, db_engine, db_sessionmaker):
    """Redirect `app.database.session` and the WS router to the test DB.

    We have to patch the WS router separately — it imported
    ``async_session_maker`` by name at module load, so it holds its own
    reference that wouldn't follow a patch on the source module.
    """
    monkeypatch.setattr(db_session_mod, "engine", db_engine)
    monkeypatch.setattr(db_session_mod, "async_session_maker", db_sessionmaker)
    monkeypatch.setattr(ws_router_mod, "async_session_maker", db_sessionmaker)


@pytest.fixture(autouse=True)
def _reset_global_state():
    """Reset module-level singletons that would otherwise leak between tests."""
    # Anti-replay nonce cache (services.message)
    message_service_mod._nonce_cache._seen.clear()
    # WebSocket connection registry
    ws_manager._connections.clear()
    yield
    message_service_mod._nonce_cache._seen.clear()
    ws_manager._connections.clear()


# ── app + clients ────────────────────────────────────────────────────────


@pytest.fixture
def app():
    return create_app()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── helpers ──────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def register_user(client):
    """Factory: register a user, return TokenResponse dict + auth headers."""

    async def _make(username: str = "alice", password: str = "pa$$word123"):
        resp = await client.post(
            "/api/auth/register",
            json={"username": username, "password": password},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        body["headers"] = {"Authorization": f"Bearer {body['access_token']}"}
        body["password"] = password
        return body

    return _make


@pytest_asyncio.fixture
async def two_users(register_user):
    alice = await register_user(username="alice", password="alicepass1!")
    bob = await register_user(username="bob", password="bobpass123!")
    return alice, bob
