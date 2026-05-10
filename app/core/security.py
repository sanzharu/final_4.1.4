"""
All cryptography, token, password, CSRF utilities.
Never import raw secrets outside this module.
Uses bcrypt directly (compatible with bcrypt >= 4.x on Python 3.12).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets

import bcrypt
from jose import JWTError, jwt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.core.config import settings

# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash password via bcrypt. Returns string."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────
def _create_token(
    data: dict,
    secret: str,
    expire_minutes: Optional[int] = None,
    expire_days: Optional[int] = None,
) -> str:
    payload = data.copy()
    now = datetime.now(timezone.utc)
    if expire_minutes:
        expire = now + timedelta(minutes=expire_minutes)
    elif expire_days:
        expire = now + timedelta(days=expire_days)
    else:
        expire = now + timedelta(minutes=15)
    payload.update({"exp": expire, "iat": now})
    return jwt.encode(payload, secret, algorithm=settings.ALGORITHM)


def create_access_token(user_id: int, role) -> str:
    role_str = role.value if hasattr(role, "value") else str(role)
    return _create_token(
        {"sub": str(user_id), "role": role_str, "type": "access"},
        settings.SECRET_KEY,
        expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


def create_refresh_token(user_id: int) -> str:
    return _create_token(
        {"sub": str(user_id), "type": "refresh"},
        settings.REFRESH_SECRET_KEY,
        expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None


# ── CSRF ──────────────────────────────────────────────────────────────────────
_csrf_serializer = URLSafeTimedSerializer(settings.CSRF_SECRET_KEY)


def generate_csrf_token(session_id: str) -> str:
    return _csrf_serializer.dumps(session_id, salt="csrf")


def verify_csrf_token(token: str, session_id: str, max_age: int = 3600) -> bool:
    try:
        value = _csrf_serializer.loads(token, salt="csrf", max_age=max_age)
        return secrets.compare_digest(value, session_id)
    except (BadSignature, SignatureExpired):
        return False


# ── Email verification / password reset tokens ────────────────────────────────
_email_serializer = URLSafeTimedSerializer(settings.SECRET_KEY)


def generate_email_token(email: str) -> str:
    return _email_serializer.dumps(email, salt="email-verify")


def verify_email_token(token: str, max_age: int = 86400) -> Optional[str]:
    try:
        return _email_serializer.loads(token, salt="email-verify", max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def generate_password_reset_token(email: str) -> str:
    return _email_serializer.dumps(email, salt="pw-reset")


def verify_password_reset_token(token: str, max_age: int = 3600) -> Optional[str]:
    try:
        return _email_serializer.loads(token, salt="pw-reset", max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


# ── Misc helpers ──────────────────────────────────────────────────────────────
def generate_session_id() -> str:
    return secrets.token_urlsafe(32)


def safe_compare(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode(), b.encode())


# ── Cookie helpers ────────────────────────────────────────────────────────────
def set_auth_cookies(response, access_token: str, refresh_token: str) -> None:
    from app.core.config import settings as _settings
    secure = _settings.APP_ENV == "production"
    response.set_cookie(
        "access_token", access_token,
        max_age=_settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True, secure=secure, samesite="lax",
    )
    response.set_cookie(
        "refresh_token", refresh_token,
        max_age=_settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True, secure=secure, samesite="lax",
    )


def clear_auth_cookies(response) -> None:
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


def get_refresh_from_request(request) -> Optional[str]:
    return request.cookies.get("refresh_token")
