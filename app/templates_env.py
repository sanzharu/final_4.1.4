"""
Jinja2 template environment with custom filters and globals.
"""
from datetime import datetime
from typing import Optional

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


#  Custom filters 
def fmt_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}М"
    if n >= 1_000:
        return f"{n/1_000:.1f}К"
    return str(n)


def fmt_words(n: int) -> str:
    if n >= 1_000:
        return f"{n//1000}К слов"
    return f"{n} слов"


def fmt_date(dt: Optional[datetime], fmt: str = "%d.%m.%Y") -> str:
    if not dt:
        return "—"
    return dt.strftime(fmt)


def fmt_datetime(dt: Optional[datetime]) -> str:
    if not dt:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M")


def stars(rating: float) -> str:
    full = int(rating)
    half = 1 if rating - full >= 0.5 else 0
    empty = 5 - full - half
    return "" * full + "½" * half + "" * empty


def age_label(age: str) -> str:
    labels = {"G": "0+", "PG": "6+", "PG-13": "13+", "R": "16+", "NC-17": "18+"}
    return labels.get(age, age)


def role_badge(role) -> str:
    val = role.value if hasattr(role, 'value') else str(role)
    badges = {
        "admin": "администратор",
        "moderator": "модератор",
        "author": "автор",
        "reader": "читатель",
    }
    return badges.get(val, val)


# Register filters
templates.env.filters["fmt_number"] = fmt_number
templates.env.filters["fmt_words"] = fmt_words
templates.env.filters["fmt_date"] = fmt_date
templates.env.filters["fmt_datetime"] = fmt_datetime
templates.env.filters["stars"] = stars
templates.env.filters["age_label"] = age_label
templates.env.filters["role_badge"] = role_badge

def urlencode_filter(s) -> str:
    from urllib.parse import quote_plus
    return quote_plus(str(s))

templates.env.filters["urlencode"] = urlencode_filter

# Globals
templates.env.globals["site_name"] = "Literary Haven"
templates.env.globals["current_year"] = datetime.now().year


def genre_label(genre) -> str:
    val = genre.value if hasattr(genre, 'value') else str(genre)
    labels = {
        "fantasy": "Фэнтези", "romance": "Романтика", "detective": "Детектив",
        "scifi": "Фантастика", "horror": "Ужасы", "historical": "Исторический",
        "adventure": "Приключения", "thriller": "Триллер", "drama": "Драма",
        "comedy": "Комедия", "mystery": "Мистика", "young_adult": "Young Adult",
    }
    return labels.get(val, val)


def status_label(status) -> str:
    val = status.value if hasattr(status, 'value') else str(status)
    labels = {
        "ongoing": "В процессе", "completed": "Завершена",
        "hiatus": "Пауза", "draft": "Черновик",
    }
    return labels.get(val, val)


templates.env.filters["genre_label"] = genre_label

import json as _json_mod
def from_json(value):
    try: return _json_mod.loads(value or '[]')
    except: return []
templates.env.filters["from_json"] = from_json
templates.env.filters["status_label"] = status_label


def fromjson(value) -> list:
    """Parse JSON string to Python object, return empty list on error."""
    if not value:
        return []
    try:
        result = _json_module.loads(value)
        return result if isinstance(result, list) else []
    except Exception:
        return []


templates.env.filters["fromjson"] = fromjson


def render_markdown(text: str) -> str:
    """Convert simple markdown to HTML. Supports **bold**, *italic*, --- separator, {{fn:N:text}} footnotes."""
    import re
    if not text:
        return ''
    # Escape HTML first
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text, flags=re.DOTALL)
    # Italic: *text* (but not **)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text, flags=re.DOTALL)
    # Scene separator: ---
    text = re.sub(r'^\s*---\s*$', '<hr style="border:none;text-align:center;margin:2rem 0;" class="scene-sep">', text, flags=re.MULTILINE)
    # Scene separator: * * *
    text = re.sub(r'^\s*\*\s*\*\s*\*\s*$', '<div style="text-align:center;letter-spacing:0.5em;color:var(--text-muted);margin:2rem 0;">* * *</div>', text, flags=re.MULTILINE)
    # Footnote markers {{fn:N:text}} → clickable tooltip superscript
    def fn_to_html(m):
        n = m.group(1)
        ft = m.group(2).replace('"', '&quot;').replace("'", '&#39;')
        return (
            f'<span class="fn-ref" data-fn="{n}" title="{ft}" '
            f'style="cursor:pointer;color:#8B7355;font-size:0.7em;vertical-align:super;'
            f'border-bottom:1px dotted #8B7355;user-select:none;" '
            f'onclick="showFnTooltip(event,\'{n}\',\'{ft}\')">[{n}]</span>'
        )
    text = re.sub(r'\{\{fn:(\d+):([^}]+)\}\}', fn_to_html, text)
    # Remove any remaining bare {{fn:...}} that didn't parse
    text = re.sub(r'\{\{fn:[^}]*\}\}', '', text)
    return text


templates.env.filters["render_md"] = render_markdown

