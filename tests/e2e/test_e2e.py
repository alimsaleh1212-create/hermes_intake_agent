"""End-to-end claims against the real compose stack (ticket #11).

The tests are ordered and share state through ``RUN``: one phase submits the three
demo Transcripts, later tests inspect and approve them, then the stack is restarted
with the primary broken to prove the Fallback. Run with ``-m e2e`` (never by default).
"""

import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.schemas.intake import IntakeOutput
from app.slack.factory import APPROVE_ACTION_ID
from tests.e2e.conftest import API_URL, COMPOSE_FILES, FALLBACK_FILES, Stack

pytestmark = pytest.mark.e2e

DEFAULTS = Settings(_env_file=None)
PRIMARY = DEFAULTS.groq_model
SECONDARY = DEFAULTS.openrouter_model
# Raw values from transcripts/pii_example.txt that must never be stored or logged.
RAW_PII = [
    "dana.whitfield@clearflowplumbing.com",
    "555-0187",
    "555-0142",
    "4821 Riverside",
]
RUN: dict[str, Any] = {}


def _is_primary(model: str) -> bool:
    return model == PRIMARY or model.endswith("/" + PRIMARY.split("/")[-1])


def _assert_no_pii(label: str, text: str) -> None:
    leaked = [i for i, raw in enumerate(RAW_PII) if raw in text]
    assert not leaked, f"{label} contains raw PII values (indexes {leaked})"


def test_submit_demo_transcripts(stack: Stack, transcript) -> None:
    """Submit Mike's Roofing, PII and injection ~30 s apart; all reach approval."""
    for key, name, file in [
        ("mikes", "Mike's Roofing", "mikes_roofing"),
        ("pii", "Clearflow Plumbing", "pii_example"),
        ("injection", "Arctic Air HVAC", "injection_example"),
    ]:
        created = stack.submit(name, transcript(file))
        assert created["status"] == "processing"
        RUN[key] = stack.wait_for(created["id"])
    for key in ("mikes", "pii", "injection"):
        detail = RUN[key]
        assert detail["status"] == "awaiting_approval", (key, detail["error"])
        IntakeOutput.model_validate(detail["output"])
        assert detail["fallback_used"] is False, (
            key,
            detail["model_used"],
            detail["fallback_reason"],
            [ln for ln in stack.logs().splitlines() if "provider" in ln],
        )
        assert _is_primary(detail["model_used"]), detail["model_used"]
        assert detail["tokens_in"] and detail["duration_ms"] is not None


def test_mikes_roofing_counts(stack: Stack) -> None:
    """Spec: 3 Current Systems and 1 Issue (a Feasibility Verdict of "no")."""
    output = RUN["mikes"]["output"]
    issues = [v for v in output["feasibility"] if v["verdict"] == "no"]
    assert len(output["current_systems"]) == 3, output["current_systems"]
    assert len(issues) == 1, [
        (v["integration"], v["verdict"]) for v in output["feasibility"]
    ]


def test_pii_is_redacted_everywhere(stack: Stack) -> None:
    detail = RUN["pii"]
    assert "[EMAIL_" in detail["transcript_redacted"]
    assert "[PHONE_" in detail["transcript_redacted"]
    api_text = json.dumps(detail) + httpx.get(f"{API_URL}/intakes").text
    _assert_no_pii("API responses", api_text)
    rows = stack.query("SELECT row_to_json(i)::text AS doc FROM intakes i")
    _assert_no_pii("database", "\n".join(row["doc"] for row in rows))


def test_injection_is_flagged(stack: Stack) -> None:
    assert RUN["injection"]["injection_flagged"] is True
    assert RUN["mikes"]["injection_flagged"] is False
    assert RUN["pii"]["injection_flagged"] is False


def _signed_slack_action(stack: Stack, intake_id: str) -> httpx.Response:
    payload = {
        "type": "block_actions",
        "user": {"id": "U_E2E_APPROVER"},
        "actions": [{"action_id": APPROVE_ACTION_ID, "value": intake_id}],
    }
    body = urllib.parse.urlencode({"payload": json.dumps(payload)}).encode()
    timestamp = str(int(time.time()))
    base = b"v0:" + timestamp.encode() + b":" + body
    signature = (
        "v0=" + hmac.new(stack.slack_secret.encode(), base, hashlib.sha256).hexdigest()
    )
    return httpx.post(
        f"{API_URL}/slack/actions",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
        timeout=10,
    )


def test_signed_slack_approve(stack: Stack) -> None:
    intake_id = RUN["mikes"]["id"]
    assert _signed_slack_action(stack, intake_id).status_code == 200
    deadline = time.monotonic() + 20
    detail: dict[str, Any] = {}
    while time.monotonic() < deadline:
        detail = httpx.get(f"{API_URL}/intakes/{intake_id}").json()
        if detail["status"] != "awaiting_approval":
            break
        time.sleep(1)
    assert detail["status"] == "approved"
    assert detail["approved_by"] == "U_E2E_APPROVER"
    assert detail["decided_at"] is not None


def test_bad_slack_signature_rejected(stack: Stack) -> None:
    response = httpx.post(
        f"{API_URL}/slack/actions",
        content=b"payload=%7B%7D",
        headers={
            "X-Slack-Request-Timestamp": str(int(time.time())),
            "X-Slack-Signature": "v0=" + "0" * 64,
        },
    )
    assert response.status_code == 401


def test_logs_have_no_raw_pii(stack: Stack) -> None:
    logs = stack.logs()
    assert "status=awaiting_approval" in logs
    _assert_no_pii("api logs", logs)


def test_forced_fallback(stack: Stack, transcript) -> None:
    """Break the primary, restart, submit a new Intake: secondary model answers."""
    stack.compose(FALLBACK_FILES, "up", "-d", "--force-recreate", "--wait", "api")
    try:
        stack.wait_healthy()
        text = transcript("mikes_roofing") + "\nAgency: Thanks, talk next week.\n"
        created = stack.submit("Mike's Roofing (fallback run)", text)
        detail = stack.wait_for(created["id"])
        assert detail["status"] == "awaiting_approval", detail["error"]
        IntakeOutput.model_validate(detail["output"])
        assert detail["fallback_used"] is True
        assert detail["model_used"] == SECONDARY or detail["model_used"].endswith(
            SECONDARY.split("/")[-1]
        ), detail["model_used"]
        _assert_no_pii("api logs (fallback)", stack.logs())
    finally:
        stack.compose(COMPOSE_FILES, "up", "-d", "--force-recreate", "--wait", "api")
