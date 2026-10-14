"""``IntakeService``: the Intake use cases. Never writes SQL; uses the repository."""

import hashlib
import logging
from dataclasses import dataclass
from uuid import UUID

from app.agents.base import IntakeAgent, IntakeAgentError
from app.db.repository import IntakeRepository
from app.guardrails.base import InjectionDetector, Redactor
from app.schemas.intake import Decision, IntakeCreate, IntakeDetail, IntakeStatus
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
        self._repository = repository
        self._agent = agent
        self._redactor = redactor
        self._detector = detector
        self._notifier = notifier

    async def submit(self, request: IntakeCreate) -> Submission:
        """Redact, flag, hash and store a new Intake in ``processing``.

        The raw Transcript goes no further than this method: only the Redacted
        Transcript is flagged, hashed and stored.

        Duplicate handling (#6): if an Intake with the same hash exists and has
        not failed, return it with ``created=False`` and store nothing.
        """
        transcript_redacted = self._redactor.redact(request.transcript)
        intake = await self._repository.create(
            client_name=request.client_name,
            transcript_redacted=transcript_redacted,
            transcript_hash=hash_transcript(transcript_redacted),
            injection_flagged=self._detector.is_flagged(transcript_redacted),
        )
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

    async def record_decision(
        self, intake_id: UUID, decision: Decision, decided_by: str
    ) -> IntakeDetail | None:
        """Apply an Approval from Slack (#7).

        Moves ``awaiting_approval`` to ``approved`` or ``changes_requested`` and
        records ``approved_by`` and ``decided_at``, then edits the Slack message.
        From any other status nothing changes, so repeated clicks are harmless.

        Returns:
            The updated Intake, or ``None`` if nothing changed.
        """
        status = (
            IntakeStatus.APPROVED
            if decision == Decision.APPROVE
            else IntakeStatus.CHANGES_REQUESTED
        )
        decided = await self._repository.apply_decision(intake_id, status, decided_by)
        if decided is None:
            return None
        try:
            await self._notifier.update_decision(decided)
        except Exception as error:  # noqa: BLE001 - the decision is already saved
            logger.error(
                "Slack update failed for Intake %s: %s", intake_id, type(error).__name__
            )
        return decided
