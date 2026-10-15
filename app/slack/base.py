"""The Slack notifier contract used by ``IntakeService``."""

from typing import Protocol

from app.schemas.intake import IntakeDetail


class SlackNotifier(Protocol):
    """Announces Intakes in Slack and reflects Approvals there."""

    async def post_intake_ready(self, intake: IntakeDetail) -> str | None:
        """Post the "New intake" message with Approve / Request changes buttons.

        Args:
            intake: An Intake in ``awaiting_approval`` with its Intake Output.

        Returns:
            The message ``ts`` to store as ``slack_ts``, or ``None`` when posting
            was skipped (no bot token configured).
        """
        ...

    async def update_decision(self, intake: IntakeDetail) -> None:
        """Edit the original message to show the decision and who made it.

        Removes the buttons and shows the change reason, if any. Does nothing
        when ``intake.slack_ts`` is ``None`` or no bot token is configured.
        """
        ...

    async def open_change_request(self, intake: IntakeDetail, trigger_id: str) -> None:
        """Open the form asking the reviewer what should change.

        Args:
            intake: The Intake whose Request changes button was clicked.
            trigger_id: The click's ``trigger_id``; Slack honours it for 3 s.
        """
        ...
