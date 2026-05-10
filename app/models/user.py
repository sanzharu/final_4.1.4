import enum
from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, Boolean, Enum, Integer, Text, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class UserRole(str, enum.Enum):
    READER = "reader"
    AUTHOR = "author"
    MODERATOR = "moderator"
    ADMIN = "admin"


class OAuthProvider(str, enum.Enum):
    GOOGLE = "google"
    GITHUB = "github"
    VK = "vk"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.READER, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ban_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Inline OAuth (single provider per user for simplicity)
    oauth_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    oauth_provider_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Counters
    followers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    following_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    works_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    books: Mapped[List["Book"]] = relationship("Book", back_populates="author", lazy="select")
    oauth_accounts: Mapped[List["OAuthAccount"]] = relationship("OAuthAccount", back_populates="user", lazy="select")
    likes: Mapped[List["Like"]] = relationship("Like", back_populates="user", lazy="select")
    bookmarks: Mapped[List["Bookmark"]] = relationship("Bookmark", back_populates="user", lazy="select")
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="user", lazy="select")
    reading_progress: Mapped[List["ReadingProgress"]] = relationship("ReadingProgress", back_populates="user", lazy="select")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username} role={self.role}>"

    @property
    def is_staff(self) -> bool:
        return self.role in (UserRole.MODERATOR, UserRole.ADMIN)

    @property
    def is_moderator_or_higher(self) -> bool:
        return self.role in (UserRole.MODERATOR, UserRole.ADMIN)

    @property
    def can_publish(self) -> bool:
        return self.role in (UserRole.AUTHOR, UserRole.MODERATOR, UserRole.ADMIN)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_uid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")
