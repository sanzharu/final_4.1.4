from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    book_tags: Mapped[list["BookTag"]] = relationship("BookTag", back_populates="tag")


class BookTag(Base):
    __tablename__ = "book_tags"
    __table_args__ = (UniqueConstraint("book_id", "tag_id", name="uq_book_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True)
    is_spoiler: Mapped[bool] = mapped_column(Integer, default=0, nullable=False)

    book: Mapped["Book"] = relationship("Book", back_populates="tags")
    tag: Mapped["Tag"] = relationship("Tag", back_populates="book_tags", lazy="selectin")
