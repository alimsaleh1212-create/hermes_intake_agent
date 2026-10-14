"""Add intakes.fallback_reason: why an Intake left the primary model.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("intakes", sa.Column("fallback_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("intakes", "fallback_reason")
