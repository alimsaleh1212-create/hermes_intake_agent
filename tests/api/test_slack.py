"""Slack Approval callbacks (``POST /slack/actions``), through the HTTP seam."""

import json
import time
import urllib.parse
import uuid
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from slack_sdk.signature import SignatureVerifier

from app.core.config import Settings
from app.deps import get_notifier, get_settings
from tests.api.test_intakes import submit
from tests.fakes import RecordingNotifier

SECRET = "test-signing-secret"


@pytest.fixture(autouse=True)
def signing_secret(app: FastAPI, settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"slack_signing_secret": SecretStr(SECRET)}
    )


def signed_request(
    intake_id: str,
    action_id: str = "intake_approve",
    timestamp: int | None = None,
    secret: str = SECRET,
    user_id: str = "U123",
) -> dict[str, Any]:
    payload = {
        "type": "block_actions",
        "user": {"id": user_id, "username": "jane"},
        "actions": [{"action_id": action_id, "value": intake_id}],
    }
    body = urllib.parse.urlencode({"payload": json.dumps(payload)})
    ts = str(int(time.time()) if timestamp is None else timestamp)
    signature = SignatureVerifier(secret).generate_signature(timestamp=ts, body=body)
    return {
        "content": body,
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": signature,
        },
    }


async def status_of(client: httpx.AsyncClient, intake_id: str) -> dict[str, Any]:
    return (await client.get(f"/intakes/{intake_id}")).json()


async def test_ready_message_is_posted_once_after_completion(
    api_client: httpx.AsyncClient, notifier: RecordingNotifier
) -> None:
    intake_id = (await submit(api_client)).json()["id"]

    assert len(notifier.posted) == 1
    assert str(notifier.posted[0].id) == intake_id
    assert (await status_of(api_client, intake_id))["slack_ts"] is not None


async def test_signed_approve_approves_and_edits_the_message(
    api_client: httpx.AsyncClient, notifier: RecordingNotifier
) -> None:
    intake_id = (await submit(api_client)).json()["id"]

    response = await api_client.post("/slack/actions", **signed_request(intake_id))

    assert response.status_code == 200
    body = await status_of(api_client, intake_id)
    assert body["status"] == "approved"
    assert body["approved_by"] == "U123"
    assert body["decided_at"] is not None
    assert [str(i.id) for i in notifier.updated] == [intake_id]
    assert notifier.updated[0].status == "approved"


async def test_signed_request_changes(api_client: httpx.AsyncClient) -> None:
    intake_id = (await submit(api_client)).json()["id"]

    response = await api_client.post(
        "/slack/actions", **signed_request(intake_id, "intake_request_changes")
    )

    assert response.status_code == 200
    body = await status_of(api_client, intake_id)
    assert body["status"] == "changes_requested"
    assert body["approved_by"] == "U123"


async def test_bad_signature_is_rejected_and_changes_nothing(
    api_client: httpx.AsyncClient, notifier: RecordingNotifier
) -> None:
    intake_id = (await submit(api_client)).json()["id"]

    response = await api_client.post(
        "/slack/actions", **signed_request(intake_id, secret="wrong")
    )

    assert response.status_code == 401
    assert (await status_of(api_client, intake_id))["status"] == "awaiting_approval"
    assert notifier.updated == []


async def test_stale_timestamp_is_rejected(api_client: httpx.AsyncClient) -> None:
    intake_id = (await submit(api_client)).json()["id"]

    response = await api_client.post(
        "/slack/actions",
        **signed_request(intake_id, timestamp=int(time.time()) - 3600),
    )

    assert response.status_code == 401
    assert (await status_of(api_client, intake_id))["status"] == "awaiting_approval"


async def test_missing_or_malformed_headers_are_rejected(
    api_client: httpx.AsyncClient,
) -> None:
    request = signed_request(str(uuid.uuid4()))
    request["headers"]["X-Slack-Request-Timestamp"] = "not-a-number"

    assert (await api_client.post("/slack/actions", **request)).status_code == 401
    assert (await api_client.post("/slack/actions", content="x")).status_code == 401


async def test_unconfigured_signing_secret_rejects_everything(
    app: FastAPI, settings: Settings, api_client: httpx.AsyncClient
) -> None:
    app.dependency_overrides[get_settings] = lambda: settings
    intake_id = (await submit(api_client)).json()["id"]

    response = await api_client.post("/slack/actions", **signed_request(intake_id))

    assert response.status_code == 401


async def test_repeated_click_changes_nothing_and_still_acks(
    api_client: httpx.AsyncClient, notifier: RecordingNotifier
) -> None:
    intake_id = (await submit(api_client)).json()["id"]
    await api_client.post("/slack/actions", **signed_request(intake_id))

    again = await api_client.post(
        "/slack/actions",
        **signed_request(intake_id, "intake_request_changes", user_id="U999"),
    )

    assert again.status_code == 200
    body = await status_of(api_client, intake_id)
    assert body["status"] == "approved"
    assert body["approved_by"] == "U123"
    assert len(notifier.updated) == 1


async def test_unknown_intake_and_unknown_action_still_ack(
    api_client: httpx.AsyncClient, notifier: RecordingNotifier
) -> None:
    unknown = await api_client.post(
        "/slack/actions", **signed_request(str(uuid.uuid4()))
    )
    garbage = await api_client.post("/slack/actions", **signed_request("not-a-uuid"))
    other = await api_client.post(
        "/slack/actions", **signed_request(str(uuid.uuid4()), "something_else")
    )

    assert [unknown.status_code, garbage.status_code, other.status_code] == [200] * 3
    assert notifier.updated == []


async def test_without_a_token_intake_is_ready_and_nothing_is_posted(
    app: FastAPI, api_client: httpx.AsyncClient
) -> None:
    app.dependency_overrides.pop(get_notifier)

    intake_id = (await submit(api_client)).json()["id"]
    body = await status_of(api_client, intake_id)

    assert body["status"] == "awaiting_approval"
    assert body["slack_ts"] is None
