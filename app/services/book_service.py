from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, or_, and_, delete
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.models.book import Book, BookStatus, Genre
from app.models.chapter import Chapter
from app.models.interaction import Like
from app.models.social import Bookmark, Review, ReadingProgress
from app.models.tag import Tag, BookTag
from app.models.user import User
from app.schemas.book import BookCreate, BookUpdate, ChapterCreate, ReviewCreate
from slugify import slugify


async def _unique_slug(db: AsyncSession, title: str, exclude_id: int = None) -> str:
    base = slugify(title, allow_unicode=False)[:300] or "book"
    slug = base
    i = 1
    while True:
        q = select(Book).where(Book.slug == slug)
        if exclude_id:
            q = q.where(Book.id != exclude_id)
        if not (await db.execute(q)).scalar_one_or_none():
            return slug
        slug = f"{base}-{i}"
        i += 1


async def create_book(db: AsyncSession, author: User, data: BookCreate) -> Book:
    if not author.can_publish:
        raise HTTPException(status_code=403, detail="Нужна роль автора для публикации")
    slug = await _unique_slug(db, data.title)
    # Support both genre enum and genre_id
    genre = getattr(data, "genre", None)
    if genre is None and hasattr(data, "genre_id") and data.genre_id:
        # genre_id not used in our model — skip
        genre = Genre.FANTASY
    book = Book(
        title=data.title,
        slug=slug,
        description=getattr(data, "description", None),
        genre=genre or Genre.FANTASY,
        cover_emoji=getattr(data, "cover_emoji", ""),
        is_adult=getattr(data, "is_adult", False),
        author_id=author.id,
        status=BookStatus.DRAFT,
    )
    db.add(book)
    await db.flush()
    author.works_count += 1
    return book


async def get_book_by_slug(db: AsyncSession, slug: str) -> Optional[Book]:
    result = await db.execute(
        select(Book)
        .where(Book.slug == slug)
        .options(selectinload(Book.author), selectinload(Book.tags).selectinload(BookTag.tag))
    )
    return result.scalar_one_or_none()


async def get_book_by_id(db: AsyncSession, book_id: int, load_relations: bool = False) -> Optional[Book]:
    q = select(Book).where(Book.id == book_id)
    if load_relations:
        q = q.options(selectinload(Book.author), selectinload(Book.tags).selectinload(BookTag.tag))
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def list_books(
    db: AsyncSession,
    genre: Optional[Genre] = None,
    genre_id: Optional[int] = None,
    status: Optional[BookStatus] = None,
    author_id: Optional[int] = None,
    search: Optional[str] = None,
    is_featured: Optional[bool] = None,
    featured_only: bool = False,
    sort: str = "views",
    order_by: Optional[str] = None,
    age_rating: Optional[str] = None,
    page: int = 1,
    page_size: int = 24,
    per_page: Optional[int] = None,
    include_unpublished: bool = False,
) -> Tuple[List[Book], int]:
    if per_page is not None:
        page_size = per_page
    if featured_only:
        is_featured = True

    if include_unpublished and author_id:
        # Author's own books — show all statuses
        q = select(Book).where(Book.author_id == author_id)
    else:
        q = select(Book).where(Book.is_published == True, Book.is_draft_hidden == False)
    if genre:
        q = q.where(Book.genre == genre)
    if status:
        q = q.where(Book.status == status)
    if author_id:
        q = q.where(Book.author_id == author_id)
    if is_featured is not None:
        q = q.where(Book.is_featured == is_featured)
    if search:
        term = f"%{search}%"
        q = q.where(or_(Book.title.ilike(term), Book.description.ilike(term)))

    # Support both 'sort' and 'order_by' params
    effective_sort = order_by or sort
    sort_map = {
        "views": Book.views_count.desc(),
        "views_count": Book.views_count.desc(),
        "likes": Book.likes_count.desc(),
        "likes_count": Book.likes_count.desc(),
        "rating": Book.rating.desc(),
        "avg_rating": Book.rating.desc(),
        "new": Book.created_at.desc(),
        "created_at": Book.created_at.desc(),
        "updated": Book.updated_at.desc(),
        "updated_at": Book.updated_at.desc(),
        "last_chapter_at": Book.updated_at.desc(),
    }
    q = q.order_by(sort_map.get(effective_sort, Book.views_count.desc()))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size)
    q = q.options(selectinload(Book.author))
    books = (await db.execute(q)).scalars().all()
    return list(books), total


async def update_book(db: AsyncSession, book: Book, data: BookUpdate, user: User = None) -> Book:
    if user and book.author_id != user.id and not user.is_staff:
        raise HTTPException(status_code=403, detail="Нет прав на редактирование")
    for field, value in data.model_dump(exclude_none=True).items():
        if hasattr(book, field):
            setattr(book, field, value)
    if data.title:
        book.slug = await _unique_slug(db, data.title, exclude_id=book.id)
    await db.flush()
    return book


async def delete_book(db: AsyncSession, book: Book, user: User) -> None:
    if book.author_id != user.id and not user.is_staff:
        raise HTTPException(status_code=403, detail="Нет прав")
    await db.delete(book)
    await db.flush()


async def publish_book(db: AsyncSession, book: Book, user: User) -> Book:
    if book.author_id != user.id and not user.is_staff:
        raise HTTPException(status_code=403, detail="Нет прав")
    if book.chapters_count == 0:
        raise HTTPException(status_code=400, detail="Нельзя публиковать книгу без глав")
    book.is_published = True
    book.status = BookStatus.ONGOING
    await db.flush()
    return book


async def increment_views(db: AsyncSession, book_id: int) -> None:
    await db.execute(update(Book).where(Book.id == book_id).values(views_count=Book.views_count + 1))


#  Genres & Tags 
async def list_genres(db: AsyncSession) -> List[dict]:
    """Return genre list as dicts with slug/name/emoji for templates."""
    GENRES = [
        {"id": "fantasy",    "slug": "fantasy",    "name": "Фэнтези",      "emoji": ""},
        {"id": "romance",    "slug": "romance",    "name": "Романтика",     "emoji": ""},
        {"id": "detective",  "slug": "detective",  "name": "Детектив",      "emoji": ""},
        {"id": "scifi",      "slug": "scifi",      "name": "Фантастика",    "emoji": ""},
        {"id": "horror",     "slug": "horror",     "name": "Ужасы",         "emoji": ""},
        {"id": "historical", "slug": "historical", "name": "Исторический",  "emoji": ""},
        {"id": "adventure",  "slug": "adventure",  "name": "Приключения",   "emoji": ""},
        {"id": "thriller",   "slug": "thriller",   "name": "Триллер",       "emoji": ""},
        {"id": "drama",      "slug": "drama",      "name": "Драма",         "emoji": ""},
        {"id": "mystery",    "slug": "mystery",    "name": "Мистика",       "emoji": ""},
    ]
    # Return as simple namespace objects so template can use g.slug, g.name, g.emoji
    class GenreObj:
        def __init__(self, d):
            self.__dict__.update(d)
    return [GenreObj(g) for g in GENRES]


async def list_tags(db: AsyncSession) -> List[Tag]:
    result = await db.execute(select(Tag).order_by(Tag.usage_count.desc()).limit(50))
    return list(result.scalars().all())


#  Chapters 
async def create_chapter(db: AsyncSession, book: Book, data: ChapterCreate, user: User = None) -> Chapter:
    if user and book.author_id != user.id and not user.is_staff:
        raise HTTPException(status_code=403, detail="Нет прав")
    if data.number is None:
        result = await db.execute(select(func.max(Chapter.number)).where(Chapter.book_id == book.id))
        max_num = result.scalar_one() or 0
        number = max_num + 1
    else:
        number = data.number

    is_pub = getattr(data, "is_published", True)
    words = len(data.content.split()) if data.content else 0
    ch = Chapter(
        book_id=book.id,
        number=number,
        title=data.title,
        content=data.content,
        words_count=words,
        author_note=getattr(data, "author_note", None),
        is_published=is_pub,
    )
    db.add(ch)
    await db.flush()
    book.chapters_count += 1
    book.words_count += words
    await db.flush()
    return ch


async def get_chapter(db: AsyncSession, chapter_id_or_book_id, chapter_num: int = None) -> Optional[Chapter]:
    """Support both get_chapter(db, chapter_id) and get_chapter(db, book_id, chapter_num)."""
    if chapter_num is not None:
        result = await db.execute(
            select(Chapter).where(Chapter.book_id == chapter_id_or_book_id, Chapter.number == chapter_num)
        )
    else:
        result = await db.execute(select(Chapter).where(Chapter.id == chapter_id_or_book_id))
    return result.scalar_one_or_none()


async def list_chapters(db: AsyncSession, book_id: int, published_only: bool = True) -> List[Chapter]:
    q = select(Chapter).where(Chapter.book_id == book_id)
    if published_only:
        q = q.where(Chapter.is_published == True)
    q = q.order_by(Chapter.number)
    result = await db.execute(q)
    return list(result.scalars().all())


async def update_chapter(db: AsyncSession, chapter: Chapter, data) -> Chapter:
    for field in ("title", "content", "author_note", "is_published"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(chapter, field, val)
    if data.content:
        chapter.words_count = len(data.content.split())
    await db.flush()
    return chapter


async def delete_chapter(db: AsyncSession, chapter: Chapter, book: Book) -> None:
    await db.delete(chapter)
    book.chapters_count = max(0, book.chapters_count - 1)
    await db.flush()


#  Interactions 
async def toggle_like(db: AsyncSession, user_id: int, book_id: int) -> bool:
    result = await db.execute(select(Like).where(Like.user_id == user_id, Like.book_id == book_id))
    like = result.scalar_one_or_none()
    book = (await db.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
    if like:
        await db.delete(like)
        if book:
            book.likes_count = max(0, book.likes_count - 1)
        return False
    else:
        db.add(Like(user_id=user_id, book_id=book_id))
        if book:
            book.likes_count += 1
        return True


async def toggle_bookmark(db: AsyncSession, user_id: int, book_id: int) -> bool:
    result = await db.execute(select(Bookmark).where(Bookmark.user_id == user_id, Bookmark.book_id == book_id))
    bm = result.scalar_one_or_none()
    book = (await db.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
    if bm:
        await db.delete(bm)
        if book:
            book.bookmarks_count = max(0, book.bookmarks_count - 1)
        return False
    else:
        db.add(Bookmark(user_id=user_id, book_id=book_id))
        if book:
            book.bookmarks_count += 1
        return True


async def is_bookmarked(db: AsyncSession, user_id: int, book_id: int) -> bool:
    result = await db.execute(select(Bookmark).where(Bookmark.user_id == user_id, Bookmark.book_id == book_id))
    return result.scalar_one_or_none() is not None


async def user_liked(db: AsyncSession, user_id: int, book_id: int) -> bool:
    result = await db.execute(select(Like).where(Like.user_id == user_id, Like.book_id == book_id))
    return result.scalar_one_or_none() is not None


async def user_bookmarked(db: AsyncSession, user_id: int, book_id: int) -> bool:
    return await is_bookmarked(db, user_id, book_id)


async def get_user_bookmarks(db: AsyncSession, user_id: int, page: int = 1, per_page: int = 20) -> Tuple[List[Book], int]:
    bm_q = select(Bookmark).where(Bookmark.user_id == user_id)
    total = (await db.execute(select(func.count()).select_from(bm_q.subquery()))).scalar_one()
    bms = (await db.execute(
        bm_q.options(selectinload(Bookmark.book).selectinload(Book.author))
        .offset((page - 1) * per_page).limit(per_page)
    )).scalars().all()
    return [bm.book for bm in bms if bm.book], total


#  Reviews 
async def create_review(db: AsyncSession, user: User, book: Book, data: ReviewCreate) -> Review:
    existing = (await db.execute(
        select(Review).where(Review.user_id == user.id, Review.book_id == book.id)
    )).scalar_one_or_none()
    if existing:
        raise ValueError("Вы уже оставили отзыв на эту книгу")
    review = Review(user_id=user.id, book_id=book.id, rating=data.rating, text=data.text, is_spoiler=getattr(data, "is_spoiler", False))
    db.add(review)
    await db.flush()
    avg = (await db.execute(
        select(func.avg(Review.rating)).where(Review.book_id == book.id, Review.is_hidden == False)
    )).scalar_one() or 0
    count = (await db.execute(
        select(func.count()).where(Review.book_id == book.id, Review.is_hidden == False)
    )).scalar_one()
    book.rating = round(float(avg), 2)
    book.reviews_count = count
    await db.flush()
    return review


async def list_reviews(db: AsyncSession, book_id: int, page: int = 1, per_page: int = 10) -> Tuple[List[Review], int]:
    q = select(Review).where(Review.book_id == book_id, Review.is_hidden == False)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    reviews = (await db.execute(
        q.options(selectinload(Review.user))
        .order_by(Review.created_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    )).scalars().all()
    return list(reviews), total


async def get_book_reviews(db: AsyncSession, book_id: int, page: int = 1) -> List[Review]:
    reviews, _ = await list_reviews(db, book_id, page)
    return reviews


async def get_user_review(db: AsyncSession, user_id: int, book_id: int) -> Optional[Review]:
    result = await db.execute(
        select(Review).where(Review.user_id == user_id, Review.book_id == book_id)
    )
    return result.scalar_one_or_none()


#  Reading progress 
async def upsert_reading_progress(db: AsyncSession, user_id: int, book_id: int, chapter_id: int) -> None:
    result = await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == user_id, ReadingProgress.book_id == book_id)
    )
    progress = result.scalar_one_or_none()
    if progress:
        progress.chapter_id = chapter_id
    else:
        db.add(ReadingProgress(user_id=user_id, book_id=book_id, chapter_id=chapter_id))
    await db.flush()


async def get_reading_progress(db: AsyncSession, user_id: int, book_id: int) -> Optional[ReadingProgress]:
    result = await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == user_id, ReadingProgress.book_id == book_id)
    )
    return result.scalar_one_or_none()


async def add_tags_to_book(db: AsyncSession, book_id: int, tag_names: list, spoiler_names: list = None) -> None:
    """Create or link tags to a book. spoiler_names are tag names that should be marked as spoilers."""
    from app.models.tag import Tag, BookTag
    from sqlalchemy import select as sel
    if spoiler_names is None:
        spoiler_names = []
    all_tags = [(n, False) for n in tag_names] + [(n, True) for n in spoiler_names]
    for name, is_spoiler in all_tags[:15]:
        name = str(name).strip()[:50]
        if not name:
            continue
        result = await db.execute(sel(Tag).where(Tag.name == name))
        tag = result.scalar_one_or_none()
        if not tag:
            tag = Tag(name=name, slug=name.lower().replace(" ", "-").replace("/", "-"))
            db.add(tag)
            await db.flush()
        existing = await db.execute(sel(BookTag).where(BookTag.book_id == book_id, BookTag.tag_id == tag.id))
        bt = existing.scalar_one_or_none()
        if bt:
            bt.is_spoiler = 1 if is_spoiler else 0
        else:
            db.add(BookTag(book_id=book_id, tag_id=tag.id, is_spoiler=1 if is_spoiler else 0))
    await db.flush()


async def clear_book_tags(db: AsyncSession, book_id: int) -> None:
    """Remove all tag links from a book."""
    from app.models.tag import BookTag
    from sqlalchemy import delete as del_
    await db.execute(del_(BookTag).where(BookTag.book_id == book_id))
    await db.flush()


# ── Follow / Subscribe helpers ────────────────────────────────────────────────
async def toggle_follow(db: AsyncSession, follower_id: int, following_id: int) -> bool:
    """Toggle follow. Returns True if now following, False if unfollowed."""
    from app.models.social import Follow
    from app.models.user import User as UserModel
    existing = (await db.execute(
        select(Follow).where(Follow.follower_id == follower_id, Follow.following_id == following_id)
    )).scalar_one_or_none()
    follower = (await db.execute(select(UserModel).where(UserModel.id == follower_id))).scalar_one_or_none()
    target = (await db.execute(select(UserModel).where(UserModel.id == following_id))).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        if follower: follower.following_count = max(0, follower.following_count - 1)
        if target: target.followers_count = max(0, target.followers_count - 1)
        await db.flush()
        return False
    else:
        db.add(Follow(follower_id=follower_id, following_id=following_id))
        if follower: follower.following_count += 1
        if target: target.followers_count += 1
        await db.flush()
        return True


async def is_following(db: AsyncSession, follower_id: int, following_id: int) -> bool:
    from app.models.social import Follow
    result = (await db.execute(
        select(Follow).where(Follow.follower_id == follower_id, Follow.following_id == following_id)
    )).scalar_one_or_none()
    return result is not None


async def toggle_book_subscription(db: AsyncSession, user_id: int, book_id: int) -> bool:
    """Toggle book subscription. Returns True if now subscribed."""
    from app.models.social import BookSubscription
    existing = (await db.execute(
        select(BookSubscription).where(BookSubscription.user_id == user_id, BookSubscription.book_id == book_id)
    )).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.flush()
        return False
    else:
        db.add(BookSubscription(user_id=user_id, book_id=book_id))
        await db.flush()
        return True


async def is_subscribed_to_book(db: AsyncSession, user_id: int, book_id: int) -> bool:
    from app.models.social import BookSubscription
    result = (await db.execute(
        select(BookSubscription).where(BookSubscription.user_id == user_id, BookSubscription.book_id == book_id)
    )).scalar_one_or_none()
    return result is not None


# ── Subscription notifications ─────────────────────────────────────────────────

async def notify_book_subscribers(
    db: AsyncSession,
    book: Book,
    kind: str,
    title: str,
    body: str,
    link: str,
) -> None:
    """Send in-app notifications to all subscribers of a book."""
    from app.models.social import BookSubscription, Notification
    subs = list((await db.execute(
        select(BookSubscription).where(BookSubscription.book_id == book.id)
    )).scalars())
    for sub in subs:
        db.add(Notification(
            user_id=sub.user_id,
            kind=kind,
            title=title,
            body=body,
            link=link,
        ))
    if subs:
        await db.flush()


STATUS_LABELS_RU = {
    "ongoing": "В процессе",
    "completed": "Завершена",
    "hiatus": "Заморожена",
    "draft": "Черновик",
}