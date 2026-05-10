from fastapi import APIRouter, HTTPException, Query
from app.core.deps import DB, CurrentUser, CurrentAdmin
from app.schemas.user import UserRead, UserUpdate, PasswordChange
from app.services.user_service import update_user, change_password, get_user_by_username, set_role, ban_user
from app.models.user import UserRole

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(user: CurrentUser):
    return user


@router.put("/me", response_model=UserRead)
async def update_me(data: UserUpdate, db: DB, user: CurrentUser):
    return await update_user(db, user, data)


@router.post("/me/password")
async def change_my_password(data: PasswordChange, db: DB, user: CurrentUser):
    await change_password(db, user, data.current_password, data.new_password)
    return {"detail": "Пароль изменён"}


@router.get("/{username}", response_model=UserRead)
async def get_user_profile(username: str, db: DB):
    user = await get_user_by_username(db, username)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


# ── Admin actions ─────────────────────────────────────────────────────────────
@router.post("/{user_id}/role")
async def change_role(user_id: int, role: UserRole, db: DB, admin: CurrentAdmin):
    user = await set_role(db, user_id, role)
    return {"detail": f"Роль изменена на {role.value}", "user_id": user.id}


@router.post("/{user_id}/ban")
async def ban(user_id: int, reason: str = Query(..., max_length=500), db: DB = None, admin: CurrentAdmin = None):
    user = await ban_user(db, user_id, reason)
    return {"detail": "Пользователь заблокирован", "user_id": user.id}
