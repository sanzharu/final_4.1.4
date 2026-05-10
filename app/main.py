"""
Literary Haven — FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.templates import templates
from app.db.base import engine, Base
from app.api.v1.router import api_router
from app.middleware.security import SecurityHeadersMiddleware, RequestTimingMiddleware

logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import all models so Alembic/SQLAlchemy sees them
    from app.models import User, Book, Chapter, Like, Bookmark, Review, Tag, BookTag, OAuthAccount, ReadingProgress, Notification, RefreshToken
    # Create tables if they don't exist yet (safe: does not drop existing tables)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Literary Haven starting up...")
    yield
    await engine.dispose()
    logger.info("Literary Haven shutdown complete.")


app = FastAPI(
    title="Literary Haven API",
    version="1.0.0",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware (order matters: outermost = last added) ────────────────────────
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, max_age=86400)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router)


# ── Error handlers ────────────────────────────────────────────────────────────
@app.exception_handler(404)
async def not_found(request: Request, exc: HTTPException):
    from fastapi.responses import JSONResponse
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return templates.TemplateResponse("errors/404.html", {"request": request, "current_user": None}, status_code=404)


@app.exception_handler(500)
async def server_error(request: Request, exc: Exception):
    from fastapi.responses import JSONResponse
    logger.exception("Unhandled exception: %s", exc)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Internal server error"}, status_code=500)
    return templates.TemplateResponse("errors/500.html", {"request": request, "current_user": None}, status_code=500)


@app.exception_handler(403)
async def forbidden(request: Request, exc: HTTPException):
    from fastapi.responses import JSONResponse
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": exc.detail}, status_code=403)
    return templates.TemplateResponse("errors/404.html", {"request": request, "current_user": None, "error": exc.detail}, status_code=403)


@app.exception_handler(401)
async def unauthorized(request: Request, exc: HTTPException):
    from fastapi.responses import JSONResponse, RedirectResponse
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": exc.detail}, status_code=401)
    return RedirectResponse(f"/auth/login?next={request.url.path}", status_code=302)
