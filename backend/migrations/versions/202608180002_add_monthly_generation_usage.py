"""add monthly generation usage

Revision ID: 202608180002
Revises: 202608180001
Create Date: 2026-08-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202608180002"
down_revision: str | None = "202608180001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_usage_months",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("submitted_generations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "month", name="uq_generation_usage_months_user_month"),
    )
    op.create_index(op.f("ix_generation_usage_months_month"), "generation_usage_months", ["month"], unique=False)
    op.create_index(op.f("ix_generation_usage_months_user_id"), "generation_usage_months", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_generation_usage_months_user_id"), table_name="generation_usage_months")
    op.drop_index(op.f("ix_generation_usage_months_month"), table_name="generation_usage_months")
    op.drop_table("generation_usage_months")
