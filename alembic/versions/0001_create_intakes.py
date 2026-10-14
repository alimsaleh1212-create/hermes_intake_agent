"""Create the intakes table.

Revision ID: 0001
Revises:
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "intakes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_name", sa.String(length=200), nullable=False),
        sa.Column("transcript_redacted", sa.Text(), nullable=False),
        sa.Column("transcript_hash", sa.String(length=64), nullable=False),
        sa.Column("output_json", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(length=200), nullable=True),
        sa.Column(
            "fallback_used", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "injection_flagged",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("est_cost_usd", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("slack_ts", sa.String(length=64), nullable=True),
        sa.Column("approved_by", sa.String(length=200), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'awaiting_approval', 'approved', "
            "'changes_requested', 'failed')",
            name="ck_intakes_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_intakes_transcript_hash", "intakes", ["transcript_hash"])
    op.create_index("ix_intakes_status", "intakes", ["status"])
    op.create_index("ix_intakes_created_at", "intakes", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_intakes_created_at", table_name="intakes")
    op.drop_index("ix_intakes_status", table_name="intakes")
    op.drop_index("ix_intakes_transcript_hash", table_name="intakes")
    op.drop_table("intakes")
