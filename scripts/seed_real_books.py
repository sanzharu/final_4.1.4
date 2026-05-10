#!/usr/bin/env python3
"""
Seed the database with real books.

Russian books  → Kaggle «Russian Literature» dataset (data/ruslit/prose/)
English books  → Project Gutenberg (downloaded at runtime)

Run from project root:
    python scripts/seed_real_books.py
"""

import asyncio, re, sys, os, time, random, html as html_mod, zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import text as sa_text, delete as sa_delete
from app.db.base import engine, AsyncSessionLocal, Base
import app.models
from app.models.user import User, UserRole
from app.models.book import Book, BookStatus, Genre
from app.models.chapter import Chapter
from app.models.tag import Tag, BookTag
from app.models.social import Review, Bookmark
from app.core.security import hash_password

random.seed(42)

# ─── Dataset path ────────────────────────────────────────────────────────────
_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SCRIPT_DIR)
DATASET_DIR  = os.path.join(_PROJECT_DIR, "data", "ruslit")   # extracted dataset

# ══════════════════════════════════════════════════════════════════════════════
# AUTHORS
# ══════════════════════════════════════════════════════════════════════════════

RUSSIAN_AUTHORS = [
    {"username": "leo_tolstoy",        "email": "leo_tolstoy@classic.lib",
     "display_name": "Лев Толстой",
     "bio": "Лев Николаевич Толстой (1828–1910) — граф, русский писатель, один из величайших романистов мировой литературы. Автор «Войны и мира», «Анны Карениной», «Воскресения»."},
    {"username": "fyodor_dostoevsky",  "email": "dostoevsky@classic.lib",
     "display_name": "Фёдор Достоевский",
     "bio": "Фёдор Михайлович Достоевский (1821–1881) — русский писатель и мыслитель. Автор «Преступления и наказания», «Идиота», «Братьев Карамазовых»."},
    {"username": "alexander_pushkin",  "email": "pushkin@classic.lib",
     "display_name": "Александр Пушкин",
     "bio": "Александр Сергеевич Пушкин (1799–1837) — русский поэт, прозаик и драматург, основоположник современного русского литературного языка."},
    {"username": "nikolai_gogol",      "email": "gogol@classic.lib",
     "display_name": "Николай Гоголь",
     "bio": "Николай Васильевич Гоголь (1809–1852) — русский прозаик, драматург и публицист. Автор «Мёртвых душ», «Ревизора», «Вечеров на хуторе близ Диканьки»."},
    {"username": "ivan_turgenev",      "email": "turgenev@classic.lib",
     "display_name": "Иван Тургенев",
     "bio": "Иван Сергеевич Тургенев (1818–1883) — русский писатель-реалист. Автор романа «Отцы и дети» и «Записок охотника»."},
    {"username": "anton_chekhov",      "email": "chekhov@classic.lib",
     "display_name": "Антон Чехов",
     "bio": "Антон Павлович Чехов (1860–1904) — русский писатель и драматург. Признан одним из величайших мастеров короткого рассказа в мировой литературе."},
    {"username": "mikhail_lermontov",  "email": "lermontov@classic.lib",
     "display_name": "Михаил Лермонтов",
     "bio": "Михаил Юрьевич Лермонтов (1814–1841) — русский поэт и прозаик. Автор «Героя нашего времени» — первого психологического романа в русской литературе."},
    {"username": "maxim_gorky",        "email": "gorky@classic.lib",
     "display_name": "Максим Горький",
     "bio": "Алексей Максимович Пешков (1868–1936), псевдоним Максим Горький — русский и советский писатель, основоположник социалистического реализма."},
    {"username": "valery_bryusov",     "email": "bryusov@classic.lib",
     "display_name": "Валерий Брюсов",
     "bio": "Валерий Яковлевич Брюсов (1873–1924) — русский поэт и прозаик, один из основоположников русского символизма. Автор исторического романа «Огненный ангел» и фантастических рассказов."},
    {"username": "alexander_herzen",   "email": "herzen@classic.lib",
     "display_name": "Александр Герцен",
     "bio": "Александр Иванович Герцен (1812–1870) — русский публицист, писатель и философ. Автор романа «Кто виноват?» и мемуаров «Былое и думы». Основатель Вольной русской типографии в Лондоне."},
]

ENGLISH_AUTHORS = [
    {"username": "lewis_carroll",      "email": "lewis_carroll@classic.lib",    "display_name": "Lewis Carroll",
     "bio": "Charles Lutwidge Dodgson (1832–1898), pen name Lewis Carroll. English author and mathematician. Best known for Alice's Adventures in Wonderland."},
    {"username": "jane_austen",        "email": "jane_austen@classic.lib",      "display_name": "Jane Austen",
     "bio": "Jane Austen (1775–1817). English novelist whose works critique the British landed gentry. Author of Pride and Prejudice, Emma, Sense and Sensibility."},
    {"username": "arthur_conan_doyle", "email": "conan_doyle@classic.lib",      "display_name": "Arthur Conan Doyle",
     "bio": "Sir Arthur Conan Doyle (1859–1930). British author and physician. Creator of Sherlock Holmes, one of the most famous fictional characters ever."},
    {"username": "bram_stoker",        "email": "bram_stoker@classic.lib",      "display_name": "Bram Stoker",
     "bio": "Abraham Stoker (1847–1912). Irish author of Dracula (1897), the quintessential vampire novel."},
    {"username": "hg_wells",           "email": "hg_wells@classic.lib",         "display_name": "H.G. Wells",
     "bio": "Herbert George Wells (1866–1946). English writer, father of science fiction. Author of The Time Machine, The War of the Worlds, The Invisible Man."},
    {"username": "rl_stevenson",       "email": "rl_stevenson@classic.lib",     "display_name": "Robert Louis Stevenson",
     "bio": "Robert Louis Stevenson (1850–1894). Scottish novelist. Author of Treasure Island, Kidnapped, and Strange Case of Dr Jekyll and Mr Hyde."},
    {"username": "mary_shelley",       "email": "mary_shelley@classic.lib",     "display_name": "Mary Shelley",
     "bio": "Mary Wollstonecraft Shelley (1797–1851). English novelist. Author of Frankenstein (1818), the first true science fiction novel."},
    {"username": "charles_dickens",    "email": "charles_dickens@classic.lib",  "display_name": "Charles Dickens",
     "bio": "Charles Dickens (1812–1870). Greatest Victorian novelist. Author of Oliver Twist, A Tale of Two Cities, Great Expectations, David Copperfield."},
    {"username": "oscar_wilde",        "email": "oscar_wilde@classic.lib",      "display_name": "Oscar Wilde",
     "bio": "Oscar Wilde (1854–1900). Irish poet and playwright. Best known for The Picture of Dorian Gray and his legendary wit."},
    {"username": "mark_twain",         "email": "mark_twain@classic.lib",       "display_name": "Mark Twain",
     "bio": "Samuel Langhorne Clemens (1835–1910). American writer and humorist. Author of The Adventures of Tom Sawyer and Huckleberry Finn."},
    {"username": "jules_verne",        "email": "jules_verne@classic.lib",      "display_name": "Jules Verne",
     "bio": "Jules Verne (1828–1905). French novelist and pioneer of science fiction. Author of 20,000 Leagues Under the Sea and Around the World in Eighty Days."},
    {"username": "charlotte_bronte",   "email": "charlotte_bronte@classic.lib", "display_name": "Charlotte Brontë",
     "bio": "Charlotte Brontë (1816–1855). English novelist, author of Jane Eyre. Her sisters Emily and Anne were also celebrated novelists."},
    {"username": "lf_baum",            "email": "lf_baum@classic.lib",          "display_name": "L. Frank Baum",
     "bio": "Lyman Frank Baum (1856–1919). American author best known for The Wonderful Wizard of Oz and its thirteen sequels."},
    {"username": "jack_london",        "email": "jack_london@classic.lib",      "display_name": "Jack London",
     "bio": "John Griffith London (1876–1916). American novelist. Author of The Call of the Wild, White Fang, and The Sea-Wolf."},
    {"username": "alexandre_dumas",    "email": "dumas@classic.lib",            "display_name": "Alexandre Dumas",
     "bio": "Alexandre Dumas (1802–1870). French writer. Author of The Three Musketeers and The Count of Monte Cristo."},
]

ALL_AUTHORS = RUSSIAN_AUTHORS + ENGLISH_AUTHORS

# ══════════════════════════════════════════════════════════════════════════════
# TAGS
# ══════════════════════════════════════════════════════════════════════════════

ALL_TAGS = {
    "Классика": "klassika", "Романтика": "romantika",
    "Приключение": "priklyuchenie", "Мистика": "mistika",
    "Психология": "psihologiya", "Семья": "semya",
    "Дружба": "druzhba", "Вампиры": "vampiry",
    "Исторический": "istoricheskiy", "Россия XIX век": "rossiya-xix",
    "Апокалипсис": "apokalipsis", "Космос": "kosmos",
    "Путешествие": "puteshestvie", "Выживание": "vyzhivanie",
    "Предательство": "predatelstvo", "Детектив": "detektiv",
    "Сатира": "satira", "Реализм": "realizm",
    "Символизм": "simvolizm", "Антиутопия": "antiutopiya",
    "Магия": "magiya", "Дети": "deti",
    "Война": "voyna", "Любовь": "lyubov",
    "Преступление": "prestuplenie", "Природа": "priroda",
    "Философия": "filosofiya", "Юмор": "yumor",
    "Трагедия": "tragediya", "Средневековье": "srednevekove",
    "Фэнтези": "fentezi", "Постапокалипсис": "postapokalipsis",
}

# ══════════════════════════════════════════════════════════════════════════════
# DATASET LOADER
# ══════════════════════════════════════════════════════════════════════════════
#
# Reads directly from archive.zip (bypasses Windows cp437 filename mangling).
# Falls back to extracted files on disk if zip not found.
# ─────────────────────────────────────────────────────────────────────────────

_ZIP_INDEX: dict | None = None   # normalized_title → ZipInfo
_ZIP_PATH:  str  | None = None


def _find_archive_zip() -> str | None:
    """Search several likely locations for archive.zip."""
    candidates = [
        os.path.join(_PROJECT_DIR, "data", "archive.zip"),
        os.path.join(_PROJECT_DIR, "archive.zip"),
        os.path.join(os.path.dirname(_PROJECT_DIR), "archive.zip"),
        os.path.join(os.path.dirname(_PROJECT_DIR), "data", "archive.zip"),
        # If user runs from inside the 'project' subdirectory
        os.path.join(os.path.dirname(_PROJECT_DIR), "project", "data", "archive.zip"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def _zip_real_name(info) -> str:
    """Decode cp437-mangled UTF-8 Cyrillic filename stored in the zip."""
    try:
        # Zip created on Linux/Mac stores UTF-8 bytes but labels them as cp437
        return info.filename.encode('cp437').decode('utf-8')
    except Exception:
        return info.filename


def _normalize_title(s: str) -> str:
    """Lowercase + strip all spaces and punctuation for fuzzy matching."""
    s = s.lower()
    s = re.sub(r"[\s.\-\u2013\u2014\u2116#()\[\]\u00ab\u00bb'\"]+", '', s)
    return s


def _build_zip_index(zpath: str) -> dict:
    """Map {normalized_basename_without_ext → ZipInfo} for every .txt in the zip."""
    import zipfile as _zf
    index = {}
    with _zf.ZipFile(zpath) as z:
        for info in z.infolist():
            real = _zip_real_name(info)
            if not real.endswith('.txt'):
                continue
            base = os.path.splitext(os.path.basename(real))[0]
            key  = _normalize_title(base)
            if key and key not in index:
                index[key] = info
    return index


def _get_zip_index():
    global _ZIP_INDEX, _ZIP_PATH
    if _ZIP_INDEX is None:
        _ZIP_PATH = _find_archive_zip()
        if _ZIP_PATH:
            _ZIP_INDEX = _build_zip_index(_ZIP_PATH)
            print(f"   📦  Dataset index: {len(_ZIP_INDEX)} files  ({_ZIP_PATH})")
        else:
            _ZIP_INDEX = {}
            print("   ⚠️  archive.zip not found — will try filesystem only")
    return _ZIP_INDEX


def load_from_dataset(relative_path: str) -> str | None:
    """
    Load a text file from the Russian Literature dataset.
    relative_path example: 'prose/Tolstoy/Анна Каренина.txt'

    1. Read from archive.zip  (reliable, bypasses OS filename encoding)
    2. Walk filesystem        (fallback)
    """
    import zipfile as _zf

    base = os.path.splitext(os.path.basename(relative_path))[0]
    key  = _normalize_title(base)

    # ── 1. archive.zip ────────────────────────────────────────────────────
    idx = _get_zip_index()
    if key in idx and _ZIP_PATH:
        try:
            with _zf.ZipFile(_ZIP_PATH) as z:
                raw  = z.read(idx[key])
                text = raw.decode('utf-8', errors='replace')
                if len(text) > 500:
                    return text
        except Exception:
            pass

    # ── 2. Filesystem walk ─────────────────────────────────────────────────
    roots = [
        DATASET_DIR,
        os.path.join(_PROJECT_DIR, "data"),
        _PROJECT_DIR,
        os.path.join(_PROJECT_DIR, "project", "data", "ruslit"),
        os.path.join(_PROJECT_DIR, "project", "data"),
    ]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                if not fname.endswith('.txt'):
                    continue
                fname_key = _normalize_title(os.path.splitext(fname)[0])
                if fname_key == key:
                    try:
                        text = open(os.path.join(dirpath, fname),
                                    encoding='utf-8', errors='replace').read()
                        if len(text) > 500:
                            return text
                    except Exception:
                        pass
    return None
# ══════════════════════════════════════════════════════════════════════════════
# HTTP / FETCH HELPERS  (only needed for English Gutenberg books)
# ══════════════════════════════════════════════════════════════════════════════

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LibraryBot/1.0)"}


def fetch_url(url: str, timeout: int = 60) -> bytes | None:
    for attempt in range(3):
        try:
            with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=timeout) as c:
                r = c.get(url)
            if r.status_code == 200:
                return r.content
            if r.status_code == 404:
                return None
        except Exception as exc:
            if attempt == 2:
                print(f"          ✗ fetch error: {exc}")
            else:
                time.sleep(1)
    return None


def decode_bytes(data: bytes) -> str:
    if data[:3] == b'\xef\xbb\xbf':
        return data[3:].decode('utf-8', errors='replace')
    for enc in ['utf-8', 'cp1251', 'latin-1']:
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode('utf-8', errors='replace')


# ══════════════════════════════════════════════════════════════════════════════
# TEXT CLEANING
# ══════════════════════════════════════════════════════════════════════════════

def _extract_footnotes(text: str) -> tuple[str, dict]:
    """
    Extract the footnotes section from a dataset file and return:
    - text with footnote section removed
    - dict {footnote_number: footnote_text}
    """
    footnotes: dict[str, str] = {}

    # Find notes/Примечания section
    _NOTES_RE = re.compile(
        r'\n\s*(?:notes|Примечания|ПРИМЕЧАНИЯ|Комментарии|КОММЕНТАРИИ'
        r'|Приложение|Об авторе|ОБ АВТОРЕ)\s*\n',
        re.IGNORECASE
    )
    m = _NOTES_RE.search(text)
    if not m or m.start() < len(text) * 0.5:
        return text, footnotes

    notes_text = text[m.end():]
    text = text[:m.start()]

    # Parse individual footnotes: digit on its own line, then text
    # Format: \n1\n\nText of footnote...\n\n2\n\n...
    note_blocks = re.split(r'\n\s*(\d{1,4})\s*\n', notes_text)
    i = 0
    while i < len(note_blocks):
        chunk = note_blocks[i].strip()
        if chunk.isdigit() and i + 1 < len(note_blocks):
            fn_num = chunk
            fn_text = note_blocks[i + 1].strip()
            # Clean the footnote text
            fn_text = re.sub(r'\s+', ' ', fn_text).strip()
            if fn_text and len(fn_text) > 2:
                footnotes[fn_num] = fn_text
            i += 2
        else:
            i += 1

    return text, footnotes


def _embed_footnotes(text: str, footnotes: dict) -> str:
    """
    Replace [N] markers in text with {{fn:N:footnote text}} markers
    that the frontend can render as tooltips.
    """
    if not footnotes:
        # Just remove bare [N] markers
        text = re.sub(r'\[\d{1,4}\]', '', text)
        return text

    def replace_fn(m):
        n = m.group(1)
        if n in footnotes:
            # Escape any special chars in footnote text
            fn_safe = footnotes[n].replace('}}', ') ')
            return f'{{{{fn:{n}:{fn_safe}}}}}'
        return ''  # remove if no matching footnote

    text = re.sub(r'\[(\d{1,4})\]', replace_fn, text)
    return text


def clean_russian_text(text: str) -> str:
    """Fix encoding artifacts, HTML entities, typography in Russian dataset texts."""
    # ── 1. Control-char and cp1252 fixes ────────────────────────────────────
    _FIXES = {
        '\x85': '\u2026', '\x91': '\u2018', '\x92': '\u2019',
        '\x93': '\u201c', '\x94': '\u201d', '\x96': '\u2013', '\x97': '\u2014',
        '\xa0': ' ', '\xad': '', '\r': '',
    }
    for bad, good in _FIXES.items():
        text = text.replace(bad, good)

    # ── 2. Decode HTML numeric entities  &#224; → à  ────────────────────────
    def _decode_entity(m):
        try:
            return chr(int(m.group(1)))
        except (ValueError, OverflowError):
            return m.group(0)
    text = re.sub(r'&#(\d+);', _decode_entity, text)
    text = re.sub(r'&amp;#(\d+);', _decode_entity, text)
    text = (text
            .replace('&amp;', '&').replace('&lt;', '<')
            .replace('&gt;', '>').replace('&quot;', '"').replace('&apos;', "'"))

    # ── 3. Extract footnotes and embed as tooltip markers ────────────────────
    text, footnotes = _extract_footnotes(text)
    text = _embed_footnotes(text, footnotes)

    # ── 4. em-dash fixup ─────────────────────────────────────────────────────
    text = re.sub(r'(?<=[А-ЯЁа-яё\w])\s*--\s*', ' — ', text)
    text = re.sub(r'(?m)^-\s', '— ', text)

    # ── 5. Strip dataset header (author / title lines) ───────────────────────
    lines = text.splitlines()
    if (len(lines) > 5
            and lines[0].strip()
            and len(lines[0].strip()) < 80
            and not re.match(r'\s*(?:Глава|Часть|[IVXLCDM]+\s*$|\d+\s*$)', lines[0])):
        skip = 0
        for i in range(min(8, len(lines))):
            s = lines[i].strip()
            if len(s) > 100:
                skip = i; break
            if re.match(r'(?:Глава|Часть|Книга|[IVXLCDM]{1,5}\.?)\s', s):
                skip = i; break
        if 0 < skip <= 6:
            text = '\n'.join(lines[skip:])

    # ── 6. Ensure proper paragraph separation ────────────────────────────────
    if '\n\n' not in text[:2000] and '\n' in text[:2000]:
        text = re.sub(r'\n(?!\n)', '\n\n', text)

    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text.strip()


def clean_english_text(text: str) -> str:
    """Remove Gutenberg boilerplate and fix English text formatting."""
    # Strip Gutenberg header/footer
    import re as _re
    m = _re.search(r'\*{3}\s*START OF (?:THIS |THE )?PROJECT GUTENBERG[^\n]*\*{3}',
                  text, _re.IGNORECASE)
    if m: text = text[m.end():]
    m = _re.search(r'\*{3}\s*END OF (?:THIS |THE )?PROJECT GUTENBERG[^\n]*\*{3}',
                  text, _re.IGNORECASE)
    if m: text = text[:m.start()]
    m = _re.search(r'\nEnd of (?:the )?Project Gutenberg', text, _re.IGNORECASE)
    if m: text = text[:m.start()]

    # Decode HTML entities
    def _dec(mc):
        try: return chr(int(mc.group(1)))
        except: return mc.group(0)
    text = _re.sub(r'&#(\d+);', _dec, text)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')

    # Remove meta lines at the top
    lines_t = text.splitlines()
    meta_re = _re.compile(
        r'^(Title|Author|Release Date|Posting Date|Last Updated|Language|'
        r'Character set|Credits|Produced by|Transcribed by|Prepared by|'
        r'Note:|This e-?book|Edition|Translator|Illustrat)\s*[:\[]',
        _re.IGNORECASE)
    start = 0
    for i, ln in enumerate(lines_t[:80]):
        if meta_re.match(ln.strip()):
            start = i + 1
    text = '\n'.join(lines_t[start:])

    # Fix spaced-out chapter headings like "C H A P T E R   I"
    text = _re.sub(r'\b([A-Z])\s([A-Z])\s([A-Z])', r'\1\2\3', text)
    # Remove illustration tags, footnote markers [1], page numbers alone on a line
    text = _re.sub(r'\[Illustration[^\]]*\]', '', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\[\d{1,3}\]', '', text)
    text = _re.sub(r'(?m)^\s*\d{1,4}\s*$', '', text)
    # Remove underscored italics _word_
    text = _re.sub(r'_([\w\s,;.\']+?)_', r'\1', text)
    # Remove TOC
    toc = _re.search(r'(?m)^(TABLE OF CONTENTS|CONTENTS)\s*$', text, _re.IGNORECASE)
    if toc:
        after = text[toc.start():]
        prose = _re.search(r'\n\n[A-Z][a-z].{80,}', after)
        if prose:
            text = text[:toc.start()] + after[prose.start():]
    # Strip end-of-book appendices
    _end = _re.search(
        r'\n\s*(?:FOOTNOTES|NOTES|APPENDIX|BIBLIOGRAPHY|INDEX)\s*\n',
        text, _re.IGNORECASE)
    if _end and _end.start() > len(text) * 0.5:
        text = text[:_end.start()]
    # Ensure paragraph spacing
    if '\n\n' not in text[:3000] and '\n' in text[:3000]:
        text = _re.sub(r'\n(?!\n)', '\n\n', text)
    text = _re.sub(r'\r', '', text)
    text = _re.sub(r'[ \t]{2,}', ' ', text)
    text = _re.sub(r'\n{4,}', '\n\n\n', text)
    return text.strip()

# ══════════════════════════════════════════════════════════════════════════════
# GUTENBERG
# ══════════════════════════════════════════════════════════════════════════════

GUTENBERG_PATTERNS = [
    "https://gutenberg.org/cache/epub/{id}/pg{id}.txt",
    "https://www.gutenberg.org/files/{id}/{id}-0.txt",
    "https://www.gutenberg.org/files/{id}/{id}.txt",
]


def fetch_gutenberg(gid: int) -> str | None:
    for tmpl in GUTENBERG_PATTERNS:
        raw = fetch_url(tmpl.format(id=gid))
        if raw and len(raw) > 10000:
            return clean_english_text(decode_bytes(raw))
    return None


# ══════════════════════════════════════════════════════════════════════════════
# CHAPTER PARSING
# ══════════════════════════════════════════════════════════════════════════════

_RU_ORDINALS = {
    'первая':1,'первый':1,'первое':1,'вторая':2,'второй':2,'второе':2,
    'третья':3,'третий':3,'третье':3,'четвёртая':4,'четвертая':4,
    'четвёртый':4,'пятая':5,'пятый':5,'шестая':6,'шестой':6,
    'седьмая':7,'седьмой':7,'восьмая':8,'восьмой':8,'девятая':9,'девятый':9,
    'десятая':10,'десятый':10,'одиннадцатая':11,'двенадцатая':12,
    'тринадцатая':13,'четырнадцатая':14,'пятнадцатая':15,
    'шестнадцатая':16,'семнадцатая':17,'восемнадцатая':18,
    'девятнадцатая':19,'двадцатая':20,
}


def roman_to_int(s: str) -> int:
    v = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    s = s.upper().strip()
    total = prev = 0
    for ch in reversed(s):
        n = v.get(ch, 0)
        total += n if n >= prev else -n
        prev = n
    return total


def num_str_to_int(s: str) -> int:
    s = s.strip().lower()
    if s.isdigit(): return int(s)
    if re.fullmatch(r'[ivxlcdm]+', s, re.IGNORECASE):
        v = roman_to_int(s)
        if v: return v
    return _RU_ORDINALS.get(s, 0)


EN_CHAPTER_PATTERNS = [
    # "  CHAPTER I", "Chapter 12", "Chapter ONE  — optional same-line title"
    r'(?m)^\s*(?:CHAPTER|Chapter)\s+([IVXLCDM]+|\d+)(?:[ \t.:—-]+([^\n]+?))?[ \t]*$',
    # Bare roman numeral on its own line: "  IV  " or "  IV."
    r'(?m)^\s*([IVXLCDM]{2,})\.?[ \t]*$',
]
RU_CHAPTER_PATTERNS = [
    # "Глава первая", "ГЛАВА I", "Глава 5. Заголовок" — title only on same line
    r'(?m)^\s*(?:ГЛАВА|Глава)\s+([IVXLCDM]+|\d+|[а-яёА-ЯЁ][а-яёА-ЯЁ]+)(?:[ \t.:—-]+([^\n]+?))?[ \t]*$',
    # "Часть первая", "Книга вторая", "Раздел I"
    r'(?m)^\s*(?:ЧАСТЬ|Часть|КНИГА|Книга|РАЗДЕЛ|Раздел)\s+([IVXLCDM]+|\d+|[а-яёА-ЯЁ][а-яёА-ЯЁ]+)(?:[ \t.:—-]+([^\n]+?))?[ \t]*$',
    # Bare roman numeral: "   III   " or "  V."
    r'(?m)^\s*([IVXLCDM]{1,6})\.?[ \t]*$',
    # Bare arabic numeral: "   12   " or "  7."
    r'(?m)^\s*(\d{1,3})\.?[ \t]*$',
    # "* 5 *" style
    r'(?m)^\s*\*\s*(\d+)\s*\*[ \t]*$',
]


def parse_chapters(text: str, is_russian: bool = False,
                   max_ch: int = 25, min_words: int = 200) -> list[dict]:
    """
    Split text into chapters.
    Strategy:
    1. Try all heading patterns.
    2. Filter consecutive matches that are TOC entries (< 50 words between them).
    3. Pick the pattern that finds the most valid chapters with avg >= min_avg_words.
    4. After splitting: remove sub-chapter roman numerals from content.
    5. Fall back to equal-size chunks if no pattern qualifies.
    """
    patterns = RU_CHAPTER_PATTERNS if is_russian else EN_CHAPTER_PATTERNS
    # Words between two consecutive chapter headings below this = TOC entry, skip it
    toc_threshold = 50  # very tight — only removes true TOC lines (< 1 paragraph)

    def filter_toc(ms: list) -> list:
        """Remove matches that are clearly TOC entries (< toc_threshold words after)."""
        if len(ms) < 2:
            return ms
        result = []
        for i, m in enumerate(ms):
            nxt = ms[i + 1].start() if i + 1 < len(ms) else len(text)
            words_after = len(text[m.end():nxt].split())
            if words_after >= toc_threshold:
                result.append(m)
        # Safeguard: if we filtered too aggressively, return original
        return result if len(result) >= 2 else ms

    def avg_words_between(ms: list) -> float:
        if len(ms) < 2:
            return 0.0
        counts = [len(text[ms[i].end():ms[i + 1].start()].split())
                  for i in range(len(ms) - 1)]
        return sum(counts) / len(counts) if counts else 0.0

    best: list = []
    best_score: float = 0.0
    # Minimum average words per chapter — Russian chapters are longer
    min_avg_words = 200 if is_russian else 100

    for pat in patterns:
        try:
            ms = list(re.finditer(pat, text, re.MULTILINE))
        except re.error:
            continue
        if len(ms) < 2:
            continue
        ms_real = filter_toc(ms)
        if len(ms_real) < 2:
            continue
        avg = avg_words_between(ms_real)
        # Prefer the pattern with most chapters AND adequate average word count
        score = len(ms_real) if avg >= min_avg_words else 0
        if score > 0 and (score > best_score or (score == best_score and avg > avg_words_between(best))):
            best = ms_real
            best_score = score

    if len(best) < 2:
        return _chunk(text, max_ch, min_words, is_russian)

    # Build chapter list — always renumber 1, 2, 3...
    result = []
    for i, m in enumerate(best):
        start = m.end()
        end = best[i + 1].start() if i + 1 < len(best) else len(text)
        raw_content = text[start:end].strip()

        # Remove sub-chapter roman numerals standing alone on a line
        raw_content = re.sub(r'(?m)^\s*[IVXLCDM]{1,6}\.?\s*$\n?', '', raw_content)
        # Ensure proper paragraph spacing
        if '\n\n' not in raw_content[:1000] and '\n' in raw_content[:1000]:
            raw_content = re.sub(r'\n(?!\n)', '\n\n', raw_content)
        raw_content = re.sub(r'\n{4,}', '\n\n\n', raw_content).strip()

        words = len(raw_content.split())
        if words < min_words:
            continue

        seq_num = len(result) + 1
        gs = m.groups()
        title_s = (gs[1] or '').strip() if len(gs) > 1 else ''
        if re.fullmatch(r'[IVXLCDM]{1,6}\.?|\d{1,3}', title_s, re.IGNORECASE):
            title_s = ''
        label = f"Глава {seq_num}" if is_russian else f"Chapter {seq_num}"
        if title_s:
            label = f"{label}. {title_s}"
        label = label[:295]
        result.append({"number": seq_num, "title": label, "content": raw_content,
                       "words_count": words})
        if len(result) >= max_ch:
            break

    return result


def _chunk(text: str, max_chunks: int, min_words: int, is_russian: bool) -> list[dict]:
    words = text.split()
    size = max(min_words, len(words) // max_chunks + 1)
    result = []
    for i, chunk in enumerate([words[j:j + size] for j in range(0, len(words), size)][:max_chunks], 1):
        if len(chunk) < min_words:
            continue
        label = f"Часть {i}" if is_russian else f"Part {i}"
        result.append({"number": i, "title": label[:295],
                       "content": ' '.join(chunk), "words_count": len(chunk)})
    return result


def make_slug(title: str) -> str:
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[\s_]+', '-', slug)
    return re.sub(r'-+', '-', slug).strip('-')[:200] or 'book'


# ══════════════════════════════════════════════════════════════════════════════
# BOOK CATALOGUE
# source: "dataset" → read from local ruslit dataset (Russian)
# source: "gutenberg" → download from Project Gutenberg (English)
# ══════════════════════════════════════════════════════════════════════════════

BOOKS = [

    # ══════════════════════════════════════════════════════════════
    # RUSSIAN BOOKS — Kaggle «Russian Literature» dataset
    # ══════════════════════════════════════════════════════════════

    # ── Толстой ───────────────────────────────────────────────────
    {"source":"dataset","dataset_path":"prose/Tolstoy/Анна Каренина.txt","is_russian":True,
     "title":"Анна Каренина","author_username":"leo_tolstoy",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Трагическая история Анны Карениной, полюбившей офицера Вронского, переплетается с нравственными исканиями Лёвина. Один из величайших романов мировой литературы о любви, браке и нравственном законе.",
     "cover_emoji":"🌹","is_adult":False,"is_featured":True,
     "tags":["Классика","Романтика","Трагедия","Россия XIX век","Любовь"],"views_count":198000,"likes_count":16400,"rating":4.90},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Война и мир. Том 1.txt","is_russian":True,
     "title":"Война и мир. Том 1","author_username":"leo_tolstoy",
     "genre":Genre.HISTORICAL,"status":BookStatus.COMPLETED,
     "description":"Первый том грандиозной эпопеи: 1805 год, светские салоны Петербурга, Аустерлицкое сражение. Юный Пьер Безухов и Андрей Болконский ищут своё место в жизни на фоне наполеоновских войн.",
     "cover_emoji":"⚔️","is_adult":False,"is_featured":True,
     "tags":["Классика","Исторический","Война","Россия XIX век"],"views_count":167000,"likes_count":13800,"rating":4.92},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Война и мир. Том 2.txt","is_russian":True,
     "title":"Война и мир. Том 2","author_username":"leo_tolstoy",
     "genre":Genre.HISTORICAL,"status":BookStatus.COMPLETED,
     "description":"1806–1812 годы. Мирная жизнь чередуется с войной. Наташа Ростова выходит в свет. Андрей Болконский переживает потери и возрождение. Пьер ищет смысл в масонстве.",
     "cover_emoji":"🕊️","is_adult":False,"is_featured":False,
     "tags":["Классика","Исторический","Война","Романтика","Россия XIX век"],"views_count":148000,"likes_count":12200,"rating":4.90},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Война и мир. Том 3.txt","is_russian":True,
     "title":"Война и мир. Том 3","author_username":"leo_tolstoy",
     "genre":Genre.HISTORICAL,"status":BookStatus.COMPLETED,
     "description":"1812 год. Вторжение Наполеона, Бородинское сражение, пожар Москвы. Судьбы главных героев в огне Отечественной войны. Кульминация великой эпопеи.",
     "cover_emoji":"🔥","is_adult":False,"is_featured":False,
     "tags":["Классика","Исторический","Война","Трагедия","Россия XIX век"],"views_count":154000,"likes_count":12800,"rating":4.91},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Война и мир. Том 4.txt","is_russian":True,
     "title":"Война и мир. Том 4","author_username":"leo_tolstoy",
     "genre":Genre.HISTORICAL,"status":BookStatus.COMPLETED,
     "description":"Финал эпопеи: изгнание Наполеона, развязка судеб всех героев, эпилог с философскими рассуждениями об истории и свободе воли.",
     "cover_emoji":"🌅","is_adult":False,"is_featured":False,
     "tags":["Классика","Исторический","Война","Россия XIX век","Философия"],"views_count":139000,"likes_count":11400,"rating":4.89},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Воскресение.txt","is_russian":True,
     "title":"Воскресение","author_username":"leo_tolstoy",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Князь Нехлюдов узнаёт среди подсудимых девушку, которую соблазнил в юности, и отправляется за ней в Сибирь. Последний великий роман Толстого об искуплении и несправедливости закона.",
     "cover_emoji":"🕊️","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Философия","Россия XIX век"],"views_count":84000,"likes_count":6700,"rating":4.77},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Детство.txt","is_russian":True,
     "title":"Детство","author_username":"leo_tolstoy",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Первое произведение Толстого. Десятилетний Николенька Иртеньев прощается с детством, покидая родовое гнездо. Начало великой автобиографической трилогии.",
     "cover_emoji":"📚","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Семья","Россия XIX век"],"views_count":72000,"likes_count":5800,"rating":4.68},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Отрочество.txt","is_russian":True,
     "title":"Отрочество","author_username":"leo_tolstoy",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Вторая часть трилогии. Николенька взрослеет, переезжает в Москву и впервые сталкивается с социальным неравенством и жестокостью мира.",
     "cover_emoji":"📖","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Семья","Россия XIX век"],"views_count":58000,"likes_count":4500,"rating":4.62},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Юность.txt","is_russian":True,
     "title":"Юность","author_username":"leo_tolstoy",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Завершающая часть трилогии. Николенька поступает в университет, мечтает о нравственном совершенстве и открывает мир взрослых со всеми его противоречиями.",
     "cover_emoji":"🌱","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Семья","Россия XIX век"],"views_count":61000,"likes_count":4900,"rating":4.65},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Смерть Ивана Ильича.txt","is_russian":True,
     "title":"Смерть Ивана Ильича","author_username":"leo_tolstoy",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Чиновник Иван Ильич, прожив «правильную» жизнь, смертельно заболевает и впервые задаётся вопросом: правильно ли он жил? Одна из сильнейших повестей о смысле существования.",
     "cover_emoji":"⚖️","is_adult":False,"is_featured":False,
     "tags":["Классика","Философия","Трагедия","Россия XIX век"],"views_count":89000,"likes_count":7200,"rating":4.82},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Крейцерова соната.txt","is_russian":True,
     "title":"Крейцерова соната","author_username":"leo_tolstoy",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"В ночном поезде пассажир исповедуется: он убил жену из ревности. Беспощадная повесть о браке и страсти, запрещённая цензурой при жизни автора.",
     "cover_emoji":"🎻","is_adult":True,"is_featured":False,
     "tags":["Классика","Трагедия","Психология","Россия XIX век"],"views_count":76000,"likes_count":6100,"rating":4.74},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Казаки.txt","is_russian":True,
     "title":"Казаки","author_username":"leo_tolstoy",
     "genre":Genre.ADVENTURE,"status":BookStatus.COMPLETED,
     "description":"Молодой московский аристократ Оленин уезжает на Кавказ и попадает в станицу вольных казаков. Повесть о столкновении цивилизованного и природного человека.",
     "cover_emoji":"🏔️","is_adult":False,"is_featured":False,
     "tags":["Классика","Исторический","Война","Природа","Россия XIX век"],"views_count":72000,"likes_count":5800,"rating":4.77},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Хаджи-Мурат.txt","is_russian":True,
     "title":"Хаджи-Мурат","author_username":"leo_tolstoy",
     "genre":Genre.HISTORICAL,"status":BookStatus.COMPLETED,
     "description":"Легендарный чеченский воин Хаджи-Мурат переходит на сторону русских, надеясь спасти семью. Суровая повесть о достоинстве, свободе и гибели непокорного духа.",
     "cover_emoji":"⚔️","is_adult":True,"is_featured":False,
     "tags":["Классика","Исторический","Война","Россия XIX век","Трагедия"],"views_count":86000,"likes_count":7000,"rating":4.85},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Семейное счастье.txt","is_russian":True,
     "title":"Семейное счастье","author_username":"leo_tolstoy",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"История любви молодой помещицы и пожилого соседа от пылкого романтизма до спокойного семейного счастья. Ранняя повесть Толстого о природе любви и брака.",
     "cover_emoji":"🏡","is_adult":False,"is_featured":False,
     "tags":["Классика","Романтика","Семья","Россия XIX век","Любовь"],"views_count":54000,"likes_count":4300,"rating":4.70},

    {"source":"dataset","dataset_path":"prose/Tolstoy/Отец Сергий.txt","is_russian":True,
     "title":"Отец Сергий","author_username":"leo_tolstoy",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Блестящий гвардейский офицер Касатский уходит в монастырь, став отцом Сергием. Но слава праведника оборачивается новым искушением. Повесть о гордыне, смирении и поиске Бога.",
     "cover_emoji":"✝️","is_adult":False,"is_featured":False,
     "tags":["Классика","Философия","Психология","Россия XIX век"],"views_count":67000,"likes_count":5400,"rating":4.78},

    # ── Достоевский ───────────────────────────────────────────────
    {"source":"dataset","dataset_path":"prose/Dostoevsky/Братья Карамазовы.txt","is_russian":True,
     "title":"Братья Карамазовы","author_username":"fyodor_dostoevsky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Три брата связаны убийством отца. Последний роман Достоевского — грандиозная сумма его мировоззрения, трактат о Боге, свободе и братской любви.",
     "cover_emoji":"✝️","is_adult":True,"is_featured":True,
     "tags":["Классика","Философия","Преступление","Россия XIX век"],"views_count":156000,"likes_count":12800,"rating":4.92},

    {"source":"dataset","dataset_path":"prose/Dostoevsky/Идиот.txt","is_russian":True,
     "title":"Идиот","author_username":"fyodor_dostoevsky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Князь Мышкин — «положительно прекрасный человек» — возвращается в петербургское общество и своей добротой разрушает судьбы окружающих. Роман о невозможности идеала в падшем мире.",
     "cover_emoji":"😇","is_adult":False,"is_featured":True,
     "tags":["Классика","Психология","Трагедия","Россия XIX век","Философия"],"views_count":142000,"likes_count":11500,"rating":4.88},

    {"source":"dataset","dataset_path":"prose/Dostoevsky/Бесы.txt","is_russian":True,
     "title":"Бесы","author_username":"fyodor_dostoevsky",
     "genre":Genre.THRILLER,"status":BookStatus.COMPLETED,
     "description":"Группа революционеров-нигилистов совершает террористическое убийство. Жёсткий роман-пророчество о разрушительной силе безбожного радикализма.",
     "cover_emoji":"🔥","is_adult":True,"is_featured":False,
     "tags":["Классика","Психология","Преступление","Россия XIX век","Философия"],"views_count":108000,"likes_count":8900,"rating":4.83},

    {"source":"dataset","dataset_path":"prose/Dostoevsky/Бедные люди.txt","is_russian":True,
     "title":"Бедные люди","author_username":"fyodor_dostoevsky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Переписка мелкого чиновника Макара Девушкина и бедной девушки Вареньки. Дебютный роман Достоевского — первый голос «маленького человека» в русской литературе.",
     "cover_emoji":"✉️","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Россия XIX век","Трагедия"],"views_count":68000,"likes_count":5400,"rating":4.65},

    {"source":"dataset","dataset_path":"prose/Dostoevsky/Белые ночи.txt","is_russian":True,
     "title":"Белые ночи","author_username":"fyodor_dostoevsky",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"Мечтатель встречает в петербургские белые ночи Настеньку и четыре ночи подряд беседует с ней о жизни и любви. Трогательная повесть об одиночестве и несбыточных надеждах.",
     "cover_emoji":"🌙","is_adult":False,"is_featured":False,
     "tags":["Классика","Романтика","Россия XIX век","Трагедия","Любовь"],"views_count":112000,"likes_count":9400,"rating":4.87},

    {"source":"dataset","dataset_path":"prose/Dostoevsky/Игрок.txt","is_russian":True,
     "title":"Игрок","author_username":"fyodor_dostoevsky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Молодой учитель теряет голову от рулетки и от красавицы Полины. Роман об азарте и страсти, продиктованный за 26 дней — иначе права отошли бы издателю.",
     "cover_emoji":"🎲","is_adult":False,"is_featured":False,
     "tags":["Классика","Психология","Трагедия","Россия XIX век"],"views_count":72000,"likes_count":5700,"rating":4.69},

    {"source":"dataset","dataset_path":"prose/Dostoevsky/Записки из подполья.txt","is_russian":True,
     "title":"Записки из подполья","author_username":"fyodor_dostoevsky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Исповедь озлобленного «человека из подполья» — первый образец антигероя в мировой литературе. Достоевский разбивает просветительскую веру в разумного человека.",
     "cover_emoji":"🕳️","is_adult":False,"is_featured":False,
     "tags":["Классика","Психология","Философия","Россия XIX век"],"views_count":82000,"likes_count":6600,"rating":4.80},

    {"source":"dataset","dataset_path":"prose/Dostoevsky/Вечный муж.txt","is_russian":True,
     "title":"Вечный муж","author_username":"fyodor_dostoevsky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Чиновник Трусоцкий приходит к бывшему другу-сопернику после смерти жены. Психологическая дуэль двух мужчин — исследование ревности, унижения и странной взаимозависимости.",
     "cover_emoji":"🎩","is_adult":False,"is_featured":False,
     "tags":["Классика","Психология","Россия XIX век","Трагедия"],"views_count":64000,"likes_count":5100,"rating":4.72},

    {"source":"dataset","dataset_path":"prose/Dostoevsky/Двойник.txt","is_russian":True,
     "title":"Двойник","author_username":"fyodor_dostoevsky",
     "genre":Genre.MYSTERY,"status":BookStatus.COMPLETED,
     "description":"Чиновник Голядкин встречает своего двойника — точную копию, захватывающую его место в жизни. Ранняя повесть Достоевского о раздвоении личности и безумии.",
     "cover_emoji":"👤","is_adult":False,"is_featured":False,
     "tags":["Классика","Мистика","Психология","Россия XIX век"],"views_count":58000,"likes_count":4600,"rating":4.66},

    {"source":"dataset","dataset_path":"prose/Dostoevsky/Подросток.txt","is_russian":True,
     "title":"Подросток","author_username":"fyodor_dostoevsky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Двадцатилетний незаконнорождённый Аркадий Долгорукий ищет своё место в жизни и отца. Один из самых личных и недооценённых романов Достоевского.",
     "cover_emoji":"🧑","is_adult":False,"is_featured":False,
     "tags":["Классика","Психология","Семья","Россия XIX век"],"views_count":68000,"likes_count":5400,"rating":4.72},

    {"source":"dataset","dataset_path":"prose/Dostoevsky/Неточка Незванова.txt","is_russian":True,
     "title":"Неточка Незванова","author_username":"fyodor_dostoevsky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Незаконченный роман о девочке-сироте из петербургских трущоб. История взросления, любви и страдания — Достоевский в лучшей лирической форме.",
     "cover_emoji":"🎻","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Семья","Россия XIX век","Трагедия"],"views_count":52000,"likes_count":4100,"rating":4.67},

    {"source":"dataset","dataset_path":"prose/Dostoevsky/Униженные и оскорблённые.txt","is_russian":True,
     "title":"Унижённые и оскорблённые","author_username":"fyodor_dostoevsky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Молодой писатель наблюдает жизнь петербургских «маленьких людей» — сироты Нелли, несчастного Ихменева и его дочери Наташи. Роман о страдании и жертвенности.",
     "cover_emoji":"💔","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Россия XIX век","Трагедия","Психология"],"views_count":78000,"likes_count":6200,"rating":4.74},

    {"source":"dataset","dataset_path":"prose/Dostoevsky/Дядюшкин сон.txt","is_russian":True,
     "title":"Дядюшкин сон","author_username":"fyodor_dostoevsky",
     "genre":Genre.COMEDY,"status":BookStatus.COMPLETED,
     "description":"Провинциальная дама устраивает брак своей дочери со старым сенильным князем. Сатирическая комедия нравов, полная гоголевского гротеска.",
     "cover_emoji":"😴","is_adult":False,"is_featured":False,
     "tags":["Классика","Юмор","Сатира","Россия XIX век"],"views_count":44000,"likes_count":3500,"rating":4.61},

    {"source":"dataset","dataset_path":"prose/Dostoevsky/Село Степанчиково и его обитатели.txt","is_russian":True,
     "title":"Село Степанчиково и его обитатели","author_username":"fyodor_dostoevsky",
     "genre":Genre.COMEDY,"status":BookStatus.COMPLETED,
     "description":"Бывший приживальщик Фома Опискин захватил власть над помещичьим домом и его обитателями. Злая комедия о лицемерии, тирании и человеческой глупости.",
     "cover_emoji":"🏠","is_adult":False,"is_featured":False,
     "tags":["Классика","Юмор","Сатира","Психология","Россия XIX век"],"views_count":48000,"likes_count":3800,"rating":4.65},

    # ── Пушкин ────────────────────────────────────────────────────
    {"source":"dataset","dataset_path":"prose/Pushkin/Капитанская дочка.txt","is_russian":True,
     "title":"Капитанская дочка","author_username":"alexander_pushkin",
     "genre":Genre.HISTORICAL,"status":BookStatus.COMPLETED,
     "description":"На фоне Пугачёвского восстания — история молодого офицера Гринёва и его любви к Маше Мироновой. Исторический роман о чести, долге и милосердии.",
     "cover_emoji":"⚔️","is_adult":False,"is_featured":True,
     "tags":["Классика","Исторический","Романтика","Россия XIX век","Война"],"views_count":118000,"likes_count":9600,"rating":4.82},

    {"source":"dataset","dataset_path":"prose/Pushkin/Пиковая дама.txt","is_russian":True,
     "title":"Пиковая дама","author_username":"alexander_pushkin",
     "genre":Genre.MYSTERY,"status":BookStatus.COMPLETED,
     "description":"Офицер Германн одержим тайной трёх карт, обеспечивающих выигрыш. Мистическая повесть о роке, страсти и безумии.",
     "cover_emoji":"🃏","is_adult":False,"is_featured":False,
     "tags":["Классика","Мистика","Россия XIX век","Трагедия"],"views_count":96000,"likes_count":7800,"rating":4.79},

    {"source":"dataset","dataset_path":"prose/Pushkin/Дубровский.txt","is_russian":True,
     "title":"Дубровский","author_username":"alexander_pushkin",
     "genre":Genre.ADVENTURE,"status":BookStatus.COMPLETED,
     "description":"Обедневший дворянин Дубровский, лишившись имения, становится разбойником и влюбляется в дочь своего врага. Роман о чести, мести и несправедливости.",
     "cover_emoji":"🗡️","is_adult":False,"is_featured":False,
     "tags":["Классика","Романтика","Приключение","Россия XIX век"],"views_count":89000,"likes_count":7200,"rating":4.73},

    {"source":"dataset","dataset_path":"prose/Pushkin/Повести Белкина.txt","is_russian":True,
     "title":"Повести Белкина","author_username":"alexander_pushkin",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Пять повестей: «Выстрел», «Метель», «Гробовщик», «Станционный смотритель», «Барышня-крестьянка». Первый прозаический сборник Пушкина — образец лаконичной русской прозы.",
     "cover_emoji":"📜","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Россия XIX век"],"views_count":78000,"likes_count":6300,"rating":4.76},

    {"source":"dataset","dataset_path":"prose/Pushkin/Арап Петра Великого.txt","is_russian":True,
     "title":"Арап Петра Великого","author_username":"alexander_pushkin",
     "genre":Genre.HISTORICAL,"status":BookStatus.COMPLETED,
     "description":"Незаконченный исторический роман о прадеде Пушкина — Абраме Ганнибале при дворе Петра Великого. Живой портрет петровской эпохи.",
     "cover_emoji":"👑","is_adult":False,"is_featured":False,
     "tags":["Классика","Исторический","Россия XIX век"],"views_count":48000,"likes_count":3800,"rating":4.63},

    {"source":"dataset","dataset_path":"prose/Pushkin/История Пугачёва.txt","is_russian":True,
     "title":"История Пугачёва","author_username":"alexander_pushkin",
     "genre":Genre.HISTORICAL,"status":BookStatus.COMPLETED,
     "description":"Документальная история Пугачёвского восстания, написанная Пушкиным на основе архивных материалов. Строгая проза историка, дополняющая художественную «Капитанскую дочку».",
     "cover_emoji":"📜","is_adult":False,"is_featured":False,
     "tags":["Классика","Исторический","Война","Россия XIX век"],"views_count":52000,"likes_count":4100,"rating":4.67},

    # ── Гоголь ────────────────────────────────────────────────────
    {"source":"dataset","dataset_path":"prose/Gogol/Мёртвые души.txt","is_russian":True,
     "title":"Мёртвые души","author_username":"nikolai_gogol",
     "genre":Genre.COMEDY,"status":BookStatus.COMPLETED,
     "description":"Чиновник Чичиков ездит по России и скупает у помещиков «мёртвые души». Поэма в прозе о пороках российского общества — галерея незабываемых характеров.",
     "cover_emoji":"🪙","is_adult":False,"is_featured":True,
     "tags":["Классика","Сатира","Россия XIX век","Юмор"],"views_count":134000,"likes_count":10800,"rating":4.87},

    {"source":"dataset","dataset_path":"prose/Gogol/Ревизор.txt","is_russian":True,
     "title":"Ревизор","author_username":"nikolai_gogol",
     "genre":Genre.COMEDY,"status":BookStatus.COMPLETED,
     "description":"В провинциальный город приезжает мелкий чиновник Хлестаков. Напуганные чиновники принимают его за тайного ревизора. Величайшая комедия русской драматургии.",
     "cover_emoji":"🎭","is_adult":False,"is_featured":False,
     "tags":["Классика","Сатира","Юмор","Россия XIX век"],"views_count":109000,"likes_count":8700,"rating":4.84},

    {"source":"dataset","dataset_path":"prose/Gogol/Тарас Бульба.txt","is_russian":True,
     "title":"Тарас Бульба","author_username":"nikolai_gogol",
     "genre":Genre.HISTORICAL,"status":BookStatus.COMPLETED,
     "description":"Старый казацкий полковник ведёт сыновей на войну с поляками. Эпическая повесть о запорожском казачестве, воле и трагическом предательстве.",
     "cover_emoji":"🏇","is_adult":True,"is_featured":False,
     "tags":["Классика","Исторический","Война","Россия XIX век"],"views_count":98000,"likes_count":7900,"rating":4.78},

    {"source":"dataset","dataset_path":"prose/Gogol/Вечера на хуторе близ Диканьки.txt","is_russian":True,
     "title":"Вечера на хуторе близ Диканьки","author_username":"nikolai_gogol",
     "genre":Genre.FANTASY,"status":BookStatus.COMPLETED,
     "description":"Украинские народные сказки и фантастические истории: черти, ведьмы, влюблённые кузнецы и яркий колорит украинской ночи. Дебютный сборник Гоголя.",
     "cover_emoji":"🌙","is_adult":False,"is_featured":False,
     "tags":["Классика","Мистика","Магия","Юмор"],"views_count":83000,"likes_count":6800,"rating":4.73},

    {"source":"dataset","dataset_path":"prose/Gogol/Невский проспект.txt","is_russian":True,
     "title":"Невский проспект","author_username":"nikolai_gogol",
     "genre":Genre.MYSTERY,"status":BookStatus.COMPLETED,
     "description":"Две истории о молодых людях, увлечённых прекрасными незнакомками на Невском проспекте. Первый шедевр петербургского цикла Гоголя — о разрыве мечты и действительности.",
     "cover_emoji":"🌃","is_adult":True,"is_featured":False,
     "tags":["Классика","Мистика","Реализм","Россия XIX век"],"views_count":67000,"likes_count":5400,"rating":4.77},

    {"source":"dataset","dataset_path":"prose/Gogol/Портрет.txt","is_russian":True,
     "title":"Портрет","author_username":"nikolai_gogol",
     "genre":Genre.MYSTERY,"status":BookStatus.COMPLETED,
     "description":"Бедный художник покупает на рынке зловещий портрет ростовщика с живыми глазами — и его жизнь переворачивается. Мистическая повесть об искусстве, деньгах и душе.",
     "cover_emoji":"🖼️","is_adult":False,"is_featured":False,
     "tags":["Классика","Мистика","Символизм","Россия XIX век"],"views_count":72000,"likes_count":5800,"rating":4.75},

    {"source":"dataset","dataset_path":"prose/Gogol/Шинель.txt","is_russian":True,
     "title":"Шинель","author_username":"nikolai_gogol",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Мелкий чиновник Акакий Акакиевич копит на новую шинель. Повесть о судьбе «маленького человека» — один из самых знаменитых текстов русской литературы.",
     "cover_emoji":"🧥","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Трагедия","Россия XIX век"],"views_count":94000,"likes_count":7600,"rating":4.82},

    {"source":"dataset","dataset_path":"prose/Gogol/Нос.txt","is_russian":True,
     "title":"Нос","author_username":"nikolai_gogol",
     "genre":Genre.COMEDY,"status":BookStatus.COMPLETED,
     "description":"Коллежский асессор Ковалёв обнаруживает, что его нос сбежал и живёт самостоятельной жизнью. Абсурдная, блистательная повесть о чиновничьем тщеславии.",
     "cover_emoji":"👃","is_adult":False,"is_featured":False,
     "tags":["Классика","Юмор","Сатира","Россия XIX век"],"views_count":81000,"likes_count":6500,"rating":4.78},

    {"source":"dataset","dataset_path":"prose/Gogol/Вий.txt","is_russian":True,
     "title":"Вий","author_username":"nikolai_gogol",
     "genre":Genre.HORROR,"status":BookStatus.COMPLETED,
     "description":"Семинарист Хома Брут три ночи читает молитвы над гробом ведьмы. Самая страшная повесть Гоголя — классика русской мистической прозы.",
     "cover_emoji":"👁️","is_adult":True,"is_featured":False,
     "tags":["Классика","Мистика","Магия","Трагедия"],"views_count":88000,"likes_count":7100,"rating":4.80},

    {"source":"dataset","dataset_path":"prose/Gogol/Записки сумасшедшего.txt","is_russian":True,
     "title":"Записки сумасшедшего","author_username":"nikolai_gogol",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Дневник мелкого чиновника Поприщина, постепенно сходящего с ума. Один из первых психологических монологов в русской литературе — трагикомический и пронзительный.",
     "cover_emoji":"📓","is_adult":False,"is_featured":False,
     "tags":["Классика","Психология","Юмор","Россия XIX век"],"views_count":64000,"likes_count":5100,"rating":4.76},

    # ── Тургенев ──────────────────────────────────────────────────
    {"source":"dataset","dataset_path":"prose/Turgenev/Отцы и дети.txt","is_russian":True,
     "title":"Отцы и дети","author_username":"ivan_turgenev",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Нигилист Базаров приезжает в поместье и входит в конфликт со старшим поколением. Роман, породивший слово «нигилизм» и выразивший раскол русского общества 1860-х.",
     "cover_emoji":"🌿","is_adult":False,"is_featured":True,
     "tags":["Классика","Реализм","Россия XIX век","Философия"],"views_count":128000,"likes_count":10200,"rating":4.85},

    {"source":"dataset","dataset_path":"prose/Turgenev/Дворянское гнездо.txt","is_russian":True,
     "title":"Дворянское гнездо","author_username":"ivan_turgenev",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"Лаврецкий возвращается в родное гнездо и влюбляется в Лизу Калитину. Тургеневский роман о несостоявшемся счастье и русском долге.",
     "cover_emoji":"🍂","is_adult":False,"is_featured":False,
     "tags":["Классика","Романтика","Россия XIX век","Трагедия"],"views_count":87000,"likes_count":6900,"rating":4.77},

    {"source":"dataset","dataset_path":"prose/Turgenev/Записки охотника.txt","is_russian":True,
     "title":"Записки охотника","author_username":"ivan_turgenev",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Двадцать пять очерков о помещиках и крестьянах. Книга, которая ускорила отмену крепостного права. Тонкая лирическая проза с острым социальным видением.",
     "cover_emoji":"🌲","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Природа","Россия XIX век"],"views_count":76000,"likes_count":6200,"rating":4.79},

    {"source":"dataset","dataset_path":"prose/Turgenev/Вешние воды.txt","is_russian":True,
     "title":"Вешние воды","author_username":"ivan_turgenev",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"Молодой русский Санин влюбляется в итальянскую красавицу Джемму, но роковая встреча с богатой авантюристкой перевернёт всё. Повесть о любви, слабости и раскаянии.",
     "cover_emoji":"💧","is_adult":False,"is_featured":False,
     "tags":["Классика","Романтика","Россия XIX век","Трагедия","Любовь"],"views_count":72000,"likes_count":5800,"rating":4.76},

    {"source":"dataset","dataset_path":"prose/Turgenev/Первая любовь.txt","is_russian":True,
     "title":"Первая любовь","author_username":"ivan_turgenev",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"Шестнадцатилетний Владимир влюбляется в свою соседку — своевольную красавицу Зинаиду. Но тайна её сердца оказывается жестокой. Самая пронзительная повесть о первой любви.",
     "cover_emoji":"🌺","is_adult":False,"is_featured":False,
     "tags":["Классика","Романтика","Россия XIX век","Трагедия","Любовь"],"views_count":94000,"likes_count":7800,"rating":4.83},

    {"source":"dataset","dataset_path":"prose/Turgenev/Муму.txt","is_russian":True,
     "title":"Муму","author_username":"ivan_turgenev",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Немой дворник Герасим привязывается к собачке Муму. Но барыня приказывает избавиться от неё. Рассказ-протест против крепостного права.",
     "cover_emoji":"🐕","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Трагедия","Россия XIX век"],"views_count":94000,"likes_count":7700,"rating":4.72},

    {"source":"dataset","dataset_path":"prose/Turgenev/Ася.txt","is_russian":True,
     "title":"Ася","author_username":"ivan_turgenev",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"Русский путешественник встречает в Германии загадочную девушку Асю и влюбляется в неё. Но в решающий момент трусость берёт верх. О потерянном счастье.",
     "cover_emoji":"🌸","is_adult":False,"is_featured":False,
     "tags":["Классика","Романтика","Россия XIX век","Трагедия"],"views_count":81000,"likes_count":6600,"rating":4.78},

    {"source":"dataset","dataset_path":"prose/Turgenev/Дым.txt","is_russian":True,
     "title":"Дым","author_username":"ivan_turgenev",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"В Баден-Бадене русский дворянин Литвинов встречает бывшую возлюбленную и снова вспыхивает давняя страсть. Роман о иллюзиях, компромиссах и цене счастья.",
     "cover_emoji":"💨","is_adult":False,"is_featured":False,
     "tags":["Классика","Романтика","Россия XIX век","Трагедия","Любовь"],"views_count":58000,"likes_count":4600,"rating":4.69},

    # ── Чехов ─────────────────────────────────────────────────────
    {"source":"dataset","dataset_path":"prose/Chekhov/Палата №6.txt","is_russian":True,
     "title":"Палата № 6","author_username":"anton_chekhov",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Провинциальный доктор начинает беседовать с пациентом психиатрической палаты и сам попадает в неё. Беспощадная повесть о безумии системы.",
     "cover_emoji":"🏥","is_adult":False,"is_featured":True,
     "tags":["Классика","Психология","Трагедия","Россия XIX век"],"views_count":98000,"likes_count":8100,"rating":4.86},

    {"source":"dataset","dataset_path":"prose/Chekhov/Вишнёвый сад.txt","is_russian":True,
     "title":"Вишнёвый сад","author_username":"anton_chekhov",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Разорившаяся помещица возвращается в родовое имение, которое продают на аукционе. Последняя пьеса Чехова — лирическая комедия о конце старой России.",
     "cover_emoji":"🌳","is_adult":False,"is_featured":True,
     "tags":["Классика","Трагедия","Россия XIX век","Символизм"],"views_count":101000,"likes_count":8200,"rating":4.87},

    {"source":"dataset","dataset_path":"prose/Chekhov/Три сестры.txt","is_russian":True,
     "title":"Три сестры","author_username":"anton_chekhov",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Три сестры мечтают о Москве, но их жизнь проходит в провинции. Пьеса о несбыточных надеждах и невозможности вырваться из обыденности.",
     "cover_emoji":"🌸","is_adult":False,"is_featured":False,
     "tags":["Классика","Трагедия","Психология","Россия XIX век"],"views_count":86000,"likes_count":6900,"rating":4.83},

    {"source":"dataset","dataset_path":"prose/Chekhov/Дуэль.txt","is_russian":True,
     "title":"Дуэль","author_username":"anton_chekhov",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Два совершенно разных человека — вялый интеллигент Лаевский и убеждённый зоолог Фон Корен — сталкиваются в конфликте, ведущем к дуэли. Лучшая повесть Чехова о русской интеллигенции.",
     "cover_emoji":"🔫","is_adult":False,"is_featured":False,
     "tags":["Классика","Психология","Россия XIX век","Реализм"],"views_count":74000,"likes_count":5900,"rating":4.82},

    {"source":"dataset","dataset_path":"prose/Chekhov/Драма на охоте.txt","is_russian":True,
     "title":"Драма на охоте","author_username":"anton_chekhov",
     "genre":Genre.DETECTIVE,"status":BookStatus.COMPLETED,
     "description":"Следователь расследует убийство молодой женщины в помещичьей усадьбе. Единственный детективный роман Чехова — захватывающий и психологически точный.",
     "cover_emoji":"🔍","is_adult":True,"is_featured":False,
     "tags":["Классика","Детектив","Психология","Россия XIX век"],"views_count":82000,"likes_count":6600,"rating":4.78},

    {"source":"dataset","dataset_path":"prose/Chekhov/Дама с собачкой.txt","is_russian":True,
     "title":"Дама с собачкой","author_username":"anton_chekhov",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"Банковский служащий Гуров встречает в Ялте замужнюю Анну Сергеевну. Курортный роман неожиданно перерастает в настоящую любовь. Шедевр мировой короткой прозы.",
     "cover_emoji":"🐩","is_adult":False,"is_featured":False,
     "tags":["Классика","Романтика","Трагедия","Россия XIX век","Любовь"],"views_count":118000,"likes_count":9600,"rating":4.88},

    {"source":"dataset","dataset_path":"prose/Chekhov/Ионыч.txt","is_russian":True,
     "title":"Ионыч","author_username":"anton_chekhov",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"История молодого врача Старцева, как провинциальный быт и несостоявшаяся любовь превращают его в «Ионыча» — сытого, равнодушного обывателя.",
     "cover_emoji":"💊","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Трагедия","Россия XIX век"],"views_count":67000,"likes_count":5300,"rating":4.79},

    {"source":"dataset","dataset_path":"prose/Chekhov/В овраге.txt","is_russian":True,
     "title":"В овраге","author_username":"anton_chekhov",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Жизнь крестьянской семьи в деревне, где торгуют поддельной водкой. История ужасающего преступления и бессилия добра перед злом. Самая жёсткая повесть Чехова.",
     "cover_emoji":"🌾","is_adult":True,"is_featured":False,
     "tags":["Классика","Реализм","Трагедия","Россия XIX век","Преступление"],"views_count":58000,"likes_count":4600,"rating":4.76},

    {"source":"dataset","dataset_path":"prose/Chekhov/Человек в футляре.txt","is_russian":True,
     "title":"Человек в футляре","author_username":"anton_chekhov",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Учитель Беликов боится всего, что «как бы чего не вышло», и своим страхом держит в футляре весь город. Рассказ-символ о духовной несвободе.",
     "cover_emoji":"📦","is_adult":False,"is_featured":False,
     "tags":["Классика","Сатира","Психология","Россия XIX век"],"views_count":89000,"likes_count":7200,"rating":4.83},

    {"source":"dataset","dataset_path":"prose/Chekhov/Дом с мезонином.txt","is_russian":True,
     "title":"Дом с мезонином","author_username":"anton_chekhov",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"Художник влюбляется в Мисюсь — юную сестру деятельной народницы Лиды. Но Лида разлучает их. Лирическая повесть о красоте, любви и невозможности счастья.",
     "cover_emoji":"🏠","is_adult":False,"is_featured":False,
     "tags":["Классика","Романтика","Россия XIX век","Трагедия","Любовь"],"views_count":61000,"likes_count":4900,"rating":4.77},

    # ── Лермонтов ─────────────────────────────────────────────────
    {"source":"dataset","dataset_path":"prose/Lermontov/Герой нашего времени.txt","is_russian":True,
     "title":"Герой нашего времени","author_username":"mikhail_lermontov",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Печорин — офицер, эгоист и скептик — странствует по Кавказу и разрушает жизни людей. Первый психологический роман в русской литературе.",
     "cover_emoji":"🏔️","is_adult":False,"is_featured":True,
     "tags":["Классика","Психология","Россия XIX век","Философия"],"views_count":138000,"likes_count":11200,"rating":4.89},

    # ── Горький ───────────────────────────────────────────────────
    {"source":"dataset","dataset_path":"prose/Gorky/Мать.txt","is_russian":True,
     "title":"Мать","author_username":"maxim_gorky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Простая заводская женщина Пелагея Ниловна следует за сыном-революционером и сама становится борцом. Роман о пробуждении народного сознания — главный политический роман Горького.",
     "cover_emoji":"✊","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Война","Россия XIX век"],"views_count":84000,"likes_count":6700,"rating":4.72},

    {"source":"dataset","dataset_path":"prose/Gorky/Детство.txt","is_russian":True,
     "title":"Детство (Горький)","author_username":"maxim_gorky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Первая часть автобиографической трилогии. Алёша Пешков растёт в жестокой купеческой семье. Пронзительный рассказ о детстве среди насилия, где свет исходит от бабушки.",
     "cover_emoji":"🏚️","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Семья","Россия XIX век"],"views_count":84000,"likes_count":6700,"rating":4.75},

    {"source":"dataset","dataset_path":"prose/Gorky/В людях.txt","is_russian":True,
     "title":"В людях","author_username":"maxim_gorky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Вторая часть трилогии. Алёша работает слугой и поварёнком, жадно читая всё, что попадается. Роман о самообразовании и становлении писателя.",
     "cover_emoji":"📚","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Россия XIX век"],"views_count":58000,"likes_count":4600,"rating":4.67},

    {"source":"dataset","dataset_path":"prose/Gorky/Мои университеты.txt","is_russian":True,
     "title":"Мои университеты","author_username":"maxim_gorky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Третья часть трилогии. Алёша идёт в «университеты жизни»: работает в пекарне, общается с народниками, переживает духовный кризис.",
     "cover_emoji":"🎓","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Россия XIX век"],"views_count":52000,"likes_count":4100,"rating":4.65},

    {"source":"dataset","dataset_path":"prose/Gorky/Фома Гордеев.txt","is_russian":True,
     "title":"Фома Гордеев","author_username":"maxim_gorky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Сын богатого купца Фома Гордеев бунтует против мира наживы и бесчестья. Роман о трагедии свободного человека в клетке купеческого мира.",
     "cover_emoji":"🌊","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Трагедия","Россия XIX век","Психология"],"views_count":67000,"likes_count":5300,"rating":4.73},

    {"source":"dataset","dataset_path":"prose/Gorky/На дне.txt","is_russian":True,
     "title":"На дне","author_username":"maxim_gorky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"В ночлежке собрались отверженные. Приходит странник Лука с утешительной ложью. Пьеса-вопрос: что лучше — правда или утешение?",
     "cover_emoji":"🕯️","is_adult":True,"is_featured":False,
     "tags":["Классика","Реализм","Трагедия","Россия XIX век","Философия"],"views_count":94000,"likes_count":7600,"rating":4.81},

    {"source":"dataset","dataset_path":"prose/Gorky/Старуха Изергиль.txt","is_russian":True,
     "title":"Старуха Изергиль","author_username":"maxim_gorky",
     "genre":Genre.FANTASY,"status":BookStatus.COMPLETED,
     "description":"Три истории: легенда о гордеце Ларре, история жизни самой старухи Изергиль и легенда о Данко, осветившем путь людям своим горящим сердцем.",
     "cover_emoji":"🔥","is_adult":False,"is_featured":False,
     "tags":["Классика","Магия","Философия","Реализм"],"views_count":78000,"likes_count":6400,"rating":4.78},

    {"source":"dataset","dataset_path":"prose/Gorky/Бывшие люди.txt","is_russian":True,
     "title":"Бывшие люди","author_username":"maxim_gorky",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Очерк о людях «дна» — бывших чиновниках, дворянах, интеллигентах, павших до ночлежки. Ранний Горький в лучшей реалистической форме.",
     "cover_emoji":"🌧️","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Трагедия","Россия XIX век"],"views_count":48000,"likes_count":3800,"rating":4.68},

    # ── Брюсов ────────────────────────────────────────────────────
    {"source":"dataset","dataset_path":"prose/Bryusov/Огненный ангел.txt","is_russian":True,
     "title":"Огненный ангел","author_username":"valery_bryusov",
     "genre":Genre.HISTORICAL,"status":BookStatus.COMPLETED,
     "description":"Германия XVI века: рыцарь Рупрехт встречает девушку Ренату, одержимую духом «огненного ангела». Мистический исторический роман — вершина русского символизма.",
     "cover_emoji":"🔥","is_adult":True,"is_featured":False,
     "tags":["Исторический","Мистика","Символизм","Романтика","Средневековье"],"views_count":58000,"likes_count":4600,"rating":4.72},

    {"source":"dataset","dataset_path":"prose/Bryusov/Алтарь победы.txt","is_russian":True,
     "title":"Алтарь победы","author_username":"valery_bryusov",
     "genre":Genre.HISTORICAL,"status":BookStatus.COMPLETED,
     "description":"Рим IV века нашей эры на закате великой империи. Молодой провинциал Юний Норбан попадает в водоворот языческой и христианской борьбы за душу умирающей цивилизации.",
     "cover_emoji":"🏛️","is_adult":False,"is_featured":False,
     "tags":["Исторический","Классика","Философия","Средневековье"],"views_count":42000,"likes_count":3300,"rating":4.65},

    {"source":"dataset","dataset_path":"prose/Bryusov/Юпитер поверженный.txt","is_russian":True,
     "title":"Юпитер поверженный","author_username":"valery_bryusov",
     "genre":Genre.HISTORICAL,"status":BookStatus.COMPLETED,
     "description":"Продолжение «Алтаря победы»: падение Западной Римской империи. Последние язычники и первые христиане в эпоху великого перелома.",
     "cover_emoji":"⚡","is_adult":False,"is_featured":False,
     "tags":["Исторический","Классика","Философия","Средневековье","Война"],"views_count":36000,"likes_count":2900,"rating":4.61},

    {"source":"dataset","dataset_path":"prose/Bryusov/Республика Южного Креста.txt","is_russian":True,
     "title":"Республика Южного Креста","author_username":"valery_bryusov",
     "genre":Genre.SCIFI,"status":BookStatus.COMPLETED,
     "description":"В идеальном городе под арктическим куполом разгорается эпидемия безумия — «мании противоречия». Рассказ-антиутопия, предвосхитивший Замятина и Оруэлла.",
     "cover_emoji":"🌐","is_adult":False,"is_featured":False,
     "tags":["Антиутопия","Символизм","Апокалипсис","Философия"],"views_count":44000,"likes_count":3500,"rating":4.68},

    # ── Герцен ────────────────────────────────────────────────────
    {"source":"dataset","dataset_path":"prose/Herzen/Кто виноват.txt","is_russian":True,
     "title":"Кто виноват?","author_username":"alexander_herzen",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Молодой дворянин Бельтов возвращается в провинцию и разрушает тихое семейное счастье Круциферских. Роман-вопрос о вине, обществе и неустроенности «лишнего человека».",
     "cover_emoji":"❓","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Психология","Россия XIX век","Философия"],"views_count":48000,"likes_count":3800,"rating":4.68},

    {"source":"dataset","dataset_path":"prose/Herzen/Долг прежде всего.txt","is_russian":True,
     "title":"Долг прежде всего","author_username":"alexander_herzen",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Повесть об испанском революционере и его семье, оказавшейся в ловушке чести и долга. Героический сюжет с острым политическим подтекстом.",
     "cover_emoji":"⚡","is_adult":False,"is_featured":False,
     "tags":["Классика","Исторический","Война","Философия"],"views_count":38000,"likes_count":3000,"rating":4.58},

    {"source":"dataset","dataset_path":"prose/Herzen/С того берега.txt","is_russian":True,
     "title":"С того берега","author_username":"alexander_herzen",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Философские диалоги и монологи о революции 1848 года, крушении либеральных надежд и судьбе Европы. Одно из главных произведений русской политической мысли.",
     "cover_emoji":"🌊","is_adult":False,"is_featured":False,
     "tags":["Классика","Философия","Исторический","Реализм"],"views_count":32000,"likes_count":2500,"rating":4.60},

    # ══════════════════════════════════════════════════════════════
    # ENGLISH BOOKS — Project Gutenberg
    # ══════════════════════════════════════════════════════════════

    {"source":"gutenberg","gutenberg_id":11,"is_russian":False,
     "title":"Alice's Adventures in Wonderland","author_username":"lewis_carroll",
     "genre":Genre.FANTASY,"status":BookStatus.COMPLETED,
     "description":"Alice follows a White Rabbit into a world of talking creatures and a card-suit Queen. A timeless Victorian masterpiece of imagination.",
     "cover_emoji":"🐇","is_adult":False,"is_featured":True,
     "tags":["Магия","Приключение","Классика","Дети"],"views_count":124500,"likes_count":9800,"rating":4.82},

    {"source":"gutenberg","gutenberg_id":55,"is_russian":False,
     "title":"The Wonderful Wizard of Oz","author_username":"lf_baum",
     "genre":Genre.FANTASY,"status":BookStatus.COMPLETED,
     "description":"Dorothy is swept to the magical Land of Oz and must follow the Yellow Brick Road to find the wizard who can send her home.",
     "cover_emoji":"🌈","is_adult":False,"is_featured":False,
     "tags":["Магия","Дружба","Приключение","Дети"],"views_count":98700,"likes_count":8200,"rating":4.75},

    {"source":"gutenberg","gutenberg_id":1342,"is_russian":False,
     "title":"Pride and Prejudice","author_username":"jane_austen",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"Elizabeth Bennet navigates love and marriage in Regency England. Her relationship with the proud Mr. Darcy is one of literature's greatest love stories.",
     "cover_emoji":"💌","is_adult":False,"is_featured":True,
     "tags":["Романтика","Классика","Семья","Любовь"],"views_count":210000,"likes_count":18500,"rating":4.91},

    {"source":"gutenberg","gutenberg_id":161,"is_russian":False,
     "title":"Sense and Sensibility","author_username":"jane_austen",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"Sisters Elinor and Marianne Dashwood seek love — one through reason, one through passionate feeling. Austen's first published novel.",
     "cover_emoji":"🌸","is_adult":False,"is_featured":False,
     "tags":["Романтика","Классика","Семья","Любовь"],"views_count":98500,"likes_count":7800,"rating":4.79},

    {"source":"gutenberg","gutenberg_id":158,"is_russian":False,
     "title":"Emma","author_username":"jane_austen",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"Emma Woodhouse amuses herself matchmaking for her friends — with disastrous results. Austen's wittiest and most perfectly constructed novel.",
     "cover_emoji":"🎀","is_adult":False,"is_featured":False,
     "tags":["Романтика","Классика","Юмор","Семья","Любовь"],"views_count":112000,"likes_count":9200,"rating":4.83},

    {"source":"gutenberg","gutenberg_id":105,"is_russian":False,
     "title":"Persuasion","author_username":"jane_austen",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"Anne Elliot reunites with Captain Wentworth, years after being persuaded to break their engagement. Austen's last and most emotionally mature novel.",
     "cover_emoji":"🍂","is_adult":False,"is_featured":False,
     "tags":["Романтика","Классика","Любовь"],"views_count":74000,"likes_count":5900,"rating":4.77},

    {"source":"gutenberg","gutenberg_id":1260,"is_russian":False,
     "title":"Jane Eyre","author_username":"charlotte_bronte",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"Orphan Jane Eyre becomes a governess and falls for the brooding Mr. Rochester — but dark secrets haunt Thornfield Hall.",
     "cover_emoji":"🌹","is_adult":False,"is_featured":False,
     "tags":["Романтика","Классика","Психология","Любовь"],"views_count":145000,"likes_count":11200,"rating":4.87},

    {"source":"gutenberg","gutenberg_id":768,"is_russian":False,
     "title":"Wuthering Heights","author_username":"charlotte_bronte",
     "genre":Genre.ROMANCE,"status":BookStatus.COMPLETED,
     "description":"Heathcliff and Catherine's obsessive love on the wild Yorkshire moors ends in tragedy spanning two generations.",
     "cover_emoji":"🌬️","is_adult":False,"is_featured":False,
     "tags":["Романтика","Классика","Трагедия","Психология","Любовь"],"views_count":118000,"likes_count":9600,"rating":4.83},

    {"source":"gutenberg","gutenberg_id":1661,"is_russian":False,
     "title":"The Adventures of Sherlock Holmes","author_username":"arthur_conan_doyle",
     "genre":Genre.DETECTIVE,"status":BookStatus.COMPLETED,
     "description":"Twelve classic cases: A Scandal in Bohemia, The Red-Headed League, The Five Orange Pips. The definitive detective collection.",
     "cover_emoji":"🔍","is_adult":False,"is_featured":True,
     "tags":["Детектив","Классика","Психология"],"views_count":189000,"likes_count":15200,"rating":4.93},

    {"source":"gutenberg","gutenberg_id":2852,"is_russian":False,
     "title":"The Hound of the Baskervilles","author_username":"arthur_conan_doyle",
     "genre":Genre.DETECTIVE,"status":BookStatus.COMPLETED,
     "description":"A spectral hound terrorises the Baskerville family on the fog-shrouded moors. Holmes and Watson must unravel the truth.",
     "cover_emoji":"🐺","is_adult":False,"is_featured":False,
     "tags":["Детектив","Мистика","Классика"],"views_count":134000,"likes_count":10800,"rating":4.88},

    {"source":"gutenberg","gutenberg_id":244,"is_russian":False,
     "title":"A Study in Scarlet","author_username":"arthur_conan_doyle",
     "genre":Genre.DETECTIVE,"status":BookStatus.COMPLETED,
     "description":"The first Sherlock Holmes story: Watson meets the brilliant detective and together they solve a baffling murder with roots in the American West.",
     "cover_emoji":"🕵️","is_adult":False,"is_featured":False,
     "tags":["Детектив","Классика","Приключение"],"views_count":91000,"likes_count":7500,"rating":4.79},

    {"source":"gutenberg","gutenberg_id":345,"is_russian":False,
     "title":"Dracula","author_username":"bram_stoker",
     "genre":Genre.HORROR,"status":BookStatus.COMPLETED,
     "description":"Jonathan Harker's visit to Count Dracula's castle begins a nightmare. Told through journals and letters, this is the definitive vampire novel.",
     "cover_emoji":"🧛","is_adult":True,"is_featured":True,
     "tags":["Вампиры","Мистика","Классика"],"views_count":178000,"likes_count":13500,"rating":4.85},

    {"source":"gutenberg","gutenberg_id":84,"is_russian":False,
     "title":"Frankenstein","author_username":"mary_shelley",
     "genre":Genre.SCIFI,"status":BookStatus.COMPLETED,
     "description":"Victor Frankenstein creates a sentient creature from dead matter and abandons it. A profound meditation on creation and responsibility.",
     "cover_emoji":"⚡","is_adult":False,"is_featured":True,
     "tags":["Классика","Психология","Мистика","Философия"],"views_count":112000,"likes_count":9100,"rating":4.72},

    {"source":"gutenberg","gutenberg_id":43,"is_russian":False,
     "title":"The Strange Case of Dr Jekyll and Mr Hyde","author_username":"rl_stevenson",
     "genre":Genre.HORROR,"status":BookStatus.COMPLETED,
     "description":"Dr Jekyll experiments with a potion that releases his darker self as Mr Hyde. A chilling exploration of duality and the battle between good and evil.",
     "cover_emoji":"🧪","is_adult":True,"is_featured":False,
     "tags":["Мистика","Психология","Классика"],"views_count":98000,"likes_count":8200,"rating":4.76},

    {"source":"gutenberg","gutenberg_id":120,"is_russian":False,
     "title":"Treasure Island","author_username":"rl_stevenson",
     "genre":Genre.ADVENTURE,"status":BookStatus.COMPLETED,
     "description":"Young Jim Hawkins sets sail for Treasure Island with Long John Silver and a crew of pirates. The novel that defined the modern pirate story.",
     "cover_emoji":"⚓","is_adult":False,"is_featured":True,
     "tags":["Приключение","Классика","Выживание"],"views_count":134000,"likes_count":10900,"rating":4.83},

    {"source":"gutenberg","gutenberg_id":35,"is_russian":False,
     "title":"The Time Machine","author_username":"hg_wells",
     "genre":Genre.SCIFI,"status":BookStatus.COMPLETED,
     "description":"A scientist travels to the year 802,701 AD and discovers humanity split into two species. The novel that invented time travel.",
     "cover_emoji":"⏱️","is_adult":False,"is_featured":False,
     "tags":["Космос","Путешествие","Классика","Антиутопия"],"views_count":89000,"likes_count":7400,"rating":4.68},

    {"source":"gutenberg","gutenberg_id":36,"is_russian":False,
     "title":"The War of the Worlds","author_username":"hg_wells",
     "genre":Genre.SCIFI,"status":BookStatus.COMPLETED,
     "description":"Martian cylinders land in Surrey and deadly tripods begin destroying everything. Mankind's first alien invasion story.",
     "cover_emoji":"🚀","is_adult":False,"is_featured":False,
     "tags":["Космос","Апокалипсис","Классика","Война"],"views_count":95600,"likes_count":7900,"rating":4.71},

    {"source":"gutenberg","gutenberg_id":103,"is_russian":False,
     "title":"Around the World in Eighty Days","author_username":"jules_verne",
     "genre":Genre.ADVENTURE,"status":BookStatus.COMPLETED,
     "description":"Phileas Fogg bets his fortune he can circle the globe in 80 days. With servant Passepartout and detective Fix on his tail, the race begins.",
     "cover_emoji":"🌍","is_adult":False,"is_featured":False,
     "tags":["Приключение","Классика","Путешествие"],"views_count":112000,"likes_count":9200,"rating":4.77},

    {"source":"gutenberg","gutenberg_id":164,"is_russian":False,
     "title":"Twenty Thousand Leagues Under the Sea","author_username":"jules_verne",
     "genre":Genre.ADVENTURE,"status":BookStatus.COMPLETED,
     "description":"Professor Aronnax is held captive aboard the Nautilus, the submarine of the mysterious Captain Nemo. A voyage through the wonders of the deep ocean.",
     "cover_emoji":"🦑","is_adult":False,"is_featured":False,
     "tags":["Приключение","Классика","Путешествие","Природа"],"views_count":94000,"likes_count":7700,"rating":4.74},

    {"source":"gutenberg","gutenberg_id":74,"is_russian":False,
     "title":"The Adventures of Tom Sawyer","author_username":"mark_twain",
     "genre":Genre.ADVENTURE,"status":BookStatus.COMPLETED,
     "description":"Tom Sawyer's adventures on the Mississippi: whitewashing a fence, witnessing a murder, and finding buried treasure.",
     "cover_emoji":"🎣","is_adult":False,"is_featured":False,
     "tags":["Приключение","Дружба","Классика","Дети"],"views_count":103000,"likes_count":8600,"rating":4.74},

    {"source":"gutenberg","gutenberg_id":76,"is_russian":False,
     "title":"Adventures of Huckleberry Finn","author_username":"mark_twain",
     "genre":Genre.ADVENTURE,"status":BookStatus.COMPLETED,
     "description":"Huck Finn and Jim journey down the Mississippi River. Twain's masterpiece and a devastating critique of racism and hypocrisy.",
     "cover_emoji":"🚣","is_adult":False,"is_featured":False,
     "tags":["Приключение","Классика","Дружба","Выживание"],"views_count":112000,"likes_count":9200,"rating":4.80},

    {"source":"gutenberg","gutenberg_id":98,"is_russian":False,
     "title":"A Tale of Two Cities","author_username":"charles_dickens",
     "genre":Genre.HISTORICAL,"status":BookStatus.COMPLETED,
     "description":"London and Paris on the eve of the French Revolution. A story of sacrifice, resurrection, and love that transcends death.",
     "cover_emoji":"🏰","is_adult":False,"is_featured":True,
     "tags":["Классика","Исторический","Предательство","Война"],"views_count":138000,"likes_count":10600,"rating":4.84},

    {"source":"gutenberg","gutenberg_id":1400,"is_russian":False,
     "title":"Great Expectations","author_username":"charles_dickens",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Orphan Pip's life is transformed by a mysterious benefactor. A masterpiece about ambition, class, and what it means to be a gentleman.",
     "cover_emoji":"🎩","is_adult":False,"is_featured":False,
     "tags":["Классика","Семья","Психология","Реализм"],"views_count":119000,"likes_count":9400,"rating":4.80},

    {"source":"gutenberg","gutenberg_id":730,"is_russian":False,
     "title":"Oliver Twist","author_username":"charles_dickens",
     "genre":Genre.DRAMA,"status":BookStatus.COMPLETED,
     "description":"Young Oliver, born in a workhouse, falls in with a gang of criminals in London. Dickens' fierce attack on the Victorian Poor Law system.",
     "cover_emoji":"🥣","is_adult":False,"is_featured":False,
     "tags":["Классика","Реализм","Дети","Преступление"],"views_count":97000,"likes_count":7900,"rating":4.75},

    {"source":"gutenberg","gutenberg_id":174,"is_russian":False,
     "title":"The Picture of Dorian Gray","author_username":"oscar_wilde",
     "genre":Genre.MYSTERY,"status":BookStatus.COMPLETED,
     "description":"Dorian Gray's portrait ages while he stays forever young. Wilde's only novel — a dazzling fable of beauty, vanity, and damnation.",
     "cover_emoji":"🖼️","is_adult":True,"is_featured":True,
     "tags":["Мистика","Классика","Психология","Символизм"],"views_count":142000,"likes_count":11300,"rating":4.86},

    {"source":"gutenberg","gutenberg_id":910,"is_russian":False,
     "title":"The Call of the Wild","author_username":"jack_london",
     "genre":Genre.ADVENTURE,"status":BookStatus.COMPLETED,
     "description":"Buck, a domesticated dog, is sold to Yukon sled teams during the Gold Rush. A tale of survival, instinct, and the primordial wild.",
     "cover_emoji":"🐕","is_adult":False,"is_featured":False,
     "tags":["Приключение","Классика","Выживание","Природа"],"views_count":88000,"likes_count":7200,"rating":4.73},

    {"source":"gutenberg","gutenberg_id":1184,"is_russian":False,
     "title":"The Count of Monte Cristo","author_username":"alexandre_dumas",
     "genre":Genre.ADVENTURE,"status":BookStatus.COMPLETED,
     "description":"Wrongfully imprisoned Edmond Dantès escapes and returns as the wealthy Count of Monte Cristo to exact perfect revenge on those who betrayed him.",
     "cover_emoji":"💎","is_adult":False,"is_featured":True,
     "tags":["Приключение","Классика","Предательство","Исторический"],"views_count":198000,"likes_count":16500,"rating":4.92},

    {"source":"gutenberg","gutenberg_id":1257,"is_russian":False,
     "title":"The Three Musketeers","author_username":"alexandre_dumas",
     "genre":Genre.ADVENTURE,"status":BookStatus.COMPLETED,
     "description":"Young d'Artagnan befriends Athos, Porthos, and Aramis. Together they foil Cardinal Richelieu's schemes. All for one and one for all!",
     "cover_emoji":"⚔️","is_adult":False,"is_featured":False,
     "tags":["Приключение","Классика","Исторический","Дружба"],"views_count":156000,"likes_count":12800,"rating":4.88},

]

# ══════════════════════════════════════════════════════════════════════════════
# REVIEW TEXTS
# ══════════════════════════════════════════════════════════════════════════════

REVIEWS_RU = [
    "Абсолютный шедевр. Каждая страница — откровение. Перечитывал несколько раз.",
    "Одна из лучших книг в моей жизни. Язык безупречен, образы незабываемы.",
    "Глубокая, пронзительная проза. После прочтения долго не мог прийти в себя.",
    "Классика на все времена. Каждое поколение открывает в этом тексте что-то своё.",
    "Читал на одном дыхании. Невозможно оторваться от первой до последней страницы.",
    "Гениально и просто одновременно. Автор говорит о вечном очень понятно.",
    "После этой книги смотришь на мир по-другому. Настоятельно рекомендую.",
    "Знал по школьной программе, а теперь понял заново. Совсем другое восприятие.",
    "Психологическая глубина поразительная. Каждый персонаж — живой человек.",
    "Одно из тех произведений, которые остаются с тобой навсегда.",
]
REVIEWS_EN = [
    "A masterpiece that stands the test of time. Every chapter draws you deeper.",
    "Incredible prose and unforgettable characters. One of the best I've ever read.",
    "The author's genius is evident on every page. A must-read for any book lover.",
    "Captivating from first page to last. I couldn't put it down.",
    "A perfect blend of suspense and beauty. The writing is simply outstanding.",
    "An absolute classic. Changed the way I see the world.",
    "Brilliant storytelling with complex, richly drawn characters.",
    "I was completely transported to another world. Extraordinary.",
    "One of those rare books that leaves you thinking for days after finishing.",
    "Simply stunning. Every sentence is crafted with care.",
]


# ══════════════════════════════════════════════════════════════════════════════
# SEED
# ══════════════════════════════════════════════════════════════════════════════

async def seed():
    # Validate dataset
    if not os.path.isdir(DATASET_DIR):
        print(f"⚠️  Dataset not found at: {DATASET_DIR}")
        print("   Place the extracted archive.zip contents at that path.")
        print("   (Should contain prose/, poems/ subdirectories)")
        sys.exit(1)

    ru_count = sum(1 for b in BOOKS if b.get("is_russian"))
    en_count = sum(1 for b in BOOKS if not b.get("is_russian"))
    print(f"📦 Dataset: {DATASET_DIR}")
    print(f"📚 Books in catalogue: {len(BOOKS)} ({ru_count} RU + {en_count} EN)")
    print("🔧 Ensuring tables exist …")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:

        # 1. Wipe
        print("\n🗑  Removing all existing data …")
        for tbl in ("reading_progress", "bookmarks", "reviews",
                    "book_tags", "chapters", "books", "tags"):
            await db.execute(sa_text(f"DELETE FROM {tbl}"))
        await db.execute(sa_delete(User).where(User.role != UserRole.ADMIN))
        await db.commit()
        print("   ✓ Cleared")

        # 2. Tags
        print("\n🏷  Creating tags …")
        tag_map: dict[str, Tag] = {}
        for name, slug in ALL_TAGS.items():
            t = Tag(name=name, slug=slug, usage_count=random.randint(50, 8000))
            db.add(t)
            await db.flush()
            tag_map[name] = t
        await db.commit()
        print(f"   ✓ {len(tag_map)} tags")

        # 3. Authors
        print("\n✍️  Creating authors …")
        author_map: dict[str, User] = {}
        for a in ALL_AUTHORS:
            u = User(
                username=a["username"][:50],
                email=a["email"][:255],
                hashed_password=hash_password("Author1234!"),
                display_name=a["display_name"][:100],
                bio=a["bio"],
                role=UserRole.AUTHOR,
                is_active=True,
                is_verified=True,
            )
            db.add(u)
            await db.flush()
            author_map[a["username"]] = u
        await db.commit()
        print(f"   ✓ {len(author_map)} authors")

        # 4. Readers
        print("\n📖 Creating readers …")
        readers: list[User] = []
        reader_names = [
            "Анна Морозова", "Иван Петров", "Мария Соколова", "Алексей Волков",
            "Елена Козлова", "Дмитрий Новиков", "Наташа Орлова", "Павел Белов",
            "Юлия Зайцева", "Сергей Фёдоров",
        ]
        for i, name in enumerate(reader_names):
            u = User(
                username=f"reader_{i}",
                email=f"reader{i}@lh.ru",
                hashed_password=hash_password("Reader1234!"),
                display_name=name,
                role=UserRole.READER,
                is_active=True,
                is_verified=True,
            )
            db.add(u)
            await db.flush()
            readers.append(u)
        await db.commit()
        print(f"   ✓ {len(readers)} readers")

        # 5. Books
        print(f"\n📚 Loading {len(BOOKS)} books …\n")
        all_books: list[Book] = []
        failed: list[str] = []
        used_slugs: set[str] = set()

        for bdef in BOOKS:
            title = bdef["title"]
            is_ru = bdef.get("is_russian", False)
            print(f"   📖  {title}")

            raw: str | None = None

            if bdef["source"] == "dataset":
                raw = load_from_dataset(bdef["dataset_path"])
                if raw:
                    raw = clean_russian_text(raw)
                    print(f"         ✓ dataset — {len(raw):,} chars")
                else:
                    print(f"         ✗ not found in dataset: {bdef['dataset_path']}")

            elif bdef["source"] == "gutenberg":
                raw = fetch_gutenberg(bdef["gutenberg_id"])
                if raw:
                    print(f"         ✓ Gutenberg #{bdef['gutenberg_id']} — {len(raw):,} chars")
                else:
                    print(f"         ✗ Gutenberg #{bdef['gutenberg_id']} — not available")

            if not raw or len(raw) < 1000:
                print(f"         ✗ Skipping — no text")
                failed.append(title)
                continue

            # Parse chapters
            chs = parse_chapters(raw, is_russian=is_ru, max_ch=25,
                                  min_words=50 if not is_ru else 200)
            if not chs:
                print(f"         ✗ No chapters parsed — skipping")
                failed.append(title)
                continue
            print(f"         ✓ {len(chs)} chapters, "
                  f"{sum(c['words_count'] for c in chs):,} words")

            author = author_map.get(bdef["author_username"])
            if not author:
                print(f"         ✗ Unknown author '{bdef['author_username']}'")
                continue

            # Unique slug
            slug = make_slug(title)
            base_slug, ctr = slug, 0
            while slug in used_slugs:
                ctr += 1
                slug = f"{base_slug}-{ctr}"
            used_slugs.add(slug)

            words_total = sum(c["words_count"] for c in chs)
            book = Book(
                title=title[:295],
                slug=slug[:345],
                description=bdef["description"],
                cover_emoji=(bdef.get("cover_emoji") or "📚")[:10],
                author_id=author.id,
                genre=bdef["genre"],
                status=bdef.get("status", BookStatus.COMPLETED),
                is_published=True,
                is_adult=bdef.get("is_adult", False),
                is_featured=bdef.get("is_featured", False),
                views_count=bdef.get("views_count", 10000),
                likes_count=bdef.get("likes_count", 1000),
                bookmarks_count=random.randint(300, 6000),
                chapters_count=len(chs),
                words_count=words_total,
                rating=bdef.get("rating", 4.5),
            )
            db.add(book)
            await db.flush()

            for ch in chs:
                db.add(Chapter(
                    book_id=book.id,
                    number=ch["number"],
                    title=ch["title"][:295],
                    content=ch["content"],
                    words_count=ch["words_count"],
                    is_published=True,
                ))

            for tag_name in bdef.get("tags", []):
                t = tag_map.get(tag_name)
                if t:
                    db.add(BookTag(book_id=book.id, tag_id=t.id))

            await db.flush()
            all_books.append(book)

            # Small delay for Gutenberg downloads
            if bdef["source"] == "gutenberg":
                time.sleep(0.4)

        await db.commit()
        skipped_msg = f" — skipped: {', '.join(failed[:6])}" if failed else ""
        print(f"\n   ✅ {len(all_books)} books saved  "
              f"({len(failed)} failed{skipped_msg})")

        # 6. Reviews
        print("\n💬 Adding reviews …")
        rev = 0
        for book in all_books:
            pool = REVIEWS_RU if book.title and any(ord(c) > 127 for c in book.title) else REVIEWS_EN
            for reader in random.sample(readers, k=random.randint(2, 6)):
                db.add(Review(
                    user_id=reader.id,
                    book_id=book.id,
                    rating=round(random.uniform(3.8, 5.0), 1),
                    text=random.choice(pool),
                    is_spoiler=False,
                ))
                rev += 1
        await db.commit()
        print(f"   ✓ {rev} reviews")

        # 7. Bookmarks
        print("\n🔖 Adding bookmarks …")
        bm = 0
        for reader in readers:
            for book in random.sample(all_books, k=min(len(all_books), random.randint(5, 14))):
                db.add(Bookmark(user_id=reader.id, book_id=book.id))
                bm += 1
        await db.commit()
        print(f"   ✓ {bm} bookmarks")

    print()
    print("=" * 65)
    print("✅  Seed complete!")
    print("=" * 65)
    ru_saved = sum(1 for b in all_books if any(ord(c) > 127 for c in b.title))
    en_saved = len(all_books) - ru_saved
    print(f"  📚  Books:    {len(all_books)}  ({ru_saved} RU + {en_saved} EN)")
    if failed:
        print(f"  ⚠️   Failed:   {len(failed)} — {', '.join(failed[:8])}")
    print(f"  ✍️   Authors:  {len(ALL_AUTHORS)}")
    print(f"  👤  Readers:  reader0@lh.ru … reader9@lh.ru / Reader1234!")
    print(f"  💬  Reviews:  {rev}")
    print()
    print("  Russian source: Kaggle 'Russian Literature' dataset")
    print("  English source: Project Gutenberg")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(seed())
