"""Builds the Slack client (once, in lifespan) and the notifier. Owned by #7."""

from typing import Any

from slack_sdk.web.async_client import AsyncWebClient

from app.core.config import Settings
from app.schemas.intake import IntakeDetail, IntakeStatus
from app.slack.base import SlackNotifier

APPROVE_ACTION_ID = "intake_approve"
REQUEST_CHANGES_ACTION_ID = "intake_request_changes"


class NoopNotifier:
    """``SlackNotifier`` that posts nothing; used when Slack isn't configured."""

    async def post_intake_ready(self, intake: IntakeDetail) -> str | None:
        return None

    async def update_decision(self, intake: IntakeDetail) -> None:
        return None


class SlackWebNotifier:
    """``SlackNotifier`` that posts and edits messages through the Web API."""

    def __init__(self, client: AsyncWebClient, channel_id: str) -> None:
        self._client = client
        self._channel_id = channel_id

    async def post_intake_ready(self, intake: IntakeDetail) -> str | None:
        output = intake.output
        systems = len(output.current_systems) if output else 0
        issues = sum(v.verdict == "no" for v in output.feasibility) if output else 0
        noun = "issue" if issues == 1 else "issues"
        text = (
            f"New intake: {intake.client_name}. "
            f"{systems} systems found, {issues} {noun} flagged"
        )
        summary = f"*New intake:* {intake.client_name}\n{systems} systems found, "
        summary += f"{issues} {noun} flagged"
        if intake.injection_flagged:
            summary += "\n:warning: Injection Flag: the Transcript looked suspicious"
        value = str(intake.id)
        blocks: list[dict[str, Any]] = [
            {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
            {
                "type": "actions",
                "block_id": "intake_actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": APPROVE_ACTION_ID,
                        "style": "primary",
                        "value": value,
                        "text": {"type": "plain_text", "text": "Approve"},
                    },
                    {
                        "type": "button",
                        "action_id": REQUEST_CHANGES_ACTION_ID,
                        "style": "danger",
                        "value": value,
                        "text": {"type": "plain_text", "text": "Request changes"},
                    },
                ],
            },
        ]
        response = await self._client.chat_postMessage(
            channel=self._channel_id, text=text, blocks=blocks
        )
        return str(response["ts"])

    async def update_decision(self, intake: IntakeDetail) -> None:
        if intake.slack_ts is None:
            return
        label = (
            "Approved"
            if intake.status == IntakeStatus.APPROVED
            else "Changes requested"
        )
        decision = f"{label} by <@{intake.approved_by}>"
        await self._client.chat_update(
            channel=self._channel_id,
            ts=intake.slack_ts,
            text=f"{intake.client_name}: {decision}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{intake.client_name}*: {decision}",
                    },
                }
            ],
        )


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
    if slack_client is None or not settings.slack_channel_id:
        return NoopNotifier()
    return SlackWebNotifier(slack_client, settings.slack_channel_id)
