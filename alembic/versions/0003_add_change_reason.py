"""Add intakes.change_reason: what the reviewer asked to change.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("intakes", sa.Column("change_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("intakes", "change_reason")
