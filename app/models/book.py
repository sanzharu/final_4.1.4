import enum
from typing import Optional, List
from sqlalchemy import (String, Text, Integer, Boolean, Enum, ForeignKey,
                        Float, Index, CheckConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class BookStatus(str, enum.Enum):
    ONGOING = "ongoing"
    COMPLETED = "completed"
    HIATUS = "hiatus"
    DRAFT = "draft"


class Genre(str, enum.Enum):
    FANTASY = "fantasy"
    ROMANCE = "romance"
    DETECTIVE = "detective"
    SCIFI = "scifi"
    HORROR = "horror"
    HISTORICAL = "historical"
    ADVENTURE = "adventure"
    THRILLER = "thriller"
    DRAMA = "drama"
    COMEDY = "comedy"
    MYSTERY = "mystery"
    YOUNG_ADULT = "young_adult"


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (
        Index("ix_books_genre_status", "genre", "status"),
        Index("ix_books_author_id", "author_id"),
        Index("ix_books_rating", "rating"),
        CheckConstraint("rating >= 0 AND rating <= 5", name="ck_rating_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(350), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_emoji: Mapped[str] = mapped_column(String(10), default="📚", nullable=False)
    cover_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    genre: Mapped[Genre] = mapped_column(Enum(Genre), nullable=False, index=True)
    status: Mapped[BookStatus] = mapped_column(
        Enum(BookStatus), default=BookStatus.DRAFT, nullable=False, index=True
    )

    # Counters (updated via triggers/service)
    views_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    likes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bookmarks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chapters_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    words_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reviews_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_adult: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_draft_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_on_moderation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    direction: Mapped[Optional[str]] = mapped_column(String(20), default="gen", nullable=True)
    content_warnings: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # JSON list of warning keys

    # Relationships
    author: Mapped["User"] = relationship("User", back_populates="books")
    chapters: Mapped[List["Chapter"]] = relationship(
        "Chapter", back_populates="book", lazy="select", order_by="Chapter.number"
    )
    tags: Mapped[List["BookTag"]] = relationship("BookTag", back_populates="book", lazy="selectin")
    likes: Mapped[List["Like"]] = relationship("Like", back_populates="book", lazy="select")
    bookmarks: Mapped[List["Bookmark"]] = relationship("Bookmark", back_populates="book", lazy="select")
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="book", lazy="select")
    reading_progress: Mapped[List["ReadingProgress"]] = relationship("ReadingProgress", back_populates="book", lazy="select")

    def __repr__(self) -> str:
        return f"<Book id={self.id} title={self.title!r}>"

    @property
    def avg_rating(self) -> float:
        return self.rating
