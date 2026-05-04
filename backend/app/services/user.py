"""User-related queries — kept tiny because the schema is tiny."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User
from ..schemas.user import UserProfileUpdate


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def list_users(session: AsyncSession, exclude_id: int | None = None) -> list[User]:
    stmt = select(User).order_by(User.username)
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_profile(
    session: AsyncSession,
    user: User,
    payload: UserProfileUpdate,
) -> User:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        # Пустую строку трактуем как «убрать значение».
        if isinstance(value, str) and value.strip() == "":
            value = None
        setattr(user, field, value)
    await session.commit()
    await session.refresh(user)
    return user


async def touch_last_seen(session: AsyncSession, user_id: int) -> User | None:
    """Записать в БД момент последней активности (вызывается при WS-disconnect).

    Возвращает обновлённого пользователя — caller использует
    ``last_seen_at`` для рассылки presence-события другим клиентам.
    """
    now = datetime.now(timezone.utc)
    stmt = update(User).where(User.id == user_id).values(last_seen_at=now)
    await session.execute(stmt)
    await session.commit()
    user = await session.get(User, user_id)
    return user
