"""
User profile routes: public profile, settings, bookmarks, reading history.
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_current_user_optional
from app.core.security import verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserUpdate
from app.services.user_service import (
    get_user_by_username,
    update_user,
    change_password,
)
from app.services.book_service import list_books, get_user_bookmarks
from app.templates_env import templates

router = APIRouter(tags=["users"])


@router.get("/profile/{username}", response_class=HTMLResponse)
async def public_profile(
    request: Request,
    username: str,
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_username(db, username)
    if not user or not user.is_active:
        raise HTTPException(404, "User not found")

    from sqlalchemy import select
    from app.models.book import Book
    from sqlalchemy.orm import selectinload
    # Show all published+visible books for public profile
    # For own profile show all including hidden
    is_own = current_user and current_user.id == user.id
    if is_own:
        from sqlalchemy import select as sel
        q = sel(Book).where(Book.author_id == user.id).options(selectinload(Book.author)).order_by(Book.created_at.desc()).limit(24)
        result = await db.execute(q)
        books = list(result.scalars().all())
        # Sync works_count if out of sync
        actual = len(books)
        if user.works_count != actual:
            user.works_count = actual
            await db.flush()
    else:
        books, _ = await list_books(db, page=1, per_page=12, author_id=user.id)
    return templates.TemplateResponse(
        "user/profile.html",
        {
            "request": request,
            "current_user": current_user,
            "profile_user": user,
            "books": books,
            "is_own": is_own,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "user/settings.html",
        {"request": request, "current_user": current_user},
    )


@router.post("/settings")
async def update_settings(
    request: Request,
    display_name: str = Form(""),
    bio: str = Form(""),
    website: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = UserUpdate(
        display_name=display_name or None,
        bio=bio or None,
        website=website or None,
    )
    await update_user(db, current_user, data)
    return RedirectResponse("/settings?saved=1", status_code=302)


@router.post("/settings/password")
async def change_password_handler(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.hashed_password or not verify_password(current_password, current_user.hashed_password):
        return RedirectResponse("/settings?error=wrong_password", status_code=302)
    if len(new_password) < 8:
        return RedirectResponse("/settings?error=password_short", status_code=302)
    await change_password(db, current_user, new_password)
    return RedirectResponse("/settings?saved=1", status_code=302)


@router.get("/bookmarks", response_class=HTMLResponse)
async def my_bookmarks(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    books, total = await get_user_bookmarks(db, current_user.id)
    return templates.TemplateResponse(
        "user/bookmarks.html",
        {
            "request": request,
            "current_user": current_user,
            "books": books,
            "total": total,
        },
    )


@router.get("/my-books", response_class=HTMLResponse)
async def my_books(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.can_publish:
        from fastapi.responses import RedirectResponse as RR
        return RR("/", status_code=302)
    from sqlalchemy import select as sel_
    from app.models.book import Book, BookStatus
    from sqlalchemy.orm import selectinload as sload_
    # All published (any status) visible books
    pub_q = sel_(Book).where(
        Book.author_id == current_user.id,
        Book.is_published == True,
        Book.is_draft_hidden == False
    ).options(sload_(Book.author)).order_by(Book.created_at.desc())
    published = list((await db.execute(pub_q)).scalars().all())
    # Drafts and hidden
    draft_q = sel_(Book).where(
        Book.author_id == current_user.id,
        (Book.status == BookStatus.DRAFT) | (Book.is_draft_hidden == True) | (Book.is_published == False)
    ).options(sload_(Book.author)).order_by(Book.created_at.desc())
    drafts = list((await db.execute(draft_q)).unique().scalars().all())
    return templates.TemplateResponse(
        "user/my_books.html",
        {
            "request": request,
            "current_user": current_user,
            "published": published,
            "drafts": drafts,
        },
    )


@router.post("/settings/avatar", response_class=JSONResponse)
async def upload_avatar(
    request: Request,
    avatar: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload profile avatar - saves to static/uploads/avatars/."""
    import os, uuid, shutil

    # Validate file type
    allowed = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if avatar.content_type not in allowed:
        raise HTTPException(400, "Неподдерживаемый формат. Используйте JPG, PNG, GIF или WEBP.")

    # Read and check size (max 2MB)
    data = await avatar.read()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(400, "Файл слишком большой. Максимум 2 МБ.")

    # Save file
    ext = avatar.filename.rsplit(".", 1)[-1].lower() if "." in (avatar.filename or "") else "jpg"
    filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    upload_dir = "app/static/uploads/avatars"
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)

    with open(filepath, "wb") as f:
        f.write(data)

    # Remove old avatar file if exists and is a local upload
    if current_user.avatar_url and current_user.avatar_url.startswith("/static/uploads/avatars/"):
        old_path = "app" + current_user.avatar_url
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    # Update user record
    current_user.avatar_url = f"/static/uploads/avatars/{filename}"
    await db.flush()

    return JSONResponse({"url": current_user.avatar_url})


# ── Follow user (JSON API) ─────────────────────────────────────────────────────
@router.post("/api/users/{username}/follow", response_class=JSONResponse)
async def follow_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.book_service import toggle_follow, is_following
    target = await get_user_by_username(db, username)
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == current_user.id:
        raise HTTPException(400, "Cannot follow yourself")
    following = await toggle_follow(db, current_user.id, target.id)
    return {"following": following, "followers_count": target.followers_count}


@router.get("/api/users/{username}/following", response_class=JSONResponse)
async def check_following(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.book_service import is_following
    target = await get_user_by_username(db, username)
    if not target:
        raise HTTPException(404)
    following = await is_following(db, current_user.id, target.id)
    return {"following": following}


# ── Subscribe to book (JSON API) ──────────────────────────────────────────────
@router.post("/api/books/{book_id}/subscribe", response_class=JSONResponse)
async def subscribe_book(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.book_service import toggle_book_subscription, get_book_by_id
    book = await get_book_by_id(db, book_id)
    if not book:
        raise HTTPException(404)
    subscribed = await toggle_book_subscription(db, current_user.id, book_id)
    return {"subscribed": subscribed}


# ── Subscriptions page ────────────────────────────────────────────────────────
@router.get("/subscriptions", response_class=HTMLResponse)
async def subscriptions_page(
    request: Request,
    tab: str = Query("authors"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.social import Follow, BookSubscription
    from app.models.book import Book
    from sqlalchemy.orm import selectinload

    followed_users = []
    subscribed_books = []

    if tab == "authors":
        # Get users that current_user follows
        result = await db.execute(
            select(Follow).where(Follow.follower_id == current_user.id)
            .order_by(Follow.created_at.desc())
        )
        follows = result.scalars().all()
        if follows:
            target_ids = [f.following_id for f in follows]
            from app.models.user import User as UserModel
            users_result = await db.execute(
                select(UserModel).where(UserModel.id.in_(target_ids))
            )
            followed_users = users_result.scalars().all()
    else:
        # Get books that current_user is subscribed to
        result = await db.execute(
            select(BookSubscription).where(BookSubscription.user_id == current_user.id)
            .order_by(BookSubscription.created_at.desc())
        )
        subs = result.scalars().all()
        if subs:
            book_ids = [s.book_id for s in subs]
            books_result = await db.execute(
                select(Book).where(Book.id.in_(book_ids))
                .options(selectinload(Book.author))
            )
            subscribed_books = books_result.scalars().all()

    return templates.TemplateResponse("user/subscriptions.html", {
        "request": request,
        "current_user": current_user,
        "tab": tab,
        "followed_users": followed_users,
        "subscribed_books": subscribed_books,
    })