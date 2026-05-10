"""Add updated_at to follows and book_subscriptions

Revision ID: 0007
Revises: 0006
Create Date: 2025-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    # Add updated_at to follows if missing
    bind = op.get_bind()
    insp = sa.inspect(bind)
    
    follows_cols = [c['name'] for c in insp.get_columns('follows')]
    if 'updated_at' not in follows_cols:
        op.add_column('follows', sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False
        ))
    
    sub_cols = [c['name'] for c in insp.get_columns('book_subscriptions')]
    if 'updated_at' not in sub_cols:
        op.add_column('book_subscriptions', sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False
        ))


def downgrade():
    pass
