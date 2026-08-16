"""add generation status message

Revision ID: 202608160002
Revises: 202608160001
Create Date: 2026-08-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202608160002"
down_revision: str | None = "202608160001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generation_jobs", sa.Column("status_message", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("generation_jobs", "status_message")
