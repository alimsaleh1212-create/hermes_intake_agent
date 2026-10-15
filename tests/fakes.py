"""Test doubles injected through dependency overrides."""

from app.schemas.intake import IntakeDetail


class RecordingNotifier:
    """A ``SlackNotifier`` that records calls instead of talking to Slack."""

    def __init__(self, slack_ts: str | None = "1700000000.000100") -> None:
        self.slack_ts = slack_ts
        self.posted: list[IntakeDetail] = []
        self.updated: list[IntakeDetail] = []
        self.opened: list[tuple[IntakeDetail, str]] = []

    async def post_intake_ready(self, intake: IntakeDetail) -> str | None:
        self.posted.append(intake)
        return self.slack_ts

    async def update_decision(self, intake: IntakeDetail) -> None:
        self.updated.append(intake)

    async def open_change_request(self, intake: IntakeDetail, trigger_id: str) -> None:
        self.opened.append((intake, trigger_id))


class BrokenNotifier(RecordingNotifier):
    """A ``SlackNotifier`` whose posts fail, as when Slack is down."""

    async def post_intake_ready(self, intake: IntakeDetail) -> str | None:
        raise ConnectionError("slack unreachable")
