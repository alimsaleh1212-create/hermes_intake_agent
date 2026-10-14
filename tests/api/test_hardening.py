"""Submission hardening through the HTTP seam: auth, duplicates, failures, CORS, logs."""

import logging

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from app.agents.base import IntakeAgentError
from app.agents.fake import FakeAgent
from tests.api.test_intakes import MIKES_ROOFING, submit

PAYLOAD = {"client_name": "Mike's Roofing", "transcript": MIKES_ROOFING}


async def test_missing_api_key_is_rejected(
    anonymous_client: httpx.AsyncClient, fake_agent: FakeAgent
) -> None:
    response = await anonymous_client.post("/intakes", json=PAYLOAD)

    assert response.status_code == 401
    assert fake_agent.calls == []


async def test_wrong_api_key_is_rejected(anonymous_client: httpx.AsyncClient) -> None:
    response = await anonymous_client.post(
        "/intakes", json=PAYLOAD, headers={"X-API-Key": "nope"}
    )

    assert response.status_code == 401


async def test_get_endpoints_need_no_api_key(
    api_client: httpx.AsyncClient, anonymous_client: httpx.AsyncClient
) -> None:
    intake_id = (await submit(api_client)).json()["id"]

    listing = await anonymous_client.get("/intakes")
    detail = await anonymous_client.get(f"/intakes/{intake_id}")

    assert listing.status_code == 200
    assert detail.status_code == 200


async def test_unset_server_api_key_rejects_every_submission(
    app: FastAPI, anonymous_client: httpx.AsyncClient
) -> None:
    app.state.settings.intake_api_key = SecretStr("")

    response = await anonymous_client.post(
        "/intakes", json=PAYLOAD, headers={"X-API-Key": ""}
    )

    assert response.status_code == 401


async def test_duplicate_returns_the_existing_intake_without_a_second_run(
    api_client: httpx.AsyncClient, fake_agent: FakeAgent
) -> None:
    first = await submit(api_client)
    second = await submit(api_client)

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(fake_agent.calls) == 1
    assert len((await api_client.get("/intakes")).json()) == 1


async def test_duplicate_is_detected_on_the_redacted_transcript(
    api_client: httpx.AsyncClient, fake_agent: FakeAgent
) -> None:
    first = await submit(api_client, transcript="Call me on a@example.com please.")
    second = await submit(api_client, transcript="Call me on a@example.com please.")

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(fake_agent.calls) == 1


async def test_duplicate_of_a_failed_intake_starts_a_fresh_one(
    api_client: httpx.AsyncClient, fake_agent: FakeAgent
) -> None:
    fake_agent.error = IntakeAgentError("all models failed")
    first = await submit(api_client)
    fake_agent.error = None

    second = await submit(api_client)

    assert second.status_code == 202
    assert second.json()["id"] != first.json()["id"]
    body = (await api_client.get(f"/intakes/{second.json()['id']}")).json()
    assert body["status"] == "awaiting_approval"


async def test_failing_agent_marks_the_intake_failed_with_the_error(
    api_client: httpx.AsyncClient, fake_agent: FakeAgent
) -> None:
    fake_agent.error = IntakeAgentError("all models failed")

    intake_id = (await submit(api_client)).json()["id"]
    body = (await api_client.get(f"/intakes/{intake_id}")).json()

    assert body["status"] == "failed"
    assert body["error"] == "all models failed"


async def test_cors_preflight_allows_the_configured_origin(
    anonymous_client: httpx.AsyncClient,
) -> None:
    response = await anonymous_client.options(
        "/intakes",
        headers={
            "Origin": "https://dashboard.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://dashboard.example.com"
    )


async def test_cors_preflight_refuses_another_origin(
    anonymous_client: httpx.AsyncClient,
) -> None:
    response = await anonymous_client.options(
        "/intakes",
        headers={
            "Origin": "https://evil.example.org",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"client_name": "Mike's Roofing"},
        {"transcript": "Hello"},
        {"client_name": "", "transcript": "Hello"},
        {"client_name": "Mike's Roofing", "transcript": ""},
        {"client_name": "   ", "transcript": "Hello"},
        {"client_name": "Mike's Roofing", "transcript": "   "},
    ],
)
async def test_missing_or_empty_fields_give_422(
    api_client: httpx.AsyncClient, payload: dict[str, str]
) -> None:
    response = await api_client.post("/intakes", json=payload)

    assert response.status_code == 422


async def test_no_log_record_contains_transcript_text(
    api_client: httpx.AsyncClient,
    fake_agent: FakeAgent,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "Zebra-quartz-7731 mentioned the vault door code"
    transcript = f"{secret}. Email boss@example.com or call 415-555-0134."
    caplog.set_level(logging.DEBUG)

    ok = await submit(api_client, "Logging Co", transcript)
    fake_agent.error = IntakeAgentError("all models failed")
    await submit(api_client, "Logging Co", transcript + " again")

    assert ok.status_code == 202
    assert caplog.records
    for record in caplog.records:
        text = record.getMessage()
        assert "Zebra-quartz-7731" not in text
        assert "boss@example.com" not in text
        assert "415-555-0134" not in text


async def test_completion_is_logged_with_the_intake_id_and_status(
    api_client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    intake_id = (await submit(api_client)).json()["id"]

    messages = [r.getMessage() for r in caplog.records if r.name.startswith("app.")]
    assert any(intake_id in m and "awaiting_approval" in m for m in messages)
