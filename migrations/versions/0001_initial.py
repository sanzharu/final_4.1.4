"""Initial schema

Revision ID: 0001
Revises: 
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    # Tables are auto-created by SQLAlchemy in seed script;
    # this migration exists as the baseline marker.
    # For full production use, generate via: alembic revision --autogenerate -m "initial"


def downgrade() -> None:
    pass
