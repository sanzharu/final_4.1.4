"""Add reports table, direction/is_draft_hidden to books, is_draft_hidden to chapters, notifications

Revision ID: 0004
Revises: 0003
Create Date: 2025-03-12 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def get_columns(table_name: str):
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        return {c["name"] for c in insp.get_columns(table_name)}
    except Exception:
        return set()


def table_exists(name: str) -> bool:
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        return name in insp.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    # ── Reports table ─────────────────────────────────────────────────────────
    if not table_exists("reports"):
        op.create_table(
            "reports",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("reporter_id", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("book_id", sa.Integer(),
                      sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reason", sa.String(100), nullable=False),
            sa.Column("comment", sa.String(500), nullable=True),
            sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("resolved_by", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_reports_book_id", "reports", ["book_id"])
        op.create_index("ix_reports_reporter_id", "reports", ["reporter_id"])
        op.create_index("ix_reports_is_resolved", "reports", ["is_resolved"])

    # ── Books table extra columns ──────────────────────────────────────────────
    book_cols = get_columns("books")
    if "direction" not in book_cols:
        op.add_column("books", sa.Column("direction", sa.String(20),
                                          nullable=True, server_default="gen"))
    if "is_draft_hidden" not in book_cols:
        op.add_column("books", sa.Column("is_draft_hidden", sa.Boolean(),
                                          nullable=False, server_default="false"))
    if "is_on_moderation" not in book_cols:
        op.add_column("books", sa.Column("is_on_moderation", sa.Boolean(),
                                          nullable=False, server_default="false"))

    # ── Chapters table extra columns ───────────────────────────────────────────
    ch_cols = get_columns("chapters")
    if "is_draft_hidden" not in ch_cols:
        op.add_column("chapters", sa.Column("is_draft_hidden", sa.Boolean(),
                                             nullable=False, server_default="false"))

    # ── Notifications table ────────────────────────────────────────────────────
    if not table_exists("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(50), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("body", sa.String(500), nullable=True),
            sa.Column("link", sa.String(500), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_notif_user_unread", "notifications", ["user_id", "is_read"])

    # ── Users - is_banned, ban_reason columns ──────────────────────────────────
    user_cols = get_columns("users")
    if "is_banned" not in user_cols:
        op.add_column("users", sa.Column("is_banned", sa.Boolean(),
                                          nullable=False, server_default="false"))
    if "ban_reason" not in user_cols:
        op.add_column("users", sa.Column("ban_reason", sa.String(500), nullable=True))


def downgrade() -> None:
    pass
