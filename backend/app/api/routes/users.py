from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...database.session import get_db
from ...models import User
from ...schemas.user import UserProfile, UserProfileUpdate
from ...services import user as user_service
from ...websocket.manager import manager
from ..deps import current_user

router = APIRouter()


ALLOWED_AVATAR_MIME = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2 МБ — клиент должен ужать ещё больше


def _to_profile(u: User, *, online_override: bool | None = None) -> UserProfile:
    is_online = manager.is_online(u.id) if online_override is None else online_override
    return UserProfile(
        user_id=u.id,
        username=u.username,
        display_name=u.display_name,
        bio=u.bio,
        public_key_hex=u.public_key.hex(),
        created_at=u.created_at,
        last_seen_at=u.last_seen_at,
        is_online=is_online,
        has_avatar=u.avatar_data is not None,
        avatar_version=u.avatar_version or 0,
    )


@router.get("/", response_model=list[UserProfile])
async def list_users(
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> list[UserProfile]:
    users = await user_service.list_users(session, exclude_id=me.id)
    return [_to_profile(u) for u in users]


@router.get("/me", response_model=UserProfile)
async def get_me(me: User = Depends(current_user)) -> UserProfile:
    # О себе — всегда «онлайн» в момент запроса.
    return _to_profile(me, online_override=True)


@router.patch("/me", response_model=UserProfile)
async def update_me(
    payload: UserProfileUpdate,
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> UserProfile:
    me = await user_service.update_profile(session, me, payload)
    return _to_profile(me, online_override=True)


@router.get("/{user_id}", response_model=UserProfile)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(current_user),
) -> UserProfile:
    user = await user_service.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return _to_profile(user)


@router.get("/{user_id}/public-key", response_model=UserProfile)
async def get_public_key(
    user_id: int,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(current_user),
) -> UserProfile:
    """Совместимый эндпоинт — отдаёт ту же расширенную форму профиля."""
    user = await user_service.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return _to_profile(user)


# ─────────────────────────────── avatars ──────────────────────────────────

@router.post("/me/avatar", response_model=UserProfile)
async def set_my_avatar(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> UserProfile:
    if file.content_type not in ALLOWED_AVATAR_MIME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="avatar must be jpeg / png / webp",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty file")
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"avatar too large (max {MAX_AVATAR_BYTES // 1024} KB)",
        )
    me.avatar_data = data
    me.avatar_mime = file.content_type
    me.avatar_version = (me.avatar_version or 0) + 1
    await session.commit()
    await session.refresh(me)
    return _to_profile(me, online_override=True)


@router.delete("/me/avatar", response_model=UserProfile)
async def remove_my_avatar(
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> UserProfile:
    if me.avatar_data is None:
        return _to_profile(me, online_override=True)
    me.avatar_data = None
    me.avatar_mime = None
    me.avatar_version = (me.avatar_version or 0) + 1
    await session.commit()
    await session.refresh(me)
    return _to_profile(me, online_override=True)


@router.get("/{user_id}/avatar")
async def get_avatar(
    user_id: int,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(current_user),
) -> Response:
    user = await user_service.get_by_id(session, user_id)
    if user is None or user.avatar_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no avatar")
    return Response(
        content=user.avatar_data,
        media_type=user.avatar_mime or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=86400"},
    )
