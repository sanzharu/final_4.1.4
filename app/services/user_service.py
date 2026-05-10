from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.models.user import User, UserRole, OAuthAccount, OAuthProvider
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import hash_password, verify_password


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.username == username.lower()))
    return result.scalar_one_or_none()


async def get_user_by_oauth(db: AsyncSession, provider, provider_id: str) -> Optional[User]:
    provider_str = provider.value if hasattr(provider, "value") else str(provider)
    result = await db.execute(
        select(User).where(
            User.oauth_provider == provider_str,
            User.oauth_provider_id == provider_id,
        )
    )
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, data: UserCreate, role: UserRole = UserRole.READER) -> User:
    if await get_user_by_email(db, data.email):
        raise HTTPException(status_code=400, detail="Этот email уже зарегистрирован")
    if await get_user_by_username(db, data.username):
        raise HTTPException(status_code=400, detail="Это имя пользователя уже занято")

    user = User(
        username=data.username.lower(),
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
        display_name=data.display_name or data.username,
        role=role,
        is_verified=False,
    )
    db.add(user)
    await db.flush()
    return user


async def create_oauth_user(
    db: AsyncSession,
    email: str,
    username: str,
    display_name: str,
    provider,
    provider_id: str,
    avatar_url: Optional[str] = None,
) -> User:
    provider_str = provider.value if hasattr(provider, "value") else str(provider)
    user = User(
        username=username.lower(),
        email=email.lower(),
        display_name=display_name,
        avatar_url=avatar_url,
        role=UserRole.READER,
        is_verified=True,
        oauth_provider=provider_str,
        oauth_provider_id=provider_id,
    )
    db.add(user)
    await db.flush()
    return user


async def get_or_create_oauth_user(
    db: AsyncSession,
    provider: str,
    provider_id: str,
    email: str,
    display_name: str,
    avatar_url: Optional[str] = None,
) -> User:
    """Find existing OAuth user or create a new one. Used by OAuth callbacks."""
    # Try to find by oauth provider + id
    result = await db.execute(
        select(User).where(
            User.oauth_provider == provider,
            User.oauth_provider_id == provider_id,
        )
    )
    user = result.scalar_one_or_none()
    if user:
        return user

    # Try to find by email (link accounts)
    if email:
        result = await db.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()
        if user:
            user.oauth_provider = provider
            user.oauth_provider_id = provider_id
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
            await db.flush()
            return user

    # Generate unique username from display_name/email
    import re as _re
    import uuid as _uuid
    base_username = _re.sub(r"[^a-zA-Z0-9_]", "", (display_name or email.split("@")[0]).lower())[:30] or "user"
    username = base_username
    suffix = 0
    while (await db.execute(select(User).where(User.username == username))).scalar_one_or_none():
        suffix += 1
        username = f"{base_username}{suffix}"

    # Generate internal email if none provided
    if not email:
        email = f"{username}_{_uuid.uuid4().hex[:8]}@oauth.internal"

    user = User(
        username=username,
        email=email.lower(),
        display_name=display_name or username,
        avatar_url=avatar_url,
        role=UserRole.READER,
        is_active=True,
        is_verified=True,
        oauth_provider=provider,
        oauth_provider_id=provider_id,
    )
    db.add(user)
    await db.flush()
    return user



async def authenticate_user_by_username(db: AsyncSession, username: str, password: str):
    """Authenticate by username instead of email."""
    from app.core.security import verify_password
    user = await get_user_by_username(db, username.lower().strip())
    if not user or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    user = await get_user_by_email(db, email)
    if not user or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def update_user(db: AsyncSession, user: User, data: UserUpdate) -> User:
    for field, value in data.model_dump(exclude_none=True).items():
        if hasattr(user, field):
            setattr(user, field, value)
    await db.flush()
    return user


async def change_password(db: AsyncSession, user: User, current_or_new: str, new: str = None) -> None:
    """Support both change_password(db, user, current, new) and change_password(db, user, new_only)."""
    if new is None:
        # Called as change_password(db, user, new_password) - no current check
        user.hashed_password = hash_password(current_or_new)
    else:
        if not verify_password(current_or_new, user.hashed_password or ""):
            raise HTTPException(status_code=400, detail="Неверный текущий пароль")
        user.hashed_password = hash_password(new)
    await db.flush()


async def update_last_login(db: AsyncSession, user: User) -> None:
    user.last_login = datetime.now(timezone.utc)
    await db.flush()


async def set_role(db: AsyncSession, user_or_id, role: UserRole) -> User:
    if isinstance(user_or_id, int):
        user = await get_user_by_id(db, user_or_id)
    else:
        user = user_or_id
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.role = role
    await db.flush()
    return user


async def ban_user(db: AsyncSession, user_id: int, reason: str) -> User:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.is_banned = True
    user.ban_reason = reason
    await db.flush()
    return user


async def deactivate_user(db: AsyncSession, user_id: int) -> User:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.is_active = False
    await db.flush()
    return user
