"""
SSR page routes — rendered with Jinja2 templates.
These are the "web" pages; API endpoints are separate.
"""
from fastapi import APIRouter, Request, HTTPException, Query, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.core.deps import DB, OptionalUser, CurrentUser
from app.core.templates import templates, paginate
from app.core.security import generate_csrf_token, verify_csrf_token, generate_session_id
from app.core.config import settings
from app.models.book import Book, Genre, BookStatus
from app.models.user import User, UserRole
from app.models.interaction import Like
from app.models.social import Bookmark, Review
from app.schemas.user import UserCreate, UserLogin, UserUpdate, PasswordChange
from app.schemas.book import BookCreate, BookUpdate, ChapterCreate
from app.services import book_service, user_service

router = APIRouter(tags=["pages"])

GENRES = [
    {"id": "fantasy",    "label": "Фэнтези",      "icon": ""},
    {"id": "romance",    "label": "Романтика",     "icon": ""},
    {"id": "detective",  "label": "Детектив",      "icon": ""},
    {"id": "scifi",      "label": "Фантастика",    "icon": ""},
    {"id": "horror",     "label": "Ужасы",         "icon": ""},
    {"id": "historical", "label": "Исторический",  "icon": ""},
    {"id": "adventure",  "label": "Приключения",   "icon": ""},
    {"id": "thriller",   "label": "Триллер",       "icon": ""},
    {"id": "drama",      "label": "Драма",         "icon": ""},
    {"id": "mystery",    "label": "Мистика",       "icon": ""},
]


def _csrf(request: Request) -> str:
    session_id = request.cookies.get("session_id", generate_session_id())
    return generate_csrf_token(session_id)


def _check_csrf(request: Request, token: str) -> None:
    session_id = request.cookies.get("session_id", "")
    if not verify_csrf_token(token, session_id):
        raise HTTPException(status_code=403, detail="Недействительный CSRF токен")


#  Catalog redirect (legacy URL) 
@router.get("/catalog")
async def catalog_redirect(request: Request):
    from starlette.datastructures import URL
    # Forward query params to /books
    qs = request.url.query
    target = f"/books?{qs}" if qs else "/books"
    return RedirectResponse(target, status_code=301)


#  Home 
@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: DB, user: OptionalUser):
    featured, _ = await book_service.list_books(db, is_featured=True, sort="views", page=1, page_size=5)
    if not featured:
        featured, _ = await book_service.list_books(db, sort="views", page=1, page_size=5)
    popular, _ = await book_service.list_books(db, sort="views", page=1, page_size=6)
    new_books, _ = await book_service.list_books(db, sort="new", page=1, page_size=6)
    trending, _ = await book_service.list_books(db, sort="likes", page=1, page_size=5)

    books_total = (await db.execute(select(func.count(Book.id)).where(Book.is_published == True))).scalar_one()
    users_total = (await db.execute(select(func.count(User.id)))).scalar_one()
    chapters_total = (await db.execute(select(func.sum(Book.chapters_count)))).scalar_one() or 0

    # Genre stats - cannot use await inside list comprehension
    genre_counts = []
    for g in GENRES:
        count = (await db.execute(
            select(func.count(Book.id)).where(Book.genre == g["id"], Book.is_published == True)
        )).scalar_one()
        genre_counts.append(count)
    max_books = max(genre_counts, default=1)

    genre_stats = []
    for g, count in zip(GENRES[:6], genre_counts[:6]):
        genre_stats.append({**g, "count": count, "pct": round(count / max(max_books, 1) * 100)})

    return templates.TemplateResponse("index.html", {
        "request": request, "current_user": user,
        "csrf_token": _csrf(request),
        "featured": featured, "popular_books": popular,
        "new_books": new_books, "trending": trending,
        "genres": GENRES, "genre_stats": genre_stats,
        "stats": {"books": f"{books_total:,}", "users": f"{users_total:,}", "chapters": f"{int(chapters_total):,}"},
    })


#  Catalog 
@router.get("/books", response_class=HTMLResponse)
async def catalog(
    request: Request, db: DB, user: OptionalUser,
    genre: Optional[str] = None, q: Optional[str] = None,
    sort: str = "views", order: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    # Support both 'sort' and 'order' param names; 'search' and 'q'
    active_order = order or sort or "views_count"
    search_term = search or q or ""

    # Map order param to service sort values
    order_map = {
        "views_count": "views", "avg_rating": "rating",
        "created_at": "new", "last_chapter_at": "updated",
        "views": "views", "rating": "rating", "new": "new", "updated": "updated",
        "likes": "likes",
    }
    service_sort = order_map.get(active_order, "views")

    genre_enum = None
    if genre:
        try:
            genre_enum = Genre(genre)
        except ValueError:
            pass

    books, total = await book_service.list_books(
        db, genre=genre_enum, search=search_term or None, sort=service_sort,
        page=page, page_size=24
    )
    pagination = paginate(total, page, 24)

    # Build genres list with fields catalog.html expects
    genres_with_meta = [
        {"id": g["id"], "slug": g["id"], "name": g["label"], "label": g["label"], "emoji": g["icon"], "icon": g["icon"]}
        for g in GENRES
    ]

    return templates.TemplateResponse("books/catalog.html", {
        "request": request, "current_user": user,
        "books": books, "genres": genres_with_meta,
        "active_genre": genre, "active_order": active_order,
        "search": search_term,
        "total": total, "page": page, "pages": pagination["pages"],
        "pagination": pagination,
    })


#  Book detail 
@router.get("/books/{slug}", response_class=HTMLResponse)
async def book_detail(request: Request, slug: str, db: DB, user: OptionalUser):
    book = await book_service.get_book_by_slug(db, slug)
    if not book:
        raise HTTPException(status_code=404)
    if not book.is_published and (not user or (user.id != book.author_id and not user.is_staff)):
        raise HTTPException(status_code=403, detail="Книга не опубликована")
    if user:
        await book_service.increment_views(db, book.id)

    from sqlalchemy.orm import selectinload
    chapters_result = await db.execute(
        select(__import__('app.models.chapter', fromlist=['Chapter']).Chapter)
        .where(__import__('app.models.chapter', fromlist=['Chapter']).Chapter.book_id == book.id,
               __import__('app.models.chapter', fromlist=['Chapter']).Chapter.is_published == True)
        .order_by(__import__('app.models.chapter', fromlist=['Chapter']).Chapter.number)
    )
    chapters = list(chapters_result.scalars().all())
    reviews = await book_service.get_book_reviews(db, book.id)
    user_liked = user_bookmarked = user_reviewed = False
    if user:
        user_liked = await book_service.user_liked(db, user.id, book.id)
        user_bookmarked = await book_service.user_bookmarked(db, user.id, book.id)
        rev = await db.execute(select(Review).where(Review.user_id == user.id, Review.book_id == book.id))
        user_reviewed = rev.scalar_one_or_none() is not None

    return templates.TemplateResponse("books/detail.html", {
        "request": request, "current_user": user, "csrf_token": _csrf(request),
        "book": book, "chapters": chapters, "reviews": reviews,
        "user_liked": user_liked, "user_bookmarked": user_bookmarked, "user_reviewed": user_reviewed,
    })


#  Reader 
@router.get("/books/{slug}/read/{num}", response_class=HTMLResponse)
async def reader(request: Request, slug: str, num: int, db: DB, user: OptionalUser):
    from app.models.chapter import Chapter as Ch
    book = await book_service.get_book_by_slug(db, slug)
    if not book or not book.is_published:
        raise HTTPException(status_code=404)
    chapter = await book_service.get_chapter(db, book.id, num)
    if not chapter:
        raise HTTPException(status_code=404)

    prev_ch = await book_service.get_chapter(db, book.id, num - 1) if num > 1 else None
    next_ch = await book_service.get_chapter(db, book.id, num + 1)
    progress = round(num / book.chapters_count * 100) if book.chapters_count else 100

    await book_service.increment_views(db, book.id)
    return templates.TemplateResponse("books/reader.html", {
        "request": request, "current_user": user,
        "book": book, "chapter": chapter,
        "prev_chapter": prev_ch, "next_chapter": next_ch, "progress": progress,
    })


#  Auth pages 
@router.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request, user: OptionalUser):
    if user:
        return RedirectResponse("/")
    return templates.TemplateResponse("auth/login.html", {
        "request": request, "current_user": None, "csrf_token": _csrf(request),
        "error": None, "email": None,
        "google_oauth": bool(settings.GOOGLE_CLIENT_ID),
        "github_oauth": bool(settings.GITHUB_CLIENT_ID),
    })


@router.post("/auth/login", response_class=HTMLResponse)
async def login_submit(
    request: Request, response: Response, db: DB,
    email: str = Form(...), password: str = Form(...), csrf_token: str = Form(...),
):
    _check_csrf(request, csrf_token)
    from app.core.security import create_access_token, create_refresh_token
    user = await user_service.authenticate_user(db, email, password)
    if not user:
        return templates.TemplateResponse("auth/login.html", {
            "request": request, "current_user": None, "csrf_token": _csrf(request),
            "error": "Неверный email или пароль", "email": email,
            "google_oauth": bool(settings.GOOGLE_CLIENT_ID),
            "github_oauth": bool(settings.GITHUB_CLIENT_ID),
        }, status_code=401)
    if user.is_banned:
        return templates.TemplateResponse("auth/login.html", {
            "request": request, "current_user": None, "csrf_token": _csrf(request),
            "error": f"Аккаунт заблокирован: {user.ban_reason}", "email": email,
            "google_oauth": False, "github_oauth": False,
        }, status_code=403)
    COOKIE_OPTS = dict(httponly=True, secure=settings.APP_ENV == "production", samesite="lax")
    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id)
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie("access_token", access, max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, **COOKIE_OPTS)
    resp.set_cookie("refresh_token", refresh, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, **COOKIE_OPTS)
    session_id = generate_session_id()
    resp.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return resp


@router.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request, user: OptionalUser):
    if user:
        return RedirectResponse("/")
    return templates.TemplateResponse("auth/register.html", {
        "request": request, "current_user": None, "csrf_token": _csrf(request), "error": None,
    })


@router.post("/auth/register", response_class=HTMLResponse)
async def register_submit(
    request: Request, response: Response, db: DB,
    username: str = Form(...), email: str = Form(...),
    password: str = Form(...), password2: str = Form(...),
    display_name: str = Form(""), csrf_token: str = Form(...),
):
    _check_csrf(request, csrf_token)
    ctx = {"request": request, "current_user": None, "csrf_token": _csrf(request)}
    if password != password2:
        return templates.TemplateResponse("auth/register.html", {**ctx, "error": "Пароли не совпадают", "username": username, "email": email}, status_code=400)
    from app.schemas.user import UserCreate as UC
    try:
        data = UC(username=username, email=email, password=password, display_name=display_name or None)
    except Exception as e:
        return templates.TemplateResponse("auth/register.html", {**ctx, "error": str(e), "username": username, "email": email}, status_code=400)
    try:
        user = await user_service.create_user(db, data)
    except HTTPException as e:
        return templates.TemplateResponse("auth/register.html", {**ctx, "error": e.detail, "username": username, "email": email}, status_code=400)
    from app.core.security import create_access_token, create_refresh_token
    COOKIE_OPTS = dict(httponly=True, secure=settings.APP_ENV == "production", samesite="lax")
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie("access_token", create_access_token(user.id, user.role.value), max_age=1800, **COOKIE_OPTS)
    resp.set_cookie("refresh_token", create_refresh_token(user.id), max_age=2592000, **COOKIE_OPTS)
    session_id = generate_session_id()
    resp.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return resp


@router.get("/auth/logout")
async def logout(response: Response):
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie("access_token")
    resp.delete_cookie("refresh_token")
    return resp


#  Profile 
@router.get("/profile/{username}", response_class=HTMLResponse)
async def profile(request: Request, username: str, db: DB, user: OptionalUser):
    profile_user = await user_service.get_user_by_username(db, username)
    if not profile_user:
        raise HTTPException(status_code=404)
    books, _ = await book_service.list_books(db, author_id=profile_user.id, sort="views", page=1, page_size=12)
    return templates.TemplateResponse("user/profile.html", {
        "request": request, "current_user": user, "profile_user": profile_user, "books": books,
    })


@router.get("/library", response_class=HTMLResponse)
async def library(request: Request, db: DB, user: CurrentUser):
    from sqlalchemy.orm import selectinload
    bms = await db.execute(
        select(Bookmark).where(Bookmark.user_id == user.id).options(
            selectinload(Bookmark.book).selectinload(Book.author)
        )
    )
    bookmarks = [bm.book for bm in bms.scalars().all()]
    return templates.TemplateResponse("user/library.html", {
        "request": request, "current_user": user, "books": bookmarks,
    })


#  Settings 
@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: CurrentUser):
    return templates.TemplateResponse("user/settings.html", {
        "request": request, "current_user": user, "csrf_token": _csrf(request),
        "success": None, "error": None,
    })


@router.post("/settings/profile")
async def settings_profile(
    request: Request, db: DB, user: CurrentUser,
    display_name: str = Form(""), bio: str = Form(""), csrf_token: str = Form(...),
):
    _check_csrf(request, csrf_token)
    data = UserUpdate(display_name=display_name or None, bio=bio or None)
    await user_service.update_user(db, user, data)
    return templates.TemplateResponse("user/settings.html", {
        "request": request, "current_user": user, "csrf_token": _csrf(request),
        "success": "Профиль обновлён", "error": None,
    })


@router.post("/settings/password")
async def settings_password(
    request: Request, db: DB, user: CurrentUser,
    current_password: str = Form(...), new_password: str = Form(...), csrf_token: str = Form(...),
):
    _check_csrf(request, csrf_token)
    try:
        await user_service.change_password(db, user, current_password, new_password)
        success, error = "Пароль изменён", None
    except HTTPException as e:
        success, error = None, e.detail
    return templates.TemplateResponse("user/settings.html", {
        "request": request, "current_user": user, "csrf_token": _csrf(request),
        "success": success, "error": error,
    })


@router.post("/settings/become-author")
async def become_author(request: Request, db: DB, user: CurrentUser, csrf_token: str = Form(...)):
    _check_csrf(request, csrf_token)
    user.role = UserRole.AUTHOR
    await db.flush()
    return RedirectResponse("/settings", status_code=302)


#  Write 
@router.get("/write", response_class=HTMLResponse)
async def write_page(request: Request, user: CurrentUser):
    return templates.TemplateResponse("books/write.html", {
        "request": request, "current_user": user, "csrf_token": _csrf(request),
        "book": None, "genres": GENRES, "show_chapter_editor": True,
    })


@router.post("/write")
async def write_submit(
    request: Request, db: DB, user: CurrentUser,
    title: str = Form(...), description: str = Form(""), genre: str = Form(...),
    status: str = Form("draft"), cover_emoji: str = Form(""),
    is_adult: bool = Form(False), content: str = Form(""),
    chapter_title: str = Form("Глава 1"), chapter_number: str = Form(""),
    csrf_token: str = Form(...),
):
    _check_csrf(request, csrf_token)
    try:
        genre_enum = Genre(genre)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный жанр")
    data = BookCreate(title=title, description=description or None, genre=genre_enum,
                      cover_emoji=cover_emoji, is_adult=is_adult)
    book = await book_service.create_book(db, user, data)
    if content.strip():
        ch_data = ChapterCreate(title=chapter_title or "Глава 1", content=content)
        await book_service.create_chapter(db, book, ch_data, user)
    return RedirectResponse(f"/write/{book.slug}/edit", status_code=302)


@router.get("/write/{slug}/edit", response_class=HTMLResponse)
async def edit_page(request: Request, slug: str, db: DB, user: CurrentUser):
    book = await book_service.get_book_by_slug(db, slug)
    if not book or (book.author_id != user.id and not user.is_staff):
        raise HTTPException(status_code=403)
    return templates.TemplateResponse("books/write.html", {
        "request": request, "current_user": user, "csrf_token": _csrf(request),
        "book": book, "genres": GENRES, "show_chapter_editor": True,
        "chapter": None, "chapter_content": "",
    })


#  Admin 
@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: DB, user: CurrentUser, tab: str = "users"):
    if not user.is_staff:
        raise HTTPException(status_code=403)
    books_c = (await db.execute(select(func.count(Book.id)))).scalar_one()
    users_c = (await db.execute(select(func.count(User.id)))).scalar_one()
    pub_c = (await db.execute(select(func.count(Book.id)).where(Book.is_published == True))).scalar_one()
    reviews_c = (await db.execute(select(func.count(Review.id)))).scalar_one()
    admin_stats = [
        {"icon": "", "label": "Пользователей", "value": users_c},
        {"icon": "", "label": "Книг всего", "value": books_c},
        {"icon": "", "label": "Опубликовано", "value": pub_c},
        {"icon": "", "label": "Отзывов", "value": reviews_c},
    ]
    if tab == "users":
        result = await db.execute(select(User).order_by(User.created_at.desc()).limit(50))
        items = list(result.scalars().all())
    elif tab == "books":
        from sqlalchemy.orm import selectinload
        result = await db.execute(select(Book).options(selectinload(Book.author)).order_by(Book.created_at.desc()).limit(50))
        items = list(result.scalars().all())
    else:
        items = []
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request, "current_user": user, "csrf_token": _csrf(request),
        "tab": tab, "items": items, "admin_stats": admin_stats,
    })


@router.post("/admin/users/{user_id}/role")
async def admin_set_role(request: Request, user_id: int, db: DB, user: CurrentUser, role: str = Form(...), csrf_token: str = Form(...)):
    if not user.is_staff:
        raise HTTPException(status_code=403)
    _check_csrf(request, csrf_token)
    await user_service.set_role(db, user_id, UserRole(role))
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/users/{user_id}/ban")
async def admin_ban(request: Request, user_id: int, db: DB, user: CurrentUser, reason: str = Form(...), csrf_token: str = Form(...)):
    if not user.is_staff:
        raise HTTPException(status_code=403)
    _check_csrf(request, csrf_token)
    await user_service.ban_user(db, user_id, reason)
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/books/{book_id}/feature")
async def admin_feature(request: Request, book_id: int, db: DB, user: CurrentUser, csrf_token: str = Form(...)):
    if not user.is_staff:
        raise HTTPException(status_code=403)
    _check_csrf(request, csrf_token)
    book = await book_service.get_book_by_id(db, book_id)
    if book:
        book.is_featured = not book.is_featured
    return RedirectResponse("/admin?tab=books", status_code=302)


#  Static / Info pages 
@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request, user: OptionalUser):
    return templates.TemplateResponse("pages/about.html", {
        "request": request, "current_user": user,
    })


@router.get("/rules", response_class=HTMLResponse)
async def rules_page(request: Request, user: OptionalUser):
    return templates.TemplateResponse("pages/rules.html", {
        "request": request, "current_user": user,
    })


#  Write/new redirect 
@router.get("/write/new", response_class=HTMLResponse)
async def write_new_page(request: Request, user: CurrentUser):
    return templates.TemplateResponse("books/write.html", {
        "request": request, "current_user": user, "csrf_token": _csrf(request),
        "book": None, "genres": GENRES, "show_chapter_editor": True,
    })


#  Bookmarks (alias for library) 
@router.get("/bookmarks", response_class=HTMLResponse)
async def bookmarks_page(request: Request, db: DB, user: CurrentUser):
    from sqlalchemy.orm import selectinload
    bms = await db.execute(
        select(Bookmark).where(Bookmark.user_id == user.id).options(
            selectinload(Bookmark.book).selectinload(Book.author)
        )
    )
    bookmarks = [bm.book for bm in bms.scalars().all()]
    return templates.TemplateResponse("user/library.html", {
        "request": request, "current_user": user, "books": bookmarks,
    })


#  My books 
@router.get("/my-books", response_class=HTMLResponse)
async def my_books_page(request: Request, db: DB, user: CurrentUser):
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Book).where(Book.author_id == user.id)
        .options(selectinload(Book.author))
        .order_by(Book.created_at.desc())
    )
    all_books = list(result.scalars().all())
    published = [b for b in all_books if b.is_published]
    drafts = [b for b in all_books if not b.is_published]
    return templates.TemplateResponse("user/my_books.html", {
        "request": request, "current_user": user,
        "published": published, "drafts": drafts,
    })
