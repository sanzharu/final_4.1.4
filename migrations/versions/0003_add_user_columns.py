"""Add missing columns to users table: website, oauth_provider, oauth_provider_id, last_login

Revision ID: 0003
Revises: 0002
Create Date: 2025-03-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def get_columns(table_name: str):
    bind = op.get_bind()
    insp = inspect(bind)
    return {c["name"] for c in insp.get_columns(table_name)}


def upgrade() -> None:
    cols = get_columns("users")

    if "website" not in cols:
        op.add_column("users", sa.Column("website", sa.String(255), nullable=True))

    if "oauth_provider" not in cols:
        op.add_column("users", sa.Column("oauth_provider", sa.String(50), nullable=True))

    if "oauth_provider_id" not in cols:
        op.add_column("users", sa.Column("oauth_provider_id", sa.String(255), nullable=True))

    if "last_login" not in cols:
        op.add_column("users", sa.Column("last_login", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    cols = get_columns("users")
    for col in ["website", "oauth_provider", "oauth_provider_id", "last_login"]:
        if col in cols:
            op.drop_column("users", col)
