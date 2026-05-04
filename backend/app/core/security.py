"""Password hashing (bcrypt) and JWT helpers.

bcrypt is the ONLY external crypto we use, and only for password
storage. All transport / signing / hashing of message bodies goes
through the manual GOST CryptoProvider.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from .config import get_settings


# ----------------------------------------------------------------------
# Password hashing
# ----------------------------------------------------------------------
async def hash_password(password: str) -> str:
    settings = get_settings()
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    digest = await asyncio.to_thread(bcrypt.hashpw, password.encode("utf-8"), salt)
    return digest.decode("utf-8")


async def verify_password(password: str, password_hash: str) -> bool:
    return await asyncio.to_thread(
        bcrypt.checkpw, password.encode("utf-8"), password_hash.encode("utf-8")
    )


# ----------------------------------------------------------------------
# JWT
# ----------------------------------------------------------------------
def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_ttl_minutes)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
