from fastapi import APIRouter
from app.api.v1 import auth, books, users, admin, pages

api_router = APIRouter()

# HTML page routes — at root level so templates can link to /catalog, /auth/login etc.
api_router.include_router(auth.router)       # /auth/login, /auth/register, /auth/logout ...
api_router.include_router(books.router)      # /catalog, /books/*, /write/*, /api/books/*
api_router.include_router(users.router)      # /profile/*, /settings, /bookmarks, /my-books
api_router.include_router(admin.router)      # /admin/*
api_router.include_router(pages.router)      # / (home page)

# ALSO register auth at /api/v1 — main.js calls /api/v1/auth/logout and /api/v1/auth/refresh
api_router.include_router(auth.router, prefix="/api/v1")
