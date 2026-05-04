"""Application settings, all loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "RubinChat"
    debug: bool = False

    database_url: str = Field(
        default="postgresql+asyncpg://messenger:messenger@db:5432/messenger",
        description="SQLAlchemy async DSN (asyncpg driver).",
    )
    sync_database_url: str = Field(
        default="postgresql+psycopg2://messenger:messenger@db:5432/messenger",
        description="Sync DSN, used only if Alembic falls back to sync mode.",
    )

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 60 * 24

    bcrypt_rounds: int = 12

    nonce_window_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
