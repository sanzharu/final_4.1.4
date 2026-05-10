"""Admin panel routes - accessible by moderator and admin roles."""
import math
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.deps import get_current_moderator
from app.db.session import get_db
from app.models.book import Book, BookStatus
from app.models.user import User, UserRole
from app.models.social import Review, Notification
from app.services.user_service import set_role, deactivate_user, get_user_by_id
from app.services.book_service import get_book_by_id
from app.templates_env import templates

router = APIRouter(prefix="/admin", tags=["admin"])

PER_PAGE = 25


async def _notify(db: AsyncSession, user_id: int, kind: str, title: str, body: str = None, link: str = None):
    """Create a notification for a user."""
    notif = Notification(user_id=user_id, kind=kind, title=title, body=body, link=link)
    db.add(notif)
    await db.flush()


# ── Dashboard ────────────────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    book_count = (await db.execute(select(func.count()).select_from(Book))).scalar_one()
    published_count = (await db.execute(select(func.count()).select_from(Book).where(Book.is_published == True))).scalar_one()
    review_count = (await db.execute(select(func.count()).select_from(Review))).scalar_one()

    try:
        from app.models.social import Report
        report_count = (await db.execute(select(func.count()).select_from(Report).where(Report.is_resolved == False))).scalar_one()
    except Exception:
        report_count = 0

    recent_users = list((await db.execute(
        select(User).order_by(User.created_at.desc()).limit(8)
    )).scalars())
    recent_books = list((await db.execute(
        select(Book).options(joinedload(Book.author)).order_by(Book.created_at.desc()).limit(8)
    )).unique().scalars())

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request, "current_user": current_user,
        "user_count": user_count, "book_count": book_count,
        "published_count": published_count, "review_count": review_count,
        "report_count": report_count,
        "recent_users": recent_users, "recent_books": recent_books,
    })


# ── Users ─────────────────────────────────────────────────────────────────────
@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    page: int = Query(1, ge=1),
    search: str = Query(""),
    role_filter: str = Query(""),
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    q = select(User).order_by(User.created_at.desc())
    if search.strip():
        term = f"%{search.strip()}%"
        q = q.where(or_(
            User.username.ilike(term),
            User.email.ilike(term),
            User.display_name.ilike(term),
        ))
    if role_filter:
        try:
            q = q.where(User.role == UserRole(role_filter))
        except ValueError:
            pass

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    users = list((await db.execute(q.offset((page - 1) * PER_PAGE).limit(PER_PAGE))).scalars())

    return templates.TemplateResponse("admin/users.html", {
        "request": request, "current_user": current_user,
        "users": users, "total": total, "page": page,
        "pages": math.ceil(total / PER_PAGE) or 1,
        "search": search, "role_filter": role_filter,
    })


@router.post("/users/{user_id}/role")
async def set_user_role(
    user_id: int,
    role: str = Form(...),
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(403, "Только администраторы могут менять роли")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(404)
    try:
        new_role = UserRole(role)
    except ValueError:
        raise HTTPException(400, "Неверная роль")
    await set_role(db, user.id, new_role)
    await _notify(db, user.id, "role_changed", f"Ваша роль изменена на: {new_role.value}")
    return RedirectResponse(f"/admin/users?search=", status_code=302)


@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: int,
    reason: str = Form("Нарушение правил"),
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_id(db, user_id)
    if not user or user.id == current_user.id:
        raise HTTPException(400)
    user.is_banned = True
    user.ban_reason = reason
    await db.flush()
    await _notify(db, user.id, "ban", "Ваш аккаунт заблокирован", reason)
    return RedirectResponse("/admin/users", status_code=302)


@router.post("/users/{user_id}/unban")
async def unban_user(
    user_id: int,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(404)
    user.is_banned = False
    user.ban_reason = None
    await db.flush()
    await _notify(db, user.id, "unban", "Блокировка снята", "Ваш аккаунт восстановлен")
    return RedirectResponse("/admin/users", status_code=302)


@router.post("/users/{user_id}/deactivate")
async def deactivate_user_handler(
    user_id: int,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(403)
    user = await get_user_by_id(db, user_id)
    if not user or user.id == current_user.id:
        raise HTTPException(400)
    await deactivate_user(db, user.id)
    return RedirectResponse("/admin/users", status_code=302)


# ── Books ─────────────────────────────────────────────────────────────────────
@router.get("/books", response_class=HTMLResponse)
async def admin_books(
    request: Request,
    page: int = Query(1, ge=1),
    status: str = Query("published"),
    search: str = Query(""),
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    q = select(Book).options(joinedload(Book.author)).order_by(Book.created_at.desc())

    # Status filter
    if status == "moderation":
        q = q.where(Book.is_on_moderation == True)
    elif status == "published":
        q = q.where(Book.is_published == True, Book.is_on_moderation == False)
    elif status == "draft":
        q = q.where(Book.status == BookStatus.DRAFT)
    elif status == "completed":
        q = q.where(Book.status == BookStatus.COMPLETED)
    elif status == "hidden":
        q = q.where(Book.is_draft_hidden == True)
    elif status == "ongoing":
        q = q.where(Book.status == BookStatus.ONGOING, Book.is_published == True)
    else:
        # fallback to all published
        q = q.where(Book.is_published == True)

    if search.strip():
        term = f"%{search.strip()}%"
        q = q.where(Book.title.ilike(term))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    books = list((await db.execute(q.offset((page - 1) * PER_PAGE).limit(PER_PAGE))).unique().scalars())

    return templates.TemplateResponse("admin/books.html", {
        "request": request, "current_user": current_user,
        "books": books, "total": total, "page": page,
        "pages": math.ceil(total / PER_PAGE) or 1,
        "active_status": status, "search": search,
    })


@router.post("/books/{book_id}/feature")
async def toggle_featured(
    book_id: int,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    book = await get_book_by_id(db, book_id)
    if not book:
        raise HTTPException(404)
    book.is_featured = not book.is_featured
    await db.flush()
    return RedirectResponse("/admin/books", status_code=302)


@router.post("/books/{book_id}/moderation")
async def send_to_moderation(
    book_id: int,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    book = await get_book_by_id(db, book_id)
    if not book:
        raise HTTPException(404)
    book.is_on_moderation = not book.is_on_moderation
    await db.flush()
    if book.is_on_moderation:
        await _notify(db, book.author_id, "moderation", f"Книга «{book.title}» отправлена на модерацию",
                      "Пожалуйста, ознакомьтесь с правилами платформы", f"/books/{book.slug}")
    return RedirectResponse("/admin/books", status_code=302)


@router.post("/books/{book_id}/delete")
async def admin_delete_book(
    book_id: int,
    reason: str = Form("Нарушение правил платформы"),
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    book = await get_book_by_id(db, book_id)
    if not book:
        raise HTTPException(404)
    author_id = book.author_id
    title = book.title
    book.is_published = False
    book.status = BookStatus.DRAFT
    book.is_draft_hidden = True
    await db.flush()
    await _notify(db, author_id, "book_removed", f"Книга «{title}» снята с публикации", reason)
    return RedirectResponse("/admin/books", status_code=302)


@router.post("/books/{book_id}/restore")
async def admin_restore_book(
    book_id: int,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    book = await get_book_by_id(db, book_id)
    if not book:
        raise HTTPException(404)
    book.is_draft_hidden = False
    book.is_on_moderation = False
    await db.flush()
    return RedirectResponse("/admin/books", status_code=302)


# ── Reports ───────────────────────────────────────────────────────────────────
@router.get("/reports", response_class=HTMLResponse)
async def admin_reports(
    request: Request,
    page: int = Query(1, ge=1),
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    from app.models.book import Book as BookModel
    total, reports = 0, []
    error_msg = None
    try:
        from app.models.social import Report
        # First ensure table exists by doing a simple count
        count_q = select(func.count()).select_from(Report)
        total = (await db.execute(count_q)).scalar_one()
        q = (select(Report)
             .options(
                 joinedload(Report.reporter),
                 joinedload(Report.book).joinedload(BookModel.author),
             )
             .order_by(Report.created_at.desc()))
        reports = list((await db.execute(
            q.offset((page - 1) * PER_PAGE).limit(PER_PAGE)
        )).unique().scalars().all())
    except Exception as e:
        import logging
        logging.getLogger("app").error(f"Reports error: {e}", exc_info=True)
        error_msg = str(e)
        total, reports = 0, []

    return templates.TemplateResponse("admin/reports.html", {
        "request": request, "current_user": current_user,
        "reports": reports, "total": total, "page": page,
        "pages": math.ceil(total / PER_PAGE) or 1,
        "error_msg": error_msg,
    })


@router.post("/reports/{report_id}/action")
async def report_action(
    report_id: int,
    action: str = Form("resolve"),
    note: str = Form(""),
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Handle moderation actions on a report."""
    try:
        from app.models.social import Report
        result = await db.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            return RedirectResponse("/admin/reports", status_code=302)

        if action == "ban_book":
            book = await get_book_by_id(db, report.book_id)
            if book:
                book.is_published = False
                book.is_draft_hidden = True
                await db.flush()
                reason = note or "Жалоба принята модератором"
                await _notify(db, book.author_id, "book_removed",
                              f"Книга «{book.title}» снята с публикации", reason)
            report.is_resolved = True
            report.resolved_by = current_user.id

        elif action == "ban_user":
            book = await get_book_by_id(db, report.book_id)
            if book:
                user = await get_user_by_id(db, book.author_id)
                if user:
                    user.is_banned = True
                    user.ban_reason = note or "Нарушение правил платформы"
                    await db.flush()
                    await _notify(db, user.id, "ban", "Ваш аккаунт заблокирован",
                                  user.ban_reason)
            report.is_resolved = True
            report.resolved_by = current_user.id

        elif action == "warn_author":
            book = await get_book_by_id(db, report.book_id)
            if book:
                msg = note or "Ваша книга нарушает правила платформы. Пожалуйста, ознакомьтесь с правилами."
                await _notify(db, book.author_id, "moderation",
                              f"Предупреждение по книге «{book.title}»", msg,
                              f"/books/{book.slug}")
                book.is_on_moderation = True
                await db.flush()
            report.is_resolved = True
            report.resolved_by = current_user.id

        elif action == "decline":
            report.is_resolved = True
            report.resolved_by = current_user.id

        else:  # resolve
            report.is_resolved = True
            report.resolved_by = current_user.id

        await db.flush()
    except Exception as e:
        print(f"Report action error: {e}")

    return RedirectResponse("/admin/reports", status_code=302)


@router.post("/reports/{report_id}/action")
async def report_action(
    report_id: int,
    action: str = Form(...),
    note: str = Form(""),
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Handle moderator action on a report."""
    from app.models.social import Report, Notification
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(404)

    if action == "resolve":
        report.is_resolved = True
        report.resolved_by = current_user.id
        await db.flush()

    elif action == "ban_book":
        book = await get_book_by_id(db, report.book_id)
        if book:
            book.is_published = False
            book.is_draft_hidden = True
            book.status = BookStatus.DRAFT
            await db.flush()
            await _notify(db, book.author_id, "book_removed",
                f"Книга «{book.title}» снята с публикации",
                note or "Нарушение правил платформы")
        report.is_resolved = True
        report.resolved_by = current_user.id
        await db.flush()

    elif action == "ban_user":
        reporter_book = await get_book_by_id(db, report.book_id)
        if reporter_book:
            user = await get_user_by_id(db, reporter_book.author_id)
            if user:
                user.is_banned = True
                user.ban_reason = note or "Нарушение правил платформы"
                await db.flush()
                await _notify(db, user.id, "ban",
                    "Ваш аккаунт заблокирован",
                    note or "Нарушение правил платформы")
        report.is_resolved = True
        report.resolved_by = current_user.id
        await db.flush()

    elif action == "warn_author":
        book = await get_book_by_id(db, report.book_id)
        if book:
            await _notify(db, book.author_id, "warning",
                "Предупреждение от модерации",
                note or "Ваш контент нарушает правила платформы")
        report.is_resolved = True
        report.resolved_by = current_user.id
        await db.flush()

    elif action == "decline":
        report.is_resolved = True
        report.resolved_by = current_user.id
        await db.flush()

    return RedirectResponse("/admin/reports", status_code=302)


@router.post("/reports/{report_id}/reopen")
async def reopen_report(
    report_id: int,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    from app.models.social import Report
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if report:
        report.is_resolved = False
        report.resolved_by = None
        await db.flush()
    return RedirectResponse("/admin/reports", status_code=302)


# ── Reviews ───────────────────────────────────────────────────────────────────
@router.get("/reviews", response_class=HTMLResponse)
async def admin_reviews(
    request: Request,
    page: int = Query(1, ge=1),
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    q = (select(Review)
         .options(joinedload(Review.user), joinedload(Review.book))
         .order_by(Review.created_at.desc()))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    reviews = list((await db.execute(q.offset((page - 1) * PER_PAGE).limit(PER_PAGE))).unique().scalars())

    return templates.TemplateResponse("admin/reviews.html", {
        "request": request, "current_user": current_user,
        "reviews": reviews, "total": total, "page": page,
        "pages": math.ceil(total / PER_PAGE) or 1,
    })


@router.post("/reviews/{review_id}/hide")
async def hide_review(
    review_id: int,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(404)
    review.is_hidden = not review.is_hidden
    await db.flush()
    return RedirectResponse("/admin/reviews", status_code=302)


# ── Notifications API ────────────────────────────────────────────────────────
@router.get("/notifications/api")
async def get_notifications(
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import JSONResponse
    notifs = list((await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(20)
    )).scalars())
    return JSONResponse([{
        "id": n.id, "kind": n.kind, "title": n.title,
        "body": n.body, "link": n.link, "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    } for n in notifs])
