"""create bsr_items table

Revision ID: 0001
Revises: 
Create Date: 2026-03-22

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "bsr_items" in inspector.get_table_names():
        return

    op.create_table(
        "bsr_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("item_no", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("work_type", sa.Text(), nullable=True),
        sa.Column("material_type", sa.Text(), nullable=True),
        sa.Column("method", sa.Text(), nullable=True),
        sa.Column("constraints", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.UniqueConstraint("item_no", name="uq_bsr_items_item_no"),
    )

    op.create_index("ix_bsr_items_item_no", "bsr_items", ["item_no"], unique=False)
    op.create_index("ix_bsr_items_category", "bsr_items", ["category"], unique=False)
    op.create_index("ix_bsr_items_work_type", "bsr_items", ["work_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_bsr_items_work_type", table_name="bsr_items")
    op.drop_index("ix_bsr_items_category", table_name="bsr_items")
    op.drop_index("ix_bsr_items_item_no", table_name="bsr_items")
    op.drop_table("bsr_items")
