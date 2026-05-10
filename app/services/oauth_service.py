"""
OAuth 2.0 helpers for Google, GitHub, and VK.
Each provider has:
  - get_auth_url(state) → redirect URL
  - exchange_code(code)  → dict with user info
"""
import secrets
from typing import Dict, Any, Optional

import httpx

from app.core.config import settings


def generate_state() -> str:
    return secrets.token_urlsafe(32)


# ── Google ────────────────────────────────────────────────────────────────────
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def get_google_auth_url(state: str) -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
    }
    return GOOGLE_AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())


async def exchange_google_code(code: str) -> Optional[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            return None
        access_token = token_resp.json().get("access_token")
        if not access_token:
            return None

        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_resp.status_code != 200:
            return None
        data = user_resp.json()
        return {
            "provider": "google",
            "provider_id": data.get("sub"),
            "email": data.get("email"),
            "name": data.get("name", ""),
            "avatar_url": data.get("picture"),
        }


# ── GitHub ────────────────────────────────────────────────────────────────────
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


def get_github_auth_url(state: str) -> str:
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_REDIRECT_URI,
        "scope": "read:user user:email",
        "state": state,
    }
    return GITHUB_AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())


async def exchange_github_code(code: str) -> Optional[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
            },
        )
        if token_resp.status_code != 200:
            return None
        access_token = token_resp.json().get("access_token")
        if not access_token:
            return None

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        }
        user_resp = await client.get(GITHUB_USER_URL, headers=headers)
        if user_resp.status_code != 200:
            return None
        user_data = user_resp.json()

        # GitHub may not expose email in user profile – fetch separately
        email = user_data.get("email")
        if not email:
            emails_resp = await client.get(GITHUB_EMAILS_URL, headers=headers)
            if emails_resp.status_code == 200:
                primary = next(
                    (e for e in emails_resp.json() if e.get("primary") and e.get("verified")),
                    None,
                )
                email = primary["email"] if primary else None

        return {
            "provider": "github",
            "provider_id": str(user_data.get("id")),
            "email": email,
            "name": user_data.get("name") or user_data.get("login", ""),
            "avatar_url": user_data.get("avatar_url"),
        }


# ── VK ────────────────────────────────────────────────────────────────────────
VK_AUTH_URL = "https://oauth.vk.com/authorize"
VK_TOKEN_URL = "https://oauth.vk.com/access_token"
VK_USER_URL = "https://api.vk.com/method/users.get"


def get_vk_auth_url(state: str) -> str:
    params = {
        "client_id": settings.VK_CLIENT_ID,
        "redirect_uri": settings.VK_REDIRECT_URI,
        "scope": "email",
        "response_type": "code",
        "state": state,
        "v": "5.131",
    }
    return VK_AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())


async def exchange_vk_code(code: str) -> Optional[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.get(
            VK_TOKEN_URL,
            params={
                "client_id": settings.VK_CLIENT_ID,
                "client_secret": settings.VK_CLIENT_SECRET,
                "redirect_uri": settings.VK_REDIRECT_URI,
                "code": code,
            },
        )
        if token_resp.status_code != 200:
            return None
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        vk_user_id = token_data.get("user_id")
        email = token_data.get("email")
        if not access_token:
            return None

        user_resp = await client.get(
            VK_USER_URL,
            params={
                "access_token": access_token,
                "user_ids": vk_user_id,
                "fields": "photo_200",
                "v": "5.131",
            },
        )
        if user_resp.status_code != 200:
            return None
        vk_users = user_resp.json().get("response", [])
        if not vk_users:
            return None
        vk_user = vk_users[0]

        return {
            "provider": "vk",
            "provider_id": str(vk_user_id),
            "email": email,
            "name": f"{vk_user.get('first_name', '')} {vk_user.get('last_name', '')}".strip(),
            "avatar_url": vk_user.get("photo_200"),
        }
