"""``SlackWebNotifier`` against a recording fake of the Slack Web API client."""

from typing import Any

from app.agents.fake import MIKES_ROOFING_OUTPUT
from app.core.config import Settings
from app.schemas.intake import IntakeDetail, IntakeStatus
from app.slack.factory import (
    NoopNotifier,
    SlackWebNotifier,
    build_notifier,
    close_slack_client,
)


class FakeSlackClient:
    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []

    async def chat_postMessage(self, **kwargs: Any) -> dict[str, Any]:
        self.posts.append(kwargs)
        return {"ok": True, "ts": "111.222", "channel": kwargs["channel"]}

    async def chat_update(self, **kwargs: Any) -> dict[str, Any]:
        self.updates.append(kwargs)
        return {"ok": True}


def make_intake(**overrides: Any) -> IntakeDetail:
    values: dict[str, Any] = {
        "id": "7b0f7c0e-3f0a-4a53-9d5a-0d5d6a1c9f11",
        "client_name": "Mike's Roofing",
        "status": IntakeStatus.AWAITING_APPROVAL,
        "created_at": "2026-10-14T10:00:00Z",
        "transcript_redacted": "t",
        "transcript_hash": "h",
        "output": MIKES_ROOFING_OUTPUT,
        "slack_ts": "111.222",
    }
    values.update(overrides)
    return IntakeDetail(**values)


def notifier(client: FakeSlackClient) -> SlackWebNotifier:
    return SlackWebNotifier(client, "C1")  # type: ignore[arg-type]


async def test_post_has_counts_and_two_buttons_carrying_the_intake_id() -> None:
    client = FakeSlackClient()
    intake = make_intake()

    ts = await notifier(client).post_intake_ready(intake)

    assert ts == "111.222"
    post = client.posts[0]
    assert post["channel"] == "C1"
    assert (
        post["text"] == "New intake: Mike's Roofing. 3 systems found, 1 issue flagged"
    )
    actions = [b for b in post["blocks"] if b["type"] == "actions"][0]
    assert [(e["action_id"], e["value"]) for e in actions["elements"]] == [
        ("intake_approve", str(intake.id)),
        ("intake_request_changes", str(intake.id)),
    ]
    assert "Injection" not in str(post["blocks"])


async def test_injection_flag_adds_a_warning() -> None:
    client = FakeSlackClient()

    await notifier(client).post_intake_ready(make_intake(injection_flagged=True))

    assert "Injection Flag" in str(client.posts[0]["blocks"])


async def test_update_replaces_the_buttons_with_the_decision() -> None:
    client = FakeSlackClient()

    await notifier(client).update_decision(
        make_intake(status=IntakeStatus.APPROVED, approved_by="U123")
    )
    await notifier(client).update_decision(
        make_intake(status=IntakeStatus.CHANGES_REQUESTED, approved_by="U9")
    )

    approved, changes = client.updates
    assert approved["channel"] == "C1" and approved["ts"] == "111.222"
    assert approved["text"].endswith("Approved by <@U123>")
    assert "actions" not in [b["type"] for b in approved["blocks"]]
    assert changes["text"].endswith("Changes requested by <@U9>")


async def test_update_without_slack_ts_does_nothing() -> None:
    client = FakeSlackClient()

    await notifier(client).update_decision(
        make_intake(status=IntakeStatus.APPROVED, approved_by="U1", slack_ts=None)
    )

    assert client.updates == []


def test_factory_returns_noop_without_a_client() -> None:
    settings = Settings(_env_file=None, slack_channel_id="C1")

    assert isinstance(build_notifier(settings, None), NoopNotifier)
    assert isinstance(
        build_notifier(settings, FakeSlackClient()),  # type: ignore[arg-type]
        SlackWebNotifier,
    )


async def test_close_slack_client_closes_an_open_session() -> None:
    class Session:
        closed = False

        async def close(self) -> None:
            self.closed = True

    class Client:
        session = Session()

    await close_slack_client(Client())  # type: ignore[arg-type]
    await close_slack_client(None)

    assert Client.session.closed
