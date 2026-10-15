"""Builds the Slack client (once, in lifespan) and the notifier. Owned by #7."""

from typing import Any

from slack_sdk.web.async_client import AsyncWebClient

from app.core.config import Settings
from app.schemas.intake import (
    DECISION_BY_STATUS,
    DECISION_LABEL,
    Decision,
    IntakeDetail,
)
from app.slack.base import SlackNotifier
from app.slack.message import escape, headline, intake_blocks, quote

ACTION_ID_BY_DECISION = {
    Decision.APPROVE: "intake_approve",
    Decision.REQUEST_CHANGES: "intake_request_changes",
}
APPROVE_ACTION_ID = ACTION_ID_BY_DECISION[Decision.APPROVE]
REQUEST_CHANGES_ACTION_ID = ACTION_ID_BY_DECISION[Decision.REQUEST_CHANGES]

CHANGE_REQUEST_CALLBACK_ID = "intake_change_request"
"""``callback_id`` of the form that asks what should change."""
CHANGE_REASON_BLOCK_ID = "change_reason"
CHANGE_REASON_ACTION_ID = "reason"
CHANGE_REASON_MAX_LENGTH = 1000


class NoopNotifier:
    """``SlackNotifier`` that posts nothing; used when Slack isn't configured."""

    async def post_intake_ready(self, intake: IntakeDetail) -> str | None:
        """Post nothing.

        Args:
            intake: The Intake that is ready (ignored).

        Returns:
            Always ``None``: there is no Slack message.
        """
        return None

    async def update_decision(self, intake: IntakeDetail) -> None:
        """Edit nothing.

        Args:
            intake: The decided Intake (ignored).
        """
        return None

    async def open_change_request(self, intake: IntakeDetail, trigger_id: str) -> None:
        """Open nothing.

        Args:
            intake: The Intake (ignored).
            trigger_id: The click's trigger (ignored).
        """
        return None


class SlackWebNotifier:
    """``SlackNotifier`` that posts and edits messages through the Web API."""

    def __init__(
        self, client: AsyncWebClient, channel_id: str, dashboard_url: str = ""
    ) -> None:
        """Store the Slack Web API client, the target channel and dashboard URL."""
        self._client = client
        self._channel_id = channel_id
        self._dashboard_url = dashboard_url

    async def post_intake_ready(self, intake: IntakeDetail) -> str | None:
        """Post the "intake ready" message with Approve and Request changes buttons.

        The message lists Issues and partial verdicts with reasons, Current
        Systems, the proposed setup and the access to request, so the reviewer
        can decide from Slack.

        Args:
            intake: The Intake now awaiting approval.

        Returns:
            The Slack message timestamp (``ts``), used later to edit the message.
        """
        value = str(intake.id)
        blocks: list[dict[str, Any]] = [
            *intake_blocks(intake, self._dashboard_url),
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
            channel=self._channel_id, text=headline(intake), blocks=blocks
        )
        return str(response["ts"])

    async def update_decision(self, intake: IntakeDetail) -> None:
        """Replace the buttons with the decision and who made it.

        The details stay, so the message records what was decided on.

        Args:
            intake: The decided Intake; nothing happens if it has no ``slack_ts``.
        """
        if intake.slack_ts is None:
            return
        label = DECISION_LABEL[DECISION_BY_STATUS[intake.status]]
        decision = f"{label} by <@{intake.approved_by}>"
        outcome = f"*{decision}*"
        if intake.change_reason:
            outcome += f"\n{quote(intake.change_reason)}"
        await self._client.chat_update(
            channel=self._channel_id,
            ts=intake.slack_ts,
            text=f"{intake.client_name}: {decision}",
            blocks=[
                *intake_blocks(intake, self._dashboard_url),
                {"type": "section", "text": {"type": "mrkdwn", "text": outcome}},
            ],
        )

    async def open_change_request(self, intake: IntakeDetail, trigger_id: str) -> None:
        """Open a form asking the reviewer what should change.

        Submitting it sends a ``view_submission`` to ``/slack/actions`` carrying
        the Intake ID in ``private_metadata``.

        Args:
            intake: The Intake whose Request changes button was clicked.
            trigger_id: The click's ``trigger_id``.
        """
        await self._client.views_open(
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "callback_id": CHANGE_REQUEST_CALLBACK_ID,
                "private_metadata": str(intake.id),
                "title": {"type": "plain_text", "text": "Request changes"},
                "submit": {"type": "plain_text", "text": "Request changes"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{escape(headline(intake))}*",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": CHANGE_REASON_BLOCK_ID,
                        "label": {"type": "plain_text", "text": "What should change?"},
                        "element": {
                            "type": "plain_text_input",
                            "action_id": CHANGE_REASON_ACTION_ID,
                            "multiline": True,
                            "max_length": CHANGE_REASON_MAX_LENGTH,
                            "placeholder": {
                                "type": "plain_text",
                                "text": "e.g. Mike ruled out an app; drop that access.",
                            },
                        },
                    },
                ],
            },
        )


def build_slack_client(settings: Settings) -> AsyncWebClient | None:
    """Create the Slack Web API client, or ``None`` when no bot token is set."""
    token = settings.slack_bot_token.get_secret_value()
    return AsyncWebClient(token=token) if token else None


async def close_slack_client(client: AsyncWebClient | None) -> None:
    """Close the client's aiohttp session, if one was ever opened."""
    session = client.session if client is not None else None
    if session is not None and not session.closed:
        await session.close()


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
    return SlackWebNotifier(
        slack_client, settings.slack_channel_id, settings.dashboard_url
    )
