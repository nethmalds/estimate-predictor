"""create categories table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("code", name="uq_categories_code"),
    )
    op.create_index("ix_categories_code", "categories", ["code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_categories_code", table_name="categories")
    op.drop_table("categories")
