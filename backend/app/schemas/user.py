from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime


class UserProfile(BaseModel):
    """Публичный профиль пользователя.

    Используется и в списке контактов, и в модалке профиля. Поле
    ``is_online`` вычисляется на лету из ConnectionManager'a и не
    сохраняется в БД.
    """

    user_id: int
    username: str
    display_name: str | None = None
    bio: str | None = None
    public_key_hex: str
    created_at: datetime
    last_seen_at: datetime | None = None
    is_online: bool = False
    has_avatar: bool = False
    avatar_version: int = 0


class UserProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=500)
