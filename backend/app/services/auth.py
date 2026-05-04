"""Registration / login flows.

The user's GOST 34.10 private key is stored server-side **encrypted with
the user's password**. The server never persists the password itself
(only its bcrypt hash) and cannot recover the private key without the
user re-supplying their password at login. This trade-off keeps the UX
simple (login = username + password) while preventing a database leak
from instantly exposing private keys.
"""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import create_access_token, hash_password, verify_password
from ..crypto.provider import provider
from ..models import User
from ..schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from . import user as user_service


class AuthError(Exception):
    """Raised when credentials don't validate or username is taken."""


async def _wrap_private_key(private_key: bytes, password: str) -> bytes:
    """Return nonce(8) || ciphertext(32) — what we persist."""
    derived = await provider.hash(password.encode("utf-8"))  # 32-byte key
    nonce = provider.random_nonce()
    ciphertext = await provider.encrypt(private_key, derived, nonce)
    return nonce + ciphertext


async def _unwrap_private_key(blob: bytes, password: str) -> bytes:
    if len(blob) != 40:
        raise AuthError("encrypted private key blob has invalid length")
    derived = await provider.hash(password.encode("utf-8"))
    nonce, ciphertext = blob[:8], blob[8:]
    return await provider.decrypt(ciphertext, derived, nonce)


async def register(session: AsyncSession, payload: RegisterRequest) -> TokenResponse:
    if await user_service.get_by_username(session, payload.username) is not None:
        raise AuthError("username already taken")

    private_key, public_key = await provider.generate_keypair()
    encrypted_priv = await _wrap_private_key(private_key, payload.password)
    pwd_hash = await hash_password(payload.password)

    user = User(
        username=payload.username,
        password_hash=pwd_hash,
        public_key=public_key,
        encrypted_private_key=encrypted_priv,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AuthError("username already taken") from exc
    await session.refresh(user)

    token = create_access_token(user.id, extra={"username": user.username})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        private_key_hex=private_key.hex(),
    )


async def login(session: AsyncSession, payload: LoginRequest) -> TokenResponse:
    user = await user_service.get_by_username(session, payload.username)
    if user is None or not await verify_password(payload.password, user.password_hash):
        raise AuthError("invalid username or password")

    private_key = await _unwrap_private_key(user.encrypted_private_key, payload.password)
    token = create_access_token(user.id, extra={"username": user.username})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        private_key_hex=private_key.hex(),
    )


async def change_password(
    session: AsyncSession,
    user: User,
    payload: ChangePasswordRequest,
) -> TokenResponse:
    """Сменить пароль: проверяем старый, перекладываем приватный ключ под
    новый ключ-производный, обновляем bcrypt-хеш и выдаём свежий JWT."""
    if not await verify_password(payload.current_password, user.password_hash):
        raise AuthError("текущий пароль неверный")
    if payload.current_password == payload.new_password:
        raise AuthError("новый пароль совпадает со старым")

    # 1. Расшифровать приватный ключ старым паролем — иначе ключ потерян.
    private_key = await _unwrap_private_key(
        user.encrypted_private_key, payload.current_password
    )
    # 2. Перешифровать новым.
    user.encrypted_private_key = await _wrap_private_key(
        private_key, payload.new_password
    )
    # 3. Обновить bcrypt-хеш.
    user.password_hash = await hash_password(payload.new_password)

    await session.commit()
    await session.refresh(user)

    token = create_access_token(user.id, extra={"username": user.username})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        private_key_hex=private_key.hex(),
    )


async def delete_account(
    session: AsyncSession,
    user: User,
    payload: DeleteAccountRequest,
) -> None:
    if not await verify_password(payload.password, user.password_hash):
        raise AuthError("пароль неверный")
    await session.delete(user)
    await session.commit()
