"""create estimates table

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "estimates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("project_name", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="in_progress"),
        sa.Column("wizard_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("project_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("progress", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "regenerated_from_estimate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("estimates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("grand_total", sa.Float(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_estimates_user_id", "estimates", ["user_id"], unique=False)
    op.create_index(
        "ix_estimates_regenerated_from_estimate_id",
        "estimates",
        ["regenerated_from_estimate_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_estimates_regenerated_from_estimate_id", table_name="estimates")
    op.drop_index("ix_estimates_user_id", table_name="estimates")
    op.drop_table("estimates")
