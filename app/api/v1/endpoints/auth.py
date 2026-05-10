"""
Auth endpoints: register, login, logout, refresh, OAuth (Google/GitHub).
All tokens go into httpOnly cookies + returned in JSON for API clients.
"""
from fastapi import APIRouter, HTTPException, Response, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import secrets

from app.core.deps import DB, CurrentUser, get_current_user_optional
from app.core.security import (
    create_access_token, create_refresh_token, decode_refresh_token,
    generate_csrf_token, generate_session_id,
)
from app.core.config import settings
from app.schemas.user import UserCreate, UserLogin, TokenPair, UserRead
from app.services.user_service import (
    create_user, authenticate_user, get_user_by_id, get_or_create_oauth_user,
)
from app.models.user import UserRole

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_OPTS = dict(httponly=True, secure=settings.APP_ENV == "production", samesite="lax")


def _set_tokens(response: Response, user_id: int, role: str) -> TokenPair:
    access = create_access_token(user_id, role)
    refresh = create_refresh_token(user_id)
    response.set_cookie("access_token", access, max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, **COOKIE_OPTS)
    response.set_cookie("refresh_token", refresh, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, **COOKIE_OPTS)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/register", response_model=UserRead, status_code=201)
async def register(data: UserCreate, response: Response, db: DB):
    user = await create_user(db, data)
    _set_tokens(response, user.id, user.role.value)
    return user


@router.post("/login", response_model=TokenPair)
async def login(data: UserLogin, response: Response, db: DB):
    user = await authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Аккаунт деактивирован")
    if user.is_banned:
        raise HTTPException(status_code=403, detail=f"Аккаунт заблокирован: {user.ban_reason}")
    return _set_tokens(response, user.id, user.role.value)


@router.post("/refresh", response_model=TokenPair)
async def refresh(request: Request, response: Response, db: DB):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Отсутствует refresh token")
    payload = decode_refresh_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Недействительный refresh token")
    user = await get_user_by_id(db, int(payload["sub"]))
    if not user or not user.is_active or user.is_banned:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return _set_tokens(response, user.id, user.role.value)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"detail": "Вы вышли из системы"}


# ── OAuth: Google ─────────────────────────────────────────────────────────────
@router.get("/google")
async def google_login(request: Request, response: Response):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth не настроен")
    state = secrets.token_urlsafe(16)
    response.set_cookie("oauth_state", state, max_age=300, httponly=True)
    redirect_uri = f"{settings.OAUTH_REDIRECT_BASE}/api/v1/auth/google/callback"
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code&scope=openid email profile"
        f"&state={state}"
    )
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(request: Request, response: Response, db: DB, code: str = "", state: str = ""):
    stored_state = request.cookies.get("oauth_state", "")
    if not secrets.compare_digest(state, stored_state):
        raise HTTPException(status_code=400, detail="Invalid state")

    redirect_uri = f"{settings.OAUTH_REDIRECT_BASE}/api/v1/auth/google/callback"
    async with httpx.AsyncClient() as client:
        token_resp = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        })
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Ошибка получения токена Google")

        user_resp = await client.get("https://www.googleapis.com/oauth2/v2/userinfo",
                                     headers={"Authorization": f"Bearer {access_token}"})
        info = user_resp.json()

    user = await get_or_create_oauth_user(
        db, "google", info["id"], info["email"],
        info.get("name", info["email"].split("@")[0]),
        info.get("picture"),
    )
    _set_tokens(response, user.id, user.role.value)
    response.delete_cookie("oauth_state")
    return RedirectResponse("/")


# ── OAuth: GitHub ─────────────────────────────────────────────────────────────
@router.get("/github")
async def github_login(request: Request, response: Response):
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=501, detail="GitHub OAuth не настроен")
    state = secrets.token_urlsafe(16)
    response.set_cookie("oauth_state", state, max_age=300, httponly=True)
    redirect_uri = f"{settings.OAUTH_REDIRECT_BASE}/api/v1/auth/github/callback"
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=user:email&state={state}"
    )
    return RedirectResponse(url)


@router.get("/github/callback")
async def github_callback(request: Request, response: Response, db: DB, code: str = "", state: str = ""):
    stored_state = request.cookies.get("oauth_state", "")
    if not secrets.compare_digest(state, stored_state):
        raise HTTPException(status_code=400, detail="Invalid state")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post("https://github.com/login/oauth/access_token", data={
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
        }, headers={"Accept": "application/json"})
        token_data = token_resp.json()
        gh_token = token_data.get("access_token")
        if not gh_token:
            raise HTTPException(status_code=400, detail="Ошибка получения токена GitHub")

        headers = {"Authorization": f"Bearer {gh_token}"}
        user_resp = await client.get("https://api.github.com/user", headers=headers)
        info = user_resp.json()
        emails_resp = await client.get("https://api.github.com/user/emails", headers=headers)
        emails = emails_resp.json()
        primary_email = next((e["email"] for e in emails if e.get("primary")), info.get("email", ""))

    user = await get_or_create_oauth_user(
        db, "github", str(info["id"]), primary_email,
        info.get("name") or info.get("login", ""),
        info.get("avatar_url"),
    )
    _set_tokens(response, user.id, user.role.value)
    response.delete_cookie("oauth_state")
    return RedirectResponse("/")
