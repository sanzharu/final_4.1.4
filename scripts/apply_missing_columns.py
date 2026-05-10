"""
Run this script ONCE to fix the database schema:
    python scripts/apply_missing_columns.py

It adds all missing columns safely (IF NOT EXISTS).
No alembic needed.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings


SQL_COMMANDS = [
    # books table
    "ALTER TABLE books ADD COLUMN IF NOT EXISTS direction VARCHAR(20) DEFAULT 'gen'",
    "ALTER TABLE books ADD COLUMN IF NOT EXISTS is_draft_hidden BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE books ADD COLUMN IF NOT EXISTS is_on_moderation BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE books ADD COLUMN IF NOT EXISTS content_warnings VARCHAR(500)",

    # chapters table
    "ALTER TABLE chapters ADD COLUMN IF NOT EXISTS is_draft_hidden BOOLEAN NOT NULL DEFAULT FALSE",

    # users table
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason VARCHAR(500)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS followers_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS works_count INTEGER NOT NULL DEFAULT 0",

    # reports table
    """
    CREATE TABLE IF NOT EXISTS reports (
        id SERIAL PRIMARY KEY,
        reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
        reason VARCHAR(100) NOT NULL,
        comment VARCHAR(500),
        is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
        resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_reports_reporter_id ON reports(reporter_id)",
    "CREATE INDEX IF NOT EXISTS ix_reports_book_id ON reports(book_id)",
    "CREATE INDEX IF NOT EXISTS ix_reports_is_resolved ON reports(is_resolved)",

    # notifications table
    """
    CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        kind VARCHAR(50) NOT NULL,
        title VARCHAR(200) NOT NULL,
        body VARCHAR(500),
        link VARCHAR(500),
        is_read BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications(user_id)",
    "CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications(is_read)",
    "CREATE INDEX IF NOT EXISTS ix_notif_user_unread ON notifications(user_id, is_read)",
]


async def main():
    url = str(settings.DATABASE_URL)
    print(f"Connecting to: {url[:40]}...")
    engine = create_async_engine(url, echo=False)

    async with engine.begin() as conn:
        for sql in SQL_COMMANDS:
            sql = sql.strip()
            if not sql:
                continue
            try:
                await conn.execute(__import__("sqlalchemy").text(sql))
                # Print first 70 chars of statement
                preview = sql.replace('\n', ' ').strip()[:70]
                print(f"  OK: {preview}")
            except Exception as e:
                print(f"  SKIP ({e!s:.80})")

    await engine.dispose()
    print("\nDone! All missing columns applied.")
    print("Now restart the server: uvicorn app.main:app --reload")


if __name__ == "__main__":
    asyncio.run(main())
