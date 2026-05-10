#!/usr/bin/env python3
"""
⚠️  DEPRECATED — this script used fake generated books.
Use scripts/seed_real_books.py instead.
"""
import sys
print("=" * 60)
print("⚠️  seed.py is deprecated. Use:")
print("   python scripts/seed_real_books.py")
print("=" * 60)
sys.exit(1)

# ---- OLD CODE BELOW (kept for reference) ----
"""
Seed the database with sample data compatible with the actual models.

Run from project root:
    python scripts/seed.py
"""
import asyncio
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faker import Faker
from sqlalchemy import select

from app.db.base import engine, AsyncSessionLocal, Base
import app.models  # гарантирует регистрацию всех моделей
from app.models.user import User, UserRole, OAuthAccount
from app.models.book import Book, BookStatus, Genre
from app.models.chapter import Chapter
from app.models.tag import Tag, BookTag
from app.models.social import Review, Bookmark, ReadingProgress
from app.core.security import hash_password
from app.core.config import settings


fake = Faker("ru_RU")
random.seed(42)

# ── 110 books: (title, Genre enum, is_adult) ─────────────────────────────────
BOOK_DATA = [
    # Fantasy (15)
    ("Зеркальный лабиринт",        Genre.FANTASY,   False),
    ("Кровь Дракона",               Genre.FANTASY,   True),
    ("Академия Теней",              Genre.FANTASY,   False),
    ("Последний Маг Империи",       Genre.FANTASY,   False),
    ("Дочь Бури",                   Genre.FANTASY,   False),
    ("Хроники Мёртвого Леса",       Genre.FANTASY,   True),
    ("Рунный Круг",                 Genre.FANTASY,   False),
    ("Башня Ворона",                Genre.FANTASY,   False),
    ("Проклятье Короны",            Genre.FANTASY,   False),
    ("Серебряный Клинок",           Genre.FANTASY,   True),
    ("Путь Изгоя",                  Genre.FANTASY,   False),
    ("Тайны Вечного Города",        Genre.FANTASY,   False),
    ("Наследница Хаоса",            Genre.FANTASY,   False),
    ("Богиня Войны",                Genre.FANTASY,   True),
    ("Сад Мёртвых Цветов",          Genre.FANTASY,   False),
    # Romance (10)
    ("Между Нами Зима",             Genre.ROMANCE,   False),
    ("Незнакомец из Прошлого",      Genre.ROMANCE,   False),
    ("Контракт на Любовь",          Genre.ROMANCE,   True),
    ("Сердце Миллиардера",          Genre.ROMANCE,   True),
    ("Лето в Провансе",             Genre.ROMANCE,   False),
    ("Случайная Встреча",           Genre.ROMANCE,   False),
    ("Враг или Возлюбленный",       Genre.ROMANCE,   True),
    ("Морской Берег",               Genre.ROMANCE,   False),
    ("Маска Чувств",                Genre.ROMANCE,   False),
    ("Ты — Мой Рассвет",            Genre.ROMANCE,   False),
    # Detective (10)
    ("Дело Ночного Города",         Genre.DETECTIVE, False),
    ("Тихий Убийца",                Genre.DETECTIVE, True),
    ("Следователь Тьмы",            Genre.DETECTIVE, False),
    ("Призрак на Вилле",            Genre.DETECTIVE, False),
    ("Код Молчания",                Genre.DETECTIVE, True),
    ("Смерть в Опере",              Genre.DETECTIVE, False),
    ("Последний Свидетель",         Genre.DETECTIVE, True),
    ("Тайная Организация",          Genre.DETECTIVE, False),
    ("Красная Нить",                Genre.DETECTIVE, False),
    ("Детектив без Имени",          Genre.DETECTIVE, False),
    # Sci-Fi (10)
    ("Звёздный Ковчег",             Genre.SCIFI,     False),
    ("Матрица Разума",              Genre.SCIFI,     False),
    ("Последний Сигнал",            Genre.SCIFI,     False),
    ("Квантовый Разрыв",            Genre.SCIFI,     True),
    ("Планета Забытых",             Genre.SCIFI,     False),
    ("Нейросеть Богов",             Genre.SCIFI,     False),
    ("Колония Омега",               Genre.SCIFI,     False),
    ("Дрейф во Времени",            Genre.SCIFI,     False),
    ("Проект Химера",               Genre.SCIFI,     True),
    ("Солнечный Ветер",             Genre.SCIFI,     False),
    # Horror (10)
    ("Дом на Холме",                Genre.HORROR,    True),
    ("Шёпот Тьмы",                  Genre.HORROR,    True),
    ("Последняя Ночь",              Genre.HORROR,    True),
    ("Зов Бездны",                  Genre.HORROR,    True),
    ("Кукольный Театр",             Genre.HORROR,    True),
    ("Деревня Проклятых",           Genre.HORROR,    True),
    ("Запись 666",                  Genre.HORROR,    True),
    ("Гость из Зазеркалья",         Genre.HORROR,    False),
    ("Тёмный Ритуал",               Genre.HORROR,    True),
    ("Забытое Кладбище",            Genre.HORROR,    False),
    # Historical (10)
    ("Царица Скифов",               Genre.HISTORICAL, False),
    ("Путь Варяга",                 Genre.HISTORICAL, True),
    ("Двор Людовика",               Genre.HISTORICAL, False),
    ("Стражник Рима",               Genre.HISTORICAL, False),
    ("Огонь Средневековья",         Genre.HISTORICAL, True),
    ("Купеческая Дочь",             Genre.HISTORICAL, False),
    ("Тайны Петербурга",            Genre.HISTORICAL, False),
    ("Заговор Бояр",                Genre.HISTORICAL, False),
    ("Золото Орды",                 Genre.HISTORICAL, False),
    ("Дочь Самурая",                Genre.HISTORICAL, False),
    # Adventure (10)
    ("Остров Потерянных",           Genre.ADVENTURE,  False),
    ("Горы Безмолвия",              Genre.ADVENTURE,  False),
    ("Охотник за Реликвиями",       Genre.ADVENTURE,  False),
    ("Тропа Дракона",               Genre.ADVENTURE,  False),
    ("Экспедиция в Никуда",         Genre.ADVENTURE,  False),
    ("Дикий Запад",                 Genre.ADVENTURE,  False),
    ("Морской Волк",                Genre.ADVENTURE,  False),
    ("Пещеры Забвения",             Genre.ADVENTURE,  False),
    ("Карта Судьбы",                Genre.ADVENTURE,  False),
    ("Последний Форпост",           Genre.ADVENTURE,  False),
    # Mystery (5)
    ("Ведьма из Соседнего Дома",    Genre.MYSTERY,    False),
    ("Проклятие Рода",              Genre.MYSTERY,    False),
    ("Лунный Зверь",                Genre.MYSTERY,    True),
    ("Тени Прошлого",               Genre.MYSTERY,    False),
    ("Голос из Пустоты",            Genre.MYSTERY,    False),
    # Drama (10)
    ("Зеркало Души",                Genre.DRAMA,     False),
    ("Молчание Внутри",             Genre.DRAMA,     False),
    ("Осколки",                     Genre.DRAMA,     True),
    ("Точка Невозврата",            Genre.DRAMA,     True),
    ("Между Строк",                 Genre.DRAMA,     False),
    ("Чужая Жизнь",                 Genre.DRAMA,     False),
    ("Невидимые Цепи",              Genre.DRAMA,     False),
    ("Ошибка Врача",                Genre.DRAMA,     False),
    ("Последний Шанс",              Genre.DRAMA,     False),
    ("Цена Выбора",                 Genre.DRAMA,     False),
    # Thriller (5)
    ("Без Права на Ошибку",         Genre.THRILLER,  False),
    ("Тёмный Контракт",             Genre.THRILLER,  True),
    ("Охота на Тень",               Genre.THRILLER,  False),
    ("Нулевой Пациент",             Genre.THRILLER,  False),
    ("Последний Рубеж",             Genre.THRILLER,  False),
    # Young Adult (5)
    ("Дневник Призрака",            Genre.YOUNG_ADULT, False),
    ("Суперспособность Неудачника", Genre.YOUNG_ADULT, False),
    ("Академия Монстров",           Genre.YOUNG_ADULT, False),
    ("Звезда Первого Курса",        Genre.YOUNG_ADULT, False),
    ("Мир за Стеной",               Genre.YOUNG_ADULT, False),
    # Comedy (5)
    ("Приключения Котика",          Genre.COMEDY,    False),
    ("Волшебник по Найму",          Genre.COMEDY,    False),
    ("Офис Магов",                  Genre.COMEDY,    False),
    ("Дракон на Диване",            Genre.COMEDY,    False),
    ("Некромант-неудачник",         Genre.COMEDY,    False),
]

TAGS_DATA = [
    ("магия",           "magiya"),
    ("дракон",          "drakon"),
    ("попаданец",       "popadanec"),
    ("академия",        "akademiya"),
    ("сильная героиня", "silnaya-geroinya"),
    ("тёмный герой",    "temnyy-geroy"),
    ("любовный треугольник", "lyubovnyy-treugolnik"),
    ("апокалипсис",     "apokalipsis"),
    ("вампиры",         "vampiry"),
    ("оборотни",        "oborotni"),
    ("средневековье",   "srednevekove"),
    ("постапокалипсис", "postapokalipsis"),
    ("киберпанк",       "kiberpank"),
    ("космос",          "kosmos"),
    ("путешествие во времени", "puteshestvie-vo-vremeni"),
    ("артефакты",       "artefakty"),
    ("маньяк",          "manyak"),
    ("психология",      "psihologiya"),
    ("семья",           "semya"),
    ("дружба",          "druzhba"),
    ("предательство",   "predatelstvo"),
    ("реинкарнация",    "reinkarnaciya"),
    ("система",         "sistema"),
    ("боевые искусства","boevye-iskusstva"),
    ("романтика",       "romantika"),
    ("исторический",    "istoricheskiy"),
    ("мистика",         "mistika"),
    ("Россия",          "rossiya"),
    ("выживание",       "vyzhivanie"),
    ("месть",           "mest"),
]

CHAPTER_TEXTS = [
    """Утро выдалось серым. {name} проснулся раньше обычного — что-то не давало покоя, какое-то смутное предчувствие, которое невозможно было объяснить словами.

За окном шелестел дождь. Капли ударяли по стеклу с монотонным упорством, словно пытались передать какое-то послание на языке, которого он не знал.

— Сегодня всё изменится, — прошептал он в темноту комнаты.

Он не знал, откуда взялась эта мысль. Но знал точно: она права.

{paragraph1}

{paragraph2}

Когда он наконец встал и подошёл к окну, город внизу уже просыпался. Машины, люди, суета — всё то же самое, что и вчера. Но что-то было другим. Что-то в воздухе изменилось, и он один это чувствовал.""",

    """— Это невозможно, — сказал {secondary}, и в его голосе не было ни тени сомнения.

{name} только усмехнулся. Он слышал эти слова столько раз, что они давно перестали его удивлять. «Невозможно» — любимое слово тех, кто не осмеливается попробовать.

— Смотри, — ответил он и сделал то, что по всем правилам не должно было работать.

Секунда тишины. Потом — изменённое лицо {secondary}, на котором застыло выражение человека, чей мир только что сдвинулся с места.

{paragraph1}

— Как? — наконец выдохнул {secondary}.

{name} пожал плечами. Объяснить это он не мог. Да и не хотел. Некоторые вещи лучше оставлять без объяснений — пусть будут частью той тайны, которая делает жизнь стоящей.

{paragraph2}""",

    """Запись от {date}.

Сегодня произошло то, чего я давно ждал. И одновременно — того, чего я больше всего боялся.

{paragraph1}

Я думал, что готов. Оказалось — нет. Никто никогда не бывает по-настоящему готов к таким вещам. Можно готовиться годами, строить планы, предусматривать каждую деталь — и всё равно, когда момент наступает, он застаёт врасплох.

{paragraph2}

Что будет дальше? Не знаю. Впервые за долгое время я не знаю, что будет дальше. И, как ни странно, это почти не пугает.""",
]

NAMES = ["Алекс", "Марина", "Дмитрий", "Кира", "Артём", "Соня", "Иван", "Лера", "Максим", "Ника"]
SECONDARIES = ["наставник", "союзник", "противник", "незнакомец", "старый друг"]
DATES = ["12-го", "33-го дня пути", "накануне битвы", "после полуночи"]


def gen_chapter(num: int) -> str:
    template = random.choice(CHAPTER_TEXTS)
    return template.format(
        name=random.choice(NAMES),
        secondary=random.choice(SECONDARIES),
        date=random.choice(DATES),
        paragraph1=fake.paragraph(nb_sentences=random.randint(4, 7)),
        paragraph2=fake.paragraph(nb_sentences=random.randint(4, 7)),
    ) + "\n\n" + "\n\n".join(
        fake.paragraph(nb_sentences=random.randint(3, 6))
        for _ in range(random.randint(2, 4))
    )


def make_slug(title: str) -> str:
    import re
    # Transliterate Russian to Latin for slug
    tr = {
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh',
        'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
        'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'ts',
        'ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
        ' ':'-', '—':'-', '–':'-',
    }
    slug = title.lower()
    result = ''
    for ch in slug:
        result += tr.get(ch, ch)
    result = re.sub(r'[^a-z0-9\-]', '', result)
    result = re.sub(r'-+', '-', result).strip('-')
    return result[:200] or 'book'


async def seed():
    print("🔧 Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # ── Admin ─────────────────────────────────────────────────────────────
        print("👑 Creating admin...")
        admin = (await db.execute(
            select(User).where(User.email == settings.FIRST_ADMIN_EMAIL)
        )).scalar_one_or_none()
        if not admin:
            admin = User(
                username=settings.FIRST_ADMIN_USERNAME,
                email=settings.FIRST_ADMIN_EMAIL,
                hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
                display_name="Администратор",
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.add(admin)
            await db.flush()
        print(f"   ✓ {settings.FIRST_ADMIN_EMAIL} / {settings.FIRST_ADMIN_PASSWORD}")

        # ── Authors ───────────────────────────────────────────────────────────
        print("✍️  Creating authors...")
        author_rows = [
            ("elena_storm",   "elena@lh.ru",    "Елена Буря",         "Пишу о магии и людях."),
            ("dark_scribe",   "dark@lh.ru",     "Тёмный Писец",       "Хоррор и мистика."),
            ("romantic_soul", "romantic@lh.ru", "Романтическая Душа", "Любовь во всех формах."),
            ("sci_master",    "sci@lh.ru",       "Мастер НФ",          "Будущее начинается с воображения."),
            ("adventure_pen", "adventure@lh.ru","Перо Странника",      "Каждая книга — путешествие."),
        ]
        authors = []
        for username, email, display, bio in author_rows:
            u = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if not u:
                u = User(
                    username=username,
                    email=email,
                    hashed_password=hash_password("Author1234!"),
                    display_name=display,
                    bio=bio,
                    role=UserRole.AUTHOR,
                    is_active=True,
                    is_verified=True,
                )
                db.add(u)
                await db.flush()
            authors.append(u)
        print(f"   ✓ {len(authors)} авторов")

        # ── Readers ───────────────────────────────────────────────────────────
        print("📖 Creating readers...")
        readers = []
        for i in range(10):
            email = f"reader{i}@lh.ru"
            u = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if not u:
                u = User(
                    username=f"reader_{i}",
                    email=email,
                    hashed_password=hash_password("Reader1234!"),
                    display_name=fake.name(),
                    role=UserRole.READER,
                    is_active=True,
                    is_verified=True,
                )
                db.add(u)
                await db.flush()
            readers.append(u)
        print(f"   ✓ {len(readers)} читателей")

        # ── Tags ──────────────────────────────────────────────────────────────
        print("🏷  Creating tags...")
        tag_objs = []
        for name, slug in TAGS_DATA:
            t = (await db.execute(select(Tag).where(Tag.slug == slug))).scalar_one_or_none()
            if not t:
                t = Tag(name=name, slug=slug, usage_count=random.randint(5, 300))
                db.add(t)
                await db.flush()
            tag_objs.append(t)
        print(f"   ✓ {len(tag_objs)} тегов")

        # ── Books ─────────────────────────────────────────────────────────────
        print(f"📚 Creating {len(BOOK_DATA)} books...")
        all_books = []
        for idx, (title, genre, is_adult) in enumerate(BOOK_DATA):
            slug = make_slug(title)
            # Ensure unique slug
            existing_slugs = set(
                row[0] for row in (await db.execute(
                    __import__('sqlalchemy').text("SELECT slug FROM books")
                )).fetchall()
            )
            final_slug = slug
            counter = 1
            while final_slug in existing_slugs:
                final_slug = f"{slug}-{counter}"
                counter += 1

            existing = (await db.execute(
                select(Book).where(Book.slug == final_slug)
            )).scalar_one_or_none()
            if existing:
                all_books.append(existing)
                continue

            author = random.choice(authors)
            num_chapters = random.randint(3, 8)
            words_total = 0

            book = Book(
                title=title,
                slug=final_slug,
                description=fake.paragraph(nb_sentences=random.randint(3, 5)),
                cover_emoji=random.choice(["📚","⚔️","🌹","🔍","🚀","👻","🏰","🗺️","🎭","🌙"]),
                author_id=author.id,
                genre=genre,
                status=BookStatus.ONGOING,
                is_published=True,
                is_adult=is_adult,
                is_featured=random.random() < 0.12,
                views_count=random.randint(200, 80000),
                likes_count=random.randint(20, 8000),
                bookmarks_count=random.randint(10, 3000),
                chapters_count=num_chapters,
                rating=round(random.uniform(3.0, 5.0), 2),
            )
            db.add(book)
            await db.flush()

            # Chapters
            for ch_num in range(1, num_chapters + 1):
                content = gen_chapter(ch_num)
                words = len(content.split())
                words_total += words
                ch = Chapter(
                    book_id=book.id,
                    number=ch_num,
                    title=f"Глава {ch_num}: {fake.sentence(nb_words=random.randint(2,5)).rstrip('.')}",
                    content=content,
                    words_count=words,
                    is_published=True,
                )
                db.add(ch)

            book.words_count = words_total

            # Tags (2–4 random)
            chosen_tags = random.sample(tag_objs, k=random.randint(2, 4))
            for tag in chosen_tags:
                db.add(BookTag(book_id=book.id, tag_id=tag.id))

            await db.flush()
            all_books.append(book)

            if (idx + 1) % 25 == 0:
                print(f"   {idx + 1}/{len(BOOK_DATA)} ...")

        print(f"   ✓ {len(all_books)} книг")

        # ── Reviews ───────────────────────────────────────────────────────────
        print("💬 Creating reviews...")
        rev_count = 0
        for book in random.sample(all_books, k=min(70, len(all_books))):
            for reader in random.sample(readers, k=random.randint(1, 5)):
                exists = (await db.execute(
                    select(Review).where(Review.user_id == reader.id, Review.book_id == book.id)
                )).scalar_one_or_none()
                if exists:
                    continue
                db.add(Review(
                    user_id=reader.id,
                    book_id=book.id,
                    rating=round(random.uniform(2.5, 5.0), 1),
                    text=fake.paragraph(nb_sentences=random.randint(1, 3)),
                    is_spoiler=random.random() < 0.08,
                ))
                rev_count += 1
        print(f"   ✓ {rev_count} отзывов")

        # ── Bookmarks ─────────────────────────────────────────────────────────
        print("🔖 Creating bookmarks...")
        bm_count = 0
        for reader in readers:
            for book in random.sample(all_books, k=random.randint(5, 20)):
                exists = (await db.execute(
                    select(Bookmark).where(Bookmark.user_id == reader.id, Bookmark.book_id == book.id)
                )).scalar_one_or_none()
                if not exists:
                    db.add(Bookmark(user_id=reader.id, book_id=book.id))
                    bm_count += 1
        print(f"   ✓ {bm_count} закладок")

        await db.commit()

    print()
    print("✅ Seed complete!")
    print("─" * 50)
    print(f"  👑 Admin:    {settings.FIRST_ADMIN_EMAIL} / {settings.FIRST_ADMIN_PASSWORD}")
    print(f"  ✍️  Authors:  elena@lh.ru, dark@lh.ru, romantic@lh.ru")
    print(f"             sci@lh.ru, adventure@lh.ru  / Author1234!")
    print(f"  📖 Readers:  reader0@lh.ru ... reader9@lh.ru / Reader1234!")
    print(f"  📚 Books:    {len(BOOK_DATA)} шт.")
    print("─" * 50)


if __name__ == "__main__":
    asyncio.run(seed())