from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.models.book import BookStatus, Genre


class BookCreate(BaseModel):
    title: str
    description: Optional[str] = None
    genre: Optional[Genre] = None
    genre_id: Optional[int] = None  # legacy support
    cover_emoji: str = "📚"
    is_adult: bool = False
    age_rating: Optional[str] = None
    language: Optional[str] = "ru"

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or len(v) > 300:
            raise ValueError("Название: 2–300 символов")
        return v


class BookUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[Genre] = None
    genre_id: Optional[int] = None
    status: Optional[BookStatus] = None
    cover_emoji: Optional[str] = None
    is_adult: Optional[bool] = None
    age_rating: Optional[str] = None


class BookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    slug: str
    description: Optional[str]
    cover_emoji: str
    cover_url: Optional[str]
    genre: Genre
    status: BookStatus
    views_count: int
    likes_count: int
    bookmarks_count: int
    chapters_count: int
    words_count: int
    reviews_count: int
    rating: float
    is_published: bool
    is_featured: bool
    is_adult: bool
    author_id: int
    created_at: datetime
    updated_at: datetime


class BookListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    slug: str
    cover_emoji: str
    cover_url: Optional[str]
    genre: Genre
    status: BookStatus
    views_count: int
    likes_count: int
    rating: float
    chapters_count: int
    author_id: int


class ChapterCreate(BaseModel):
    title: str
    content: str
    number: Optional[int] = None
    author_note: Optional[str] = None
    is_published: bool = True

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1 or len(v) > 300:
            raise ValueError("Название главы: 1–300 символов")
        return v


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    author_note: Optional[str] = None
    is_published: Optional[bool] = None


class ChapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    book_id: int
    number: int
    title: str
    content: Optional[str]
    words_count: int
    views_count: int
    is_published: bool
    author_note: Optional[str]
    created_at: datetime


class ReviewCreate(BaseModel):
    rating: int
    text: Optional[str] = None
    is_spoiler: bool = False

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("Оценка: от 1 до 5")
        return v


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    book_id: int
    rating: float
    text: Optional[str]
    created_at: datetime
