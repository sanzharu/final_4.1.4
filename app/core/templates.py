"""Jinja2 template engine setup with global helpers."""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from fastapi.templating import Jinja2Templates
from datetime import datetime
import math

BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ── Template globals & filters ────────────────────────────────────────────────
env = templates.env

def fmt_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}М"
    if n >= 1_000:
        return f"{n/1_000:.1f}К"
    return str(n)

def fmt_date(dt: datetime) -> str:
    if not dt:
        return ""
    months = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]
    return f"{dt.day} {months[dt.month-1]} {dt.year}"

def genre_label(genre: str) -> str:
    labels = {
        "fantasy": "Фэнтези", "romance": "Романтика", "detective": "Детектив",
        "scifi": "Фантастика", "horror": "Ужасы", "historical": "Исторический",
        "adventure": "Приключения", "thriller": "Триллер", "drama": "Драма",
        "comedy": "Комедия", "mystery": "Мистика", "young_adult": "Young Adult",
    }
    return labels.get(genre, genre)

def status_label(status: str) -> str:
    labels = {
        "ongoing": "В процессе", "completed": "Завершена",
        "hiatus": "Пауза", "draft": "Черновик",
    }
    return labels.get(status, status)

def star_rating(rating: float) -> str:
    full = int(rating)
    return "★" * full + "☆" * (5 - full)

def paginate(total: int, page: int, page_size: int) -> dict:
    pages = math.ceil(total / page_size) if total else 1
    return {
        "total": total, "page": page, "pages": pages,
        "has_prev": page > 1, "has_next": page < pages,
        "prev": page - 1, "next": page + 1,
    }

env.filters["fmt_number"] = fmt_number
env.filters["fmt_date"] = fmt_date
env.filters["genre_label"] = genre_label
env.filters["status_label"] = status_label
env.filters["star_rating"] = star_rating
env.globals["paginate"] = paginate


def fmt_words(n) -> str:
    if not n:
        return "0 слов"
    n = int(n)
    if n >= 1000:
        return f"{n // 1000}К слов"
    return f"{n} слов"


env.filters["fmt_words"] = fmt_words

from datetime import datetime as _dt
env.globals["site_name"] = "Literary Haven"
env.globals["current_year"] = _dt.now().year

def age_label(age_rating) -> str:
    labels = {"G": "G", "PG": "PG", "PG13": "PG-13", "PG-13": "PG-13", "R": "R", "NC17": "NC-17", "NC-17": "NC-17"}
    if age_rating is None:
        return ""
    val = age_rating.value if hasattr(age_rating, 'value') else str(age_rating)
    return labels.get(val, val)

def fmt_datetime(dt: datetime) -> str:
    if not dt:
        return ""
    months = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]
    return f"{dt.day} {months[dt.month-1]} {dt.year}, {dt.hour:02d}:{dt.minute:02d}"

def role_badge(role) -> str:
    labels = {"reader": "Читатель", "author": "Автор", "moderator": "Модератор", "admin": "Администратор"}
    val = role.value if hasattr(role, 'value') else str(role)
    return labels.get(val, val)

def stars(rating) -> str:
    if not rating:
        return "☆☆☆☆☆"
    r = round(float(rating))
    return "★" * r + "☆" * (5 - r)

env.filters["age_label"] = age_label
env.filters["fmt_datetime"] = fmt_datetime
env.filters["role_badge"] = role_badge
env.filters["stars"] = stars
