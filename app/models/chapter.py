from typing import Optional
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("book_id", "number", name="uq_chapter_book_num"),
        Index("ix_chapters_book_published", "book_id", "is_published"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    book_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    words_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    views_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_draft_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    author_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    book: Mapped["Book"] = relationship("Book", back_populates="chapters")
    reading_progress: Mapped[list["ReadingProgress"]] = relationship(
        "ReadingProgress", back_populates="chapter", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Chapter book={self.book_id} #{self.number} {self.title!r}>"
