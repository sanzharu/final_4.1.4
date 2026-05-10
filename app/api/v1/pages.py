from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_optional
from app.db.session import get_db
from app.services.book_service import list_books, list_genres

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    from app.templates_env import templates
    featured, _ = await list_books(db, page=1, per_page=6, featured_only=True)
    popular, _ = await list_books(db, page=1, per_page=8, order_by="views_count")
    newest, _ = await list_books(db, page=1, per_page=8, order_by="created_at")
    genres = await list_genres(db)
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "current_user": current_user,
            "featured": featured,
            "popular": popular,
            "newest": newest,
            "genres": genres,
        },
    )



@router.get("/about", response_class=HTMLResponse)
async def about_page(
    request: Request,
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    from app.templates_env import templates
    return templates.TemplateResponse(
        "pages/about.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/rules", response_class=HTMLResponse)
async def rules_page(
    request: Request,
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    from app.templates_env import templates
    return templates.TemplateResponse(
        "pages/rules.html",
        {"request": request, "current_user": current_user},
    )
