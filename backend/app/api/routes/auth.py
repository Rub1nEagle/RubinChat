from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...database.session import get_db
from ...models import User
from ...schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from ...services import auth as auth_service
from ...services.auth import AuthError
from ..deps import current_user

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        return await auth_service.register(session, payload)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        return await auth_service.login(session, payload)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/change-password", response_model=TokenResponse)
async def change_password(
    payload: ChangePasswordRequest,
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> TokenResponse:
    try:
        return await auth_service.change_password(session, me, payload)
    except AuthError as exc:
        text = str(exc)
        code = (
            status.HTTP_401_UNAUTHORIZED
            if "неверный" in text
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=text) from exc


@router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    payload: DeleteAccountRequest,
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> Response:
    try:
        await auth_service.delete_account(session, me, payload)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
