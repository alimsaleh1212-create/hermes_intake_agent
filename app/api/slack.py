"""Slack interactivity routes (``POST /slack/actions``).

The handler verifies Slack's signature and timestamp, acknowledges at once and
applies the Approval in a background task so the 3 second limit is never at risk.
"""

import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response

from app.deps import IntakeServiceDep, SettingsDep
from app.schemas.intake import Decision
from app.slack.factory import ACTION_ID_BY_DECISION

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["slack"])

DECISIONS = {
    action_id: decision for decision, action_id in ACTION_ID_BY_DECISION.items()
}


def _is_valid_signature(
    secret: str, max_age: int, body: bytes, timestamp: str, signature: str
) -> bool:
    if not secret or not timestamp or not signature:
        return False
    try:
        age = abs(time.time() - int(timestamp))
    except ValueError:
        return False
    if age > max_age:
        return False
    base = b"v0:" + timestamp.encode() + b":" + body
    expected = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _parse_decision(body: bytes) -> tuple[UUID, Decision, str] | None:
    """Extract (intake id, decision, Slack user id) from a block_actions body."""
    try:
        form = urllib.parse.parse_qs(body.decode())
        payload: dict[str, Any] = json.loads(form["payload"][0])
        action = payload["actions"][0]
        decision = DECISIONS[action["action_id"]]
        return UUID(action["value"]), decision, str(payload["user"]["id"])
    except (KeyError, IndexError, ValueError, TypeError, UnicodeDecodeError):
        return None


@router.post("/actions", include_in_schema=False)
async def slack_actions(
    request: Request,
    background_tasks: BackgroundTasks,
    service: IntakeServiceDep,
    settings: SettingsDep,
) -> Response:
    """Handle Approve / Request changes clicks; always acks 200 once verified."""
    body = await request.body()
    if not _is_valid_signature(
        settings.slack_signing_secret.get_secret_value(),
        settings.slack_signature_max_age_seconds,
        body,
        request.headers.get("X-Slack-Request-Timestamp", ""),
        request.headers.get("X-Slack-Signature", ""),
    ):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")
    parsed = _parse_decision(body)
    if parsed is not None:
        intake_id, decision, user_id = parsed
        background_tasks.add_task(service.record_decision, intake_id, decision, user_id)
    return Response(status_code=200)
