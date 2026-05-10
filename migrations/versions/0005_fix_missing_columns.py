"""Emergency fix: add all missing columns using raw SQL IF NOT EXISTS

Revision ID: 0005
Revises: 0004
Create Date: 2025-03-18 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Use raw SQL with IF NOT EXISTS — safe to run even if columns already exist

    # ── books ──────────────────────────────────────────────────────────────
    book_cols = [
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS direction VARCHAR(20) DEFAULT 'gen'",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS is_draft_hidden BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS is_on_moderation BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS content_warnings VARCHAR(500)",
    ]

    # ── chapters ──────────────────────────────────────────────────────────
    chapter_cols = [
        "ALTER TABLE chapters ADD COLUMN IF NOT EXISTS is_draft_hidden BOOLEAN NOT NULL DEFAULT false",
    ]

    # ── users ──────────────────────────────────────────────────────────────
    user_cols = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason VARCHAR(500)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS followers_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS works_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS website VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(50)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_provider_id VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE",
    ]

    # ── book_tags ─────────────────────────────────────────────────────────
    booktag_cols = [
        "ALTER TABLE book_tags ADD COLUMN IF NOT EXISTS is_spoiler INTEGER NOT NULL DEFAULT 0",
    ]

    # ── reports table ─────────────────────────────────────────────────────
    create_reports = """
        CREATE TABLE IF NOT EXISTS reports (
            id           SERIAL PRIMARY KEY,
            reporter_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            book_id      INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            reason       VARCHAR(100) NOT NULL,
            comment      VARCHAR(500),
            is_resolved  BOOLEAN NOT NULL DEFAULT false,
            resolved_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """

    # ── notifications table ───────────────────────────────────────────────
    create_notifications = """
        CREATE TABLE IF NOT EXISTS notifications (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind        VARCHAR(50) NOT NULL,
            title       VARCHAR(200) NOT NULL,
            body        VARCHAR(500),
            link        VARCHAR(500),
            is_read     BOOLEAN NOT NULL DEFAULT false,
            created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """

    all_statements = (
        book_cols + chapter_cols + user_cols + booktag_cols +
        [create_reports, create_notifications]
    )

    for stmt in all_statements:
        try:
            conn.execute(sa.text(stmt))
            print(f"  OK: {stmt[:60].strip()}...")
        except Exception as e:
            print(f"  SKIP ({e}): {stmt[:60].strip()}")

    # Create indexes safely
    index_stmts = [
        "CREATE INDEX IF NOT EXISTS ix_reports_reporter_id ON reports(reporter_id)",
        "CREATE INDEX IF NOT EXISTS ix_reports_book_id     ON reports(book_id)",
        "CREATE INDEX IF NOT EXISTS ix_reports_is_resolved ON reports(is_resolved)",
        "CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_notif_user_unread   ON notifications(user_id, is_read)",
    ]
    for stmt in index_stmts:
        try:
            conn.execute(sa.text(stmt))
        except Exception:
            pass


def downgrade() -> None:
    pass
