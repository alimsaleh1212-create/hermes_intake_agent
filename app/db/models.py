"""SQLAlchemy model for the ``intakes`` table (schema owned by Alembic)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.schemas.intake import IntakeStatus

INTAKE_STATUSES = tuple(status.value for status in IntakeStatus)


class Base(DeclarativeBase):
    """Declarative base; ``Base.metadata`` is Alembic's target metadata."""


class IntakeRow(Base):
    """One Intake: a Transcript processed once, with its status and cost."""

    __tablename__ = "intakes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('" + "', '".join(INTAKE_STATUSES) + "')",
            name="ck_intakes_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_name: Mapped[str] = mapped_column(String(200))
    transcript_redacted: Mapped[str] = mapped_column(Text)
    transcript_hash: Mapped[str] = mapped_column(String(64), index=True)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), index=True)
    error: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(200))
    fallback_used: Mapped[bool] = mapped_column(Boolean, server_default=false())
    injection_flagged: Mapped[bool] = mapped_column(Boolean, server_default=false())
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6, asdecimal=False))
    est_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6, asdecimal=False))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    slack_ts: Mapped[str | None] = mapped_column(String(64))
    approved_by: Mapped[str | None] = mapped_column(String(200))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
