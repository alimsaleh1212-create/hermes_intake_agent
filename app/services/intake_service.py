"""``IntakeService``: the Intake use cases. Never writes SQL; uses the repository."""

import hashlib
import logging
from dataclasses import dataclass
from uuid import UUID

from app.agents.base import IntakeAgent, IntakeAgentError
from app.db.repository import IntakeRepository
from app.guardrails.base import InjectionDetector, Redactor
from app.schemas.intake import (
    DECISION_STATUS,
    Decision,
    IntakeCreate,
    IntakeDetail,
    IntakeStatus,
)
from app.slack.base import SlackNotifier

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Submission:
    """Outcome of ``IntakeService.submit``.

    Attributes:
        intake: The new Intake, or the existing one for a duplicate.
        created: True when a new Intake was stored and needs ``process``.
    """

    intake: IntakeDetail
    created: bool


def hash_transcript(transcript_redacted: str) -> str:
    """SHA-256 hex digest of the Redacted Transcript (the duplicate key)."""
    return hashlib.sha256(transcript_redacted.encode("utf-8")).hexdigest()


class IntakeService:
    """Submits, processes, lists and decides Intakes."""

    def __init__(
        self,
        repository: IntakeRepository,
        agent: IntakeAgent,
        redactor: Redactor,
        detector: InjectionDetector,
        notifier: SlackNotifier,
    ) -> None:
        """Store the collaborators the use cases need."""
        self._repository = repository
        self._agent = agent
        self._redactor = redactor
        self._detector = detector
        self._notifier = notifier

    async def submit(self, submission: IntakeCreate) -> Submission:
        """Redact, flag, hash and store a new Intake in ``processing``.

        The raw Transcript goes no further than this method: only the Redacted
        Transcript is flagged, hashed and stored.

        Duplicate handling (#6): if an Intake with the same hash exists and has
        not failed, return it with ``created=False`` and store nothing.
        """
        transcript_redacted = self._redactor.redact(submission.transcript)
        transcript_hash = hash_transcript(transcript_redacted)
        existing = await self._repository.find_latest_by_hash(transcript_hash)
        if existing is not None and existing.status != IntakeStatus.FAILED:
            logger.info(
                "Duplicate submission: returning Intake %s (status=%s)",
                existing.id,
                existing.status,
            )
            return Submission(intake=existing, created=False)
        intake = await self._repository.create(
            client_name=submission.client_name,
            transcript_redacted=transcript_redacted,
            transcript_hash=transcript_hash,
            injection_flagged=self._detector.is_flagged(transcript_redacted),
        )
        logger.info("Intake %s submitted (status=%s)", intake.id, intake.status)
        return Submission(intake=intake, created=True)

    async def process(self, intake_id: UUID) -> None:
        """Run the agent for an Intake in ``processing`` (as a background task).

        On success, stores the Intake Output and usage, moves to
        ``awaiting_approval``, and posts the Slack message (storing ``slack_ts``).
        If the agent fails, the Intake moves to ``failed`` with the error, so
        nothing stays stuck in ``processing``. A Slack failure never fails the
        Intake.
        """
        intake = await self._repository.get(intake_id)
        if intake is None:
            return
        try:
            result = await self._agent.run(intake.transcript_redacted)
        except IntakeAgentError as error:
            await self._repository.mark_failed(intake_id, str(error))
            logger.error("Intake %s failed: %s", intake_id, error)
            return
        except Exception as error:  # noqa: BLE001 - never leave it in processing
            # Only the type name: messages (e.g. validation errors) may echo text.
            logger.error("Intake %s failed: %s", intake_id, type(error).__name__)
            await self._repository.mark_failed(
                intake_id, f"Unexpected error: {type(error).__name__}"
            )
            return
        ready = await self._repository.complete(intake_id, result.output, result.usage)
        if ready is not None:
            logger.info(
                "Intake %s status=%s cost_usd=%s est_cost_usd=%s duration_ms=%s",
                ready.id,
                ready.status,
                ready.cost_usd,
                ready.est_cost_usd,
                ready.duration_ms,
            )
            await self._announce(ready)

    async def _announce(self, intake: IntakeDetail) -> None:
        try:
            slack_ts = await self._notifier.post_intake_ready(intake)
        except Exception as error:  # noqa: BLE001 - Slack must not fail the Intake
            logger.error(
                "Slack post failed for Intake %s: %s", intake.id, type(error).__name__
            )
            return
        if slack_ts is not None:
            await self._repository.set_slack_ts(intake.id, slack_ts)

    async def list_intakes(self) -> list[IntakeDetail]:
        """Return all Intakes, newest first."""
        return await self._repository.list_newest_first()

    async def get_intake(self, intake_id: UUID) -> IntakeDetail | None:
        """Return one Intake, or ``None`` if unknown."""
        return await self._repository.get(intake_id)

    async def start_change_request(self, intake_id: UUID, trigger_id: str) -> None:
        """Open the Slack form asking the reviewer what should change.

        Does nothing unless the Intake is ``awaiting_approval``, so a click on a
        decided Intake opens no form. A Slack failure is logged, never raised.
        """
        intake = await self._repository.get(intake_id)
        if intake is None or intake.status != IntakeStatus.AWAITING_APPROVAL:
            return
        try:
            await self._notifier.open_change_request(intake, trigger_id)
        except Exception as error:  # noqa: BLE001 - the click must still be acked
            logger.error(
                "Slack form failed for Intake %s: %s", intake_id, type(error).__name__
            )

    async def record_decision(
        self,
        intake_id: UUID,
        decision: Decision,
        decided_by: str,
        change_reason: str | None = None,
    ) -> IntakeDetail | None:
        """Apply an Approval from Slack (#7).

        Moves ``awaiting_approval`` to ``approved`` or ``changes_requested`` and
        records ``approved_by``, ``decided_at`` and, for Request changes, the
        reviewer's ``change_reason``, then edits the Slack message. From any
        other status nothing changes, so repeated clicks are harmless.

        Returns:
            The updated Intake, or ``None`` if nothing changed.
        """
        decided = await self._repository.apply_decision(
            intake_id, DECISION_STATUS[decision], decided_by, change_reason
        )
        if decided is None:
            return None
        try:
            await self._notifier.update_decision(decided)
        except Exception as error:  # noqa: BLE001 - the decision is already saved
            logger.error(
                "Slack update failed for Intake %s: %s", intake_id, type(error).__name__
            )
        return decided
