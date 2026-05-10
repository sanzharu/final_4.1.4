"""
FastAPI dependency injection — auth, DB, current user, role checks.
"""
from typing import Optional, Annotated
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.services.user_service import get_user_by_id

bearer = HTTPBearer(auto_error=False)


async def _get_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> Optional[str]:
    """Extract JWT from Authorization header OR httpOnly cookie."""
    if credentials:
        return credentials.credentials
    return request.cookies.get("access_token")


async def get_current_user_optional(
    token: Optional[str] = Depends(_get_token),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        return None
    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active or user.is_banned:
        return None
    return user


async def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Необходима авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_author(user: User = Depends(get_current_user)) -> User:
    if not user.can_publish:
        raise HTTPException(status_code=403, detail="Требуется роль автора")
    return user


async def get_current_moderator(user: User = Depends(get_current_user)) -> User:
    if not user.is_staff:
        raise HTTPException(status_code=403, detail="Требуется роль модератора")
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Требуется роль администратора")
    return user


# Type aliases for cleaner endpoint signatures
DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[Optional[User], Depends(get_current_user_optional)]
CurrentAuthor = Annotated[User, Depends(get_current_author)]
CurrentModerator = Annotated[User, Depends(get_current_moderator)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]


async def get_current_active_author(user: User = Depends(get_current_user)) -> User:
    if not user.can_publish:
        raise HTTPException(status_code=403, detail="Требуется роль автора")
    return user
