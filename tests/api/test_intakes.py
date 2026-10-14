"""Submitting an Intake and seeing it completed, through the HTTP seam."""

import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI

from app.agents.base import IntakeAgentError
from app.agents.fake import FakeAgent
from app.deps import get_notifier
from tests.fakes import BrokenNotifier, RecordingNotifier

TRANSCRIPTS = Path(__file__).resolve().parents[2] / "transcripts"
MIKES_ROOFING = (TRANSCRIPTS / "mikes_roofing.txt").read_text()


async def submit(
    client: httpx.AsyncClient,
    client_name: str = "Mike's Roofing",
    transcript: str = MIKES_ROOFING,
) -> httpx.Response:
    return await client.post(
        "/intakes", json={"client_name": client_name, "transcript": transcript}
    )


async def test_submission_returns_202_with_an_intake_in_processing(
    api_client: httpx.AsyncClient,
) -> None:
    response = await submit(api_client)

    assert response.status_code == 202
    body = response.json()
    uuid.UUID(body["id"])
    assert body["client_name"] == "Mike's Roofing"
    assert body["status"] == "processing"
    assert body["output"] is None


async def test_intake_is_completed_by_the_agent_in_the_background(
    api_client: httpx.AsyncClient, fake_agent: FakeAgent
) -> None:
    intake_id = (await submit(api_client)).json()["id"]

    response = await api_client.get(f"/intakes/{intake_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "awaiting_approval"
    assert body["output"]["current_systems"] == ["WordPress", "Google Ads", "Jobber"]
    assert [v["verdict"] for v in body["output"]["feasibility"]] == [
        "yes",
        "partial",
        "no",
    ]
    assert body["model_used"] == "fake-model"
    assert body["fallback_used"] is False
    assert body["tokens_in"] == 1200
    assert body["tokens_out"] == 400
    assert body["cost_usd"] == 0.0
    assert body["est_cost_usd"] == 0.0005
    assert body["duration_ms"] == 5
    assert body["transcript_redacted"] == MIKES_ROOFING.strip()
    assert fake_agent.calls == [MIKES_ROOFING.strip()]


async def test_list_returns_summaries_newest_first(
    api_client: httpx.AsyncClient,
) -> None:
    first = (await submit(api_client, "First Roofing", "Call one.")).json()["id"]
    second = (await submit(api_client, "Second Plumbing", "Call two.")).json()["id"]

    response = await api_client.get("/intakes")

    assert response.status_code == 200
    rows = response.json()
    assert [row["id"] for row in rows] == [second, first]
    assert rows[0]["client_name"] == "Second Plumbing"
    assert rows[0]["status"] == "awaiting_approval"
    assert "output" not in rows[0]
    assert "transcript_redacted" not in rows[0]


async def test_unknown_intake_is_404(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(f"/intakes/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_intake_fails_with_the_error_when_every_model_fails(
    api_client: httpx.AsyncClient, fake_agent: FakeAgent
) -> None:
    fake_agent.error = IntakeAgentError("all models failed: primary 401, secondary 429")

    intake_id = (await submit(api_client)).json()["id"]
    body = (await api_client.get(f"/intakes/{intake_id}")).json()

    assert body["status"] == "failed"
    assert body["error"] == "all models failed: primary 401, secondary 429"
    assert body["output"] is None


async def test_ready_intake_is_announced_once_and_its_slack_ts_stored(
    api_client: httpx.AsyncClient, notifier: RecordingNotifier
) -> None:
    intake_id = (await submit(api_client)).json()["id"]
    body = (await api_client.get(f"/intakes/{intake_id}")).json()

    assert [str(intake.id) for intake in notifier.posted] == [intake_id]
    assert notifier.posted[0].status == "awaiting_approval"
    assert notifier.posted[0].output is not None
    assert body["slack_ts"] == "1700000000.000100"


async def test_failed_intake_is_not_announced(
    api_client: httpx.AsyncClient,
    fake_agent: FakeAgent,
    notifier: RecordingNotifier,
) -> None:
    fake_agent.error = IntakeAgentError("all models failed")

    await submit(api_client)

    assert notifier.posted == []


async def test_slack_failure_does_not_fail_the_intake(
    app: FastAPI, api_client: httpx.AsyncClient
) -> None:
    app.dependency_overrides[get_notifier] = lambda: BrokenNotifier()

    intake_id = (await submit(api_client)).json()["id"]
    body = (await api_client.get(f"/intakes/{intake_id}")).json()

    assert body["status"] == "awaiting_approval"
    assert body["slack_ts"] is None
