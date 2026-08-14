"""add generation archive timestamp

Revision ID: 202608130002
Revises: 202608130001
Create Date: 2026-08-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202608130002"
down_revision: str | None = "202608130001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generation_jobs", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("generation_jobs", "archived_at")
