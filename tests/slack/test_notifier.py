"""``SlackWebNotifier`` against a recording fake of the Slack Web API client."""

from typing import Any

from app.agents.fake import MIKES_ROOFING_OUTPUT
from app.core.config import Settings
from app.schemas.intake import (
    FeasibilityVerdict,
    IntakeDetail,
    IntakeOutput,
    IntakeStatus,
)
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


def notifier(client: FakeSlackClient, dashboard_url: str = "") -> SlackWebNotifier:
    return SlackWebNotifier(client, "C1", dashboard_url)  # type: ignore[arg-type]


def block_texts(blocks: list[dict[str, Any]]) -> list[str]:
    """The visible text of each block, in order (sections, headers, contexts)."""
    texts = []
    for block in blocks:
        if "text" in block:
            texts.append(block["text"]["text"])
        for element in block.get("elements", []):
            if element.get("type") == "mrkdwn":
                texts.append(element["text"])
    return texts


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


async def test_post_shows_the_issue_first_then_partials_with_their_reasons() -> None:
    client = FakeSlackClient()

    await notifier(client).post_intake_ready(make_intake())

    text = "\n".join(block_texts(client.posts[0]["blocks"]))
    issue = text.index("Forwarding the personal cell")
    partial = text.index("Jobber to GoHighLevel")
    feasible = text.index("Google Ads to GoHighLevel")
    assert issue < partial < feasible
    assert "Use a tracking number instead." in text
    assert "Needs Zapier; no native connector." in text


async def test_post_shows_systems_proposed_setup_and_access_to_request() -> None:
    client = FakeSlackClient()

    await notifier(client).post_intake_ready(make_intake())

    text = "\n".join(block_texts(client.posts[0]["blocks"]))
    assert "WordPress, Google Ads, Jobber" in text
    assert "Missed-call text-back" in text and "Recover missed calls" in text
    assert "Jobber" in text and "API key" in text
    assert "Domain registrar" in text and "DNS access" in text


async def test_post_shows_model_fallback_duration_and_cost() -> None:
    client = FakeSlackClient()
    intake = make_intake(
        model_used="nvidia/nemotron",
        fallback_used=True,
        fallback_reason="timeout",
        duration_ms=42_300,
        cost_usd=0.0,
        est_cost_usd=0.0012,
    )

    await notifier(client).post_intake_ready(intake)

    text = "\n".join(block_texts(client.posts[0]["blocks"]))
    assert "nvidia/nemotron" in text
    assert "Fallback" in text and "timeout" in text
    assert "42.3 s" in text
    assert "$0 (≈ $0.0012 at paid rates)" in text


async def test_post_links_to_the_dashboard_detail_when_configured() -> None:
    linked, unlinked = FakeSlackClient(), FakeSlackClient()
    intake = make_intake()

    await notifier(linked, "https://dash.example/").post_intake_ready(intake)
    await notifier(unlinked).post_intake_ready(intake)

    assert f"https://dash.example/#/intakes/{intake.id}" in str(linked.posts[0])
    assert "#/intakes/" not in str(unlinked.posts[0])


async def test_post_escapes_model_text_so_it_cannot_ping_or_link() -> None:
    client = FakeSlackClient()
    output = IntakeOutput(
        current_systems=["<!channel>"],
        architecture=[],
        access_checklist=[],
        feasibility=[
            FeasibilityVerdict(
                integration="A & B", verdict="no", reason="<https://evil.example|ok>"
            )
        ],
    )

    await notifier(client).post_intake_ready(make_intake(output=output))

    text = "\n".join(block_texts(client.posts[0]["blocks"]))
    assert "<!channel>" not in text and "&lt;!channel&gt;" in text
    assert "<https://evil.example" not in text
    assert "A &amp; B" in text


async def test_post_keeps_every_block_within_slack_limits() -> None:
    client = FakeSlackClient()
    many = [
        FeasibilityVerdict(
            integration=f"System {n} to CRM", verdict="no", reason="x" * 200
        )
        for n in range(40)
    ]
    output = MIKES_ROOFING_OUTPUT.model_copy(update={"feasibility": many})

    await notifier(client).post_intake_ready(make_intake(output=output))

    blocks = client.posts[0]["blocks"]
    assert len(blocks) <= 50
    assert all(len(text) <= 3000 for text in block_texts(blocks))
    assert "more" in "\n".join(block_texts(blocks))


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
    assert "Approved by <@U123>" in "\n".join(block_texts(approved["blocks"]))
    assert changes["text"].endswith("Changes requested by <@U9>")


async def test_update_keeps_the_details_the_reviewer_decided_on() -> None:
    client = FakeSlackClient()

    await notifier(client).update_decision(
        make_intake(status=IntakeStatus.APPROVED, approved_by="U123")
    )

    text = "\n".join(block_texts(client.updates[0]["blocks"]))
    assert "Use a tracking number instead." in text
    assert "WordPress, Google Ads, Jobber" in text


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
