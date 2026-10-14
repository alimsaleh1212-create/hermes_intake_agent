"""Builds the Slack client (once, in lifespan) and the notifier. Owned by #7."""

from slack_sdk.web.async_client import AsyncWebClient

from app.core.config import Settings
from app.schemas.intake import IntakeDetail
from app.slack.base import SlackNotifier


class NoopNotifier:
    """``SlackNotifier`` that posts nothing; used when Slack isn't configured."""

    async def post_intake_ready(self, intake: IntakeDetail) -> str | None:
        return None

    async def update_decision(self, intake: IntakeDetail) -> None:
        return None


def build_slack_client(settings: Settings) -> AsyncWebClient | None:
    """Create the Slack Web API client, or ``None`` when no bot token is set."""
    token = settings.slack_bot_token.get_secret_value()
    return AsyncWebClient(token=token) if token else None


def build_notifier(
    settings: Settings, slack_client: AsyncWebClient | None
) -> SlackNotifier:
    """Return the notifier for these settings.

    Args:
        settings: Channel ID and other Slack settings.
        slack_client: The client created in lifespan, or ``None`` (skip posting).
    """
    return NoopNotifier()
