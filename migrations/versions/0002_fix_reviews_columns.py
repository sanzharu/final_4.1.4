"""Fix reviews table: add missing columns, fix column types

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def get_column_info(table_name: str):
    bind = op.get_bind()
    insp = inspect(bind)
    return {c["name"]: c for c in insp.get_columns(table_name)}


def upgrade() -> None:
    cols = get_column_info("reviews")

    # 1. Add is_spoiler (missing column)
    if "is_spoiler" not in cols:
        op.add_column(
            "reviews",
            sa.Column("is_spoiler", sa.Boolean(), nullable=False, server_default="false")
        )

    # 2. Add helpful_count (missing column)
    if "helpful_count" not in cols:
        op.add_column(
            "reviews",
            sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0")
        )

    # 3. Fix is_hidden: INTEGER -> BOOLEAN
    if "is_hidden" in cols:
        col_type = str(cols["is_hidden"]["type"]).upper()
        if "INTEGER" in col_type or col_type in ("INT", "INT4", "INT8"):
            op.alter_column(
                "reviews", "is_hidden",
                type_=sa.Boolean(),
                existing_nullable=False,
                postgresql_using="is_hidden::boolean"
            )

    # 4. Fix rating: INTEGER -> FLOAT (if needed)
    if "rating" in cols:
        col_type = str(cols["rating"]["type"]).upper()
        if "INTEGER" in col_type or col_type in ("INT", "INT4"):
            op.alter_column(
                "reviews", "rating",
                type_=sa.Float(),
                existing_nullable=False,
                postgresql_using="rating::float"
            )

    # 5. Add created_at if missing (Base adds it)
    if "created_at" not in cols:
        op.add_column(
            "reviews",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()")
            )
        )

    # 6. Add updated_at if missing
    if "updated_at" not in cols:
        op.add_column(
            "reviews",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()")
            )
        )


def downgrade() -> None:
    cols = get_column_info("reviews")
    for col in ["is_spoiler", "helpful_count"]:
        if col in cols:
            op.drop_column("reviews", col)
    # Revert is_hidden back to integer
    if "is_hidden" in cols:
        op.alter_column(
            "reviews", "is_hidden",
            type_=sa.Integer(),
            existing_nullable=False,
            postgresql_using="is_hidden::integer"
        )
