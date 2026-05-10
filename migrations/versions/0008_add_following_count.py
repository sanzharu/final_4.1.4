"""Add missing following_count column to users table

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-10 00:00:00.000000

This fixes a bug where directly registered users could not be saved because
the 'following_count' column was present in the User model but missing from
all previous migrations.
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    user_cols = [c['name'] for c in insp.get_columns('users')]

    if 'following_count' not in user_cols:
        op.add_column(
            'users',
            sa.Column('following_count', sa.Integer(), nullable=False, server_default='0')
        )
        print("  OK: added following_count to users")
    else:
        print("  SKIP: following_count already exists in users")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    user_cols = [c['name'] for c in insp.get_columns('users')]
    if 'following_count' in user_cols:
        op.drop_column('users', 'following_count')
