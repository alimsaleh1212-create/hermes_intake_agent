"""The repository: the only module that touches SQLAlchemy sessions.

Each method is its own unit of work (one session, one transaction), so the
repository is safe to use from background tasks that outlive the request.
Methods return ``IntakeDetail`` read models, never ORM rows.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.base import AgentUsage
from app.db.models import IntakeRow
from app.schemas.intake import IntakeDetail, IntakeOutput, IntakeStatus


def _to_detail(row: IntakeRow) -> IntakeDetail:
    return IntakeDetail(
        id=row.id,
        client_name=row.client_name,
        status=IntakeStatus(row.status),
        error=row.error,
        model_used=row.model_used,
        fallback_used=row.fallback_used,
        injection_flagged=row.injection_flagged,
        tokens_in=row.tokens_in,
        tokens_out=row.tokens_out,
        cost_usd=row.cost_usd,
        est_cost_usd=row.est_cost_usd,
        duration_ms=row.duration_ms,
        approved_by=row.approved_by,
        decided_at=row.decided_at,
        created_at=row.created_at,
        transcript_redacted=row.transcript_redacted,
        transcript_hash=row.transcript_hash,
        output=(
            IntakeOutput.model_validate(row.output_json) if row.output_json else None
        ),
        slack_ts=row.slack_ts,
    )


class IntakeRepository:
    """Persistence for Intakes."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(
        self,
        *,
        client_name: str,
        transcript_redacted: str,
        transcript_hash: str,
        injection_flagged: bool,
    ) -> IntakeDetail:
        """Insert a new Intake in ``processing``."""
        async with self._session_factory() as session, session.begin():
            row = IntakeRow(
                client_name=client_name,
                transcript_redacted=transcript_redacted,
                transcript_hash=transcript_hash,
                injection_flagged=injection_flagged,
                status=IntakeStatus.PROCESSING.value,
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return _to_detail(row)

    async def get(self, intake_id: UUID) -> IntakeDetail | None:
        """Return one Intake, or ``None`` if it doesn't exist."""
        async with self._session_factory() as session:
            row = await session.get(IntakeRow, intake_id)
            return _to_detail(row) if row else None

    async def list_newest_first(self, limit: int = 200) -> list[IntakeDetail]:
        """Return Intakes ordered by creation time, newest first."""
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(IntakeRow)
                .order_by(IntakeRow.created_at.desc(), IntakeRow.id.desc())
                .limit(limit)
            )
            return [_to_detail(row) for row in rows]

    async def find_latest_by_hash(self, transcript_hash: str) -> IntakeDetail | None:
        """Return the newest Intake whose Redacted Transcript has this hash."""
        async with self._session_factory() as session:
            row = await session.scalar(
                select(IntakeRow)
                .where(IntakeRow.transcript_hash == transcript_hash)
                .order_by(IntakeRow.created_at.desc())
                .limit(1)
            )
            return _to_detail(row) if row else None

    async def complete(
        self, intake_id: UUID, output: IntakeOutput, usage: AgentUsage
    ) -> IntakeDetail | None:
        """Store the Intake Output and usage and move to ``awaiting_approval``."""
        return await self._update(
            intake_id,
            status=IntakeStatus.AWAITING_APPROVAL.value,
            output_json=output.model_dump(mode="json"),
            model_used=usage.model_used,
            fallback_used=usage.fallback_used,
            tokens_in=usage.tokens_in,
            tokens_out=usage.tokens_out,
            cost_usd=usage.cost_usd,
            est_cost_usd=usage.est_cost_usd,
            duration_ms=usage.duration_ms,
        )

    async def mark_failed(self, intake_id: UUID, error: str) -> IntakeDetail | None:
        """Move an Intake to ``failed`` and record the error."""
        return await self._update(
            intake_id, status=IntakeStatus.FAILED.value, error=error
        )

    async def set_slack_ts(self, intake_id: UUID, slack_ts: str) -> None:
        """Remember the Slack message that announced this Intake."""
        await self._update(intake_id, slack_ts=slack_ts)

    async def apply_decision(
        self, intake_id: UUID, status: IntakeStatus, decided_by: str
    ) -> IntakeDetail | None:
        """Record an Approval, only if the Intake is ``awaiting_approval``.

        The status guard makes repeated or retried clicks harmless.

        Returns:
            The updated Intake, or ``None`` if nothing changed (unknown Intake or
            not awaiting approval).
        """
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(
                update(IntakeRow)
                .where(
                    IntakeRow.id == intake_id,
                    IntakeRow.status == IntakeStatus.AWAITING_APPROVAL.value,
                )
                .values(
                    status=status.value,
                    approved_by=decided_by,
                    decided_at=datetime.now(UTC),
                )
                .returning(IntakeRow)
            )
            return _to_detail(row) if row else None

    async def _update(self, intake_id: UUID, **values: object) -> IntakeDetail | None:
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(
                update(IntakeRow)
                .where(IntakeRow.id == intake_id)
                .values(**values)
                .returning(IntakeRow)
            )
            return _to_detail(row) if row else None
