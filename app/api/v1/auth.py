"""
Auth routes: registration, login, logout, token refresh, OAuth.
All auth forms POST here and redirect back to HTML pages.
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user_optional
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    set_auth_cookies,
    clear_auth_cookies,
    hash_password,
)
from app.db.session import get_db
from app.models.user import OAuthProvider, UserRole
from app.schemas.user import UserCreate
from app.services.user_service import (
    authenticate_user,
    authenticate_user_by_username,
    create_user,
    create_oauth_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_oauth,
    get_user_by_username,
    update_last_login,
)
from app.services.oauth_service import (
    generate_state,
    get_google_auth_url,
    exchange_google_code,
    get_github_auth_url,
    exchange_github_code,
    get_vk_auth_url,
    exchange_vk_code,
)
from app.templates_env import templates

router = APIRouter(prefix="/auth", tags=["auth"])


def _redirect_with_error(url: str, msg: str) -> RedirectResponse:
    return RedirectResponse(f"{url}?error={msg}", status_code=302)


# ── Register ──────────────────────────────────────────────────────────────────
@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    current_user=Depends(get_current_user_optional),
):
    if current_user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
async def register(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(""),
    want_to_write: str = Form("no"),
    db: AsyncSession = Depends(get_db),
):
    import re as _re
    # Validate username: 3-50 chars, latin letters, digits, _ or -
    username = username.strip().lower()
    if len(username) < 3 or len(username) > 50:
        return _redirect_with_error("/auth/register", "username_length")
    if not _re.match(r"^[a-zA-Z0-9_\-]+$", username):
        return _redirect_with_error("/auth/register", "username_invalid")
    # Validate password
    if len(password) < 8:
        return _redirect_with_error("/auth/register", "password_short")
    if not _re.search(r"[A-Z]", password):
        return _redirect_with_error("/auth/register", "password_no_upper")
    if not _re.search(r"[0-9]", password):
        return _redirect_with_error("/auth/register", "password_no_digit")
    # Check uniqueness
    if await get_user_by_username(db, username):
        return _redirect_with_error("/auth/register", "username_taken")

    # Auto-generate a unique internal email (not shown to user)
    import uuid as _uuid
    email = f"{username}_{_uuid.uuid4().hex[:8]}@internal.literaryhaven"

    # Hash password manually to bypass EmailStr validation
    from app.core.security import hash_password as get_password_hash
    from app.models.user import User as UserModel, UserRole as UR
    user_obj = UserModel(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        display_name=display_name.strip() or username,
        role=UR.READER,
        is_active=True,
        is_verified=False,
        is_banned=False,
        followers_count=0,
        following_count=0,
        works_count=0,
    )
    db.add(user_obj)
    await db.flush()

    # Set author role if user wants to write
    if want_to_write == "yes":
        user_obj.role = UR.AUTHOR
        await db.flush()

    access = create_access_token(user_obj.id, user_obj.role)
    refresh = create_refresh_token(user_obj.id)
    resp = RedirectResponse("/", status_code=302)
    set_auth_cookies(resp, access, refresh)
    return resp


# ── Login ─────────────────────────────────────────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    current_user=Depends(get_current_user_optional),
):
    if current_user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user_by_username(db, username, password)
    if not user:
        return _redirect_with_error("/auth/login", "invalid_credentials")
    if not user.is_active:
        return _redirect_with_error("/auth/login", "account_disabled")

    await update_last_login(db, user)
    access = create_access_token(user.id, user.role)
    refresh = create_refresh_token(user.id)
    resp = RedirectResponse("/", status_code=302)
    set_auth_cookies(resp, access, refresh)
    return resp


# ── Logout ────────────────────────────────────────────────────────────────────
@router.post("/logout")
async def logout():
    resp = RedirectResponse("/", status_code=302)
    clear_auth_cookies(resp)
    return resp


# ── Token refresh ─────────────────────────────────────────────────────────────
@router.post("/refresh")
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    from app.core.security import get_refresh_from_request
    token = get_refresh_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    payload = decode_refresh_token(token)
    user = await get_user_by_id(db, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")
    access = create_access_token(user.id, user.role)
    new_refresh = create_refresh_token(user.id)
    resp = Response(status_code=204)
    set_auth_cookies(resp, access, new_refresh)
    return resp


# ── Google OAuth ──────────────────────────────────────────────────────────────
@router.get("/google")
async def google_auth(request: Request):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(400, "Google OAuth is not configured")
    state = generate_state()
    request.session["oauth_state"] = state
    return RedirectResponse(get_google_auth_url(state))


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if request.session.get("oauth_state") != state:
        return _redirect_with_error("/auth/login", "state_mismatch")
    request.session.pop("oauth_state", None)

    info = await exchange_google_code(code)
    if not info or not info.get("email"):
        return _redirect_with_error("/auth/login", "oauth_failed")

    return await _oauth_login_or_create(db, info, OAuthProvider.GOOGLE)


# ── GitHub OAuth ──────────────────────────────────────────────────────────────
@router.get("/github")
async def github_auth(request: Request):
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(400, "GitHub OAuth is not configured")
    state = generate_state()
    request.session["oauth_state"] = state
    return RedirectResponse(get_github_auth_url(state))


@router.get("/github/callback")
async def github_callback(
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if request.session.get("oauth_state") != state:
        return _redirect_with_error("/auth/login", "state_mismatch")
    request.session.pop("oauth_state", None)

    info = await exchange_github_code(code)
    if not info or not info.get("email"):
        return _redirect_with_error("/auth/login", "oauth_failed")

    return await _oauth_login_or_create(db, info, OAuthProvider.GITHUB)


# ── VK OAuth ──────────────────────────────────────────────────────────────────
@router.get("/vk")
async def vk_auth(request: Request):
    if not settings.VK_CLIENT_ID:
        raise HTTPException(400, "VK OAuth is not configured")
    state = generate_state()
    request.session["oauth_state"] = state
    return RedirectResponse(get_vk_auth_url(state))


@router.get("/vk/callback")
async def vk_callback(
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if request.session.get("oauth_state") != state:
        return _redirect_with_error("/auth/login", "state_mismatch")
    request.session.pop("oauth_state", None)

    info = await exchange_vk_code(code)
    if not info:
        return _redirect_with_error("/auth/login", "oauth_failed")

    return await _oauth_login_or_create(db, info, OAuthProvider.VK)


# ── Shared OAuth helper ───────────────────────────────────────────────────────
async def _oauth_login_or_create(db, info: dict, provider: OAuthProvider) -> RedirectResponse:
    user = await get_user_by_oauth(db, provider, str(info["provider_id"]))
    if not user:
        # Try to link by email
        user = await get_user_by_email(db, info["email"]) if info.get("email") else None
        if user:
            user.oauth_provider = provider
            user.oauth_provider_id = str(info["provider_id"])
            await db.flush()
        else:
            # Create new account
            base_username = _make_username(info.get("name") or info.get("email", "user"))
            username = await _unique_username(db, base_username)
            user = await create_oauth_user(
                db,
                email=info["email"],
                username=username,
                display_name=info.get("name", username),
                avatar_url=info.get("avatar_url"),
                provider=provider,
                provider_id=str(info["provider_id"]),
            )

    if not user.is_active:
        return _redirect_with_error("/auth/login", "account_disabled")

    await update_last_login(db, user)
    access = create_access_token(user.id, user.role)
    refresh = create_refresh_token(user.id)
    resp = RedirectResponse("/", status_code=302)
    set_auth_cookies(resp, access, refresh)
    return resp


def _make_username(name: str) -> str:
    import re
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())[:40] or "user"
    return slug


async def _unique_username(db, base: str) -> str:
    from app.services.user_service import get_user_by_username
    username = base
    counter = 1
    while await get_user_by_username(db, username):
        username = f"{base}{counter}"
        counter += 1
    return username
