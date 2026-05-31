"""Common FastAPI dependencies (current user from JWT, DB session)."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import decode_access_token
from ..database.session import get_db
from ..models import User
from ..services import user as user_service

# HTTPBearer (а не OAuth2PasswordBearer): логин у нас принимает JSON, а не
# OAuth2-форму, поэтому встроенный диалог password-flow в Swagger не
# работал бы. HTTPBearer даёт в «Authorize» одно поле — туда вставляется
# готовый access_token из ответа /api/auth/login.
bearer_scheme = HTTPBearer(auto_error=False)


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = await user_service.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


async def user_from_token(token: str, session: AsyncSession) -> User | None:
    """Used by the WebSocket route, which can't use Depends easily."""
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        return None
    return await user_service.get_by_id(session, user_id)
