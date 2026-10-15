"""Slack interactivity routes (``POST /slack/actions``).

The handler verifies Slack's signature and timestamp, acknowledges at once and
applies the Approval in a background task so the 3 second limit is never at risk.

Approve decides straight away. Request changes first opens a form (its
``trigger_id`` expires after 3 s, so that call is made before the ack); the
form's ``view_submission`` then records the decision with the reason.
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
from fastapi.responses import JSONResponse

from app.deps import IntakeServiceDep, SettingsDep
from app.schemas.intake import Decision
from app.slack.factory import (
    APPROVE_ACTION_ID,
    CHANGE_REASON_ACTION_ID,
    CHANGE_REASON_BLOCK_ID,
    CHANGE_REQUEST_CALLBACK_ID,
    REQUEST_CHANGES_ACTION_ID,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["slack"])

PARSE_ERRORS = (KeyError, IndexError, ValueError, TypeError, UnicodeDecodeError)


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


def _parse_payload(body: bytes) -> dict[str, Any] | None:
    """The JSON ``payload`` field of an interactivity request, if well formed."""
    try:
        payload = json.loads(urllib.parse.parse_qs(body.decode())["payload"][0])
    except PARSE_ERRORS:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_click(payload: dict[str, Any]) -> tuple[str, UUID, str, str] | None:
    """Extract (action id, intake id, Slack user id, trigger id) from a click."""
    try:
        action = payload["actions"][0]
        return (
            str(action["action_id"]),
            UUID(action["value"]),
            str(payload["user"]["id"]),
            str(payload.get("trigger_id", "")),
        )
    except PARSE_ERRORS:
        return None


def _parse_reason(payload: dict[str, Any]) -> tuple[UUID, str, str] | None:
    """Extract (intake id, Slack user id, reason) from the change-request form."""
    try:
        view = payload["view"]
        if view["callback_id"] != CHANGE_REQUEST_CALLBACK_ID:
            return None
        values = view["state"]["values"]
        reason = values[CHANGE_REASON_BLOCK_ID][CHANGE_REASON_ACTION_ID]["value"]
        return (
            UUID(view["private_metadata"]),
            str(payload["user"]["id"]),
            str(reason or "").strip(),
        )
    except PARSE_ERRORS:
        return None


@router.post("/actions", include_in_schema=False)
async def slack_actions(
    request: Request,
    background_tasks: BackgroundTasks,
    service: IntakeServiceDep,
    settings: SettingsDep,
) -> Response:
    """Handle button clicks and the change-request form; acks once verified."""
    body = await request.body()
    if not _is_valid_signature(
        settings.slack_signing_secret.get_secret_value(),
        settings.slack_signature_max_age_seconds,
        body,
        request.headers.get("X-Slack-Request-Timestamp", ""),
        request.headers.get("X-Slack-Signature", ""),
    ):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")
    payload = _parse_payload(body)
    if payload is None:
        return Response(status_code=200)
    if payload.get("type") == "view_submission":
        submitted = _parse_reason(payload)
        if submitted is None:
            return Response(status_code=200)
        intake_id, user_id, reason = submitted
        if not reason:
            return JSONResponse(
                {
                    "response_action": "errors",
                    "errors": {CHANGE_REASON_BLOCK_ID: "Say what should change."},
                }
            )
        background_tasks.add_task(
            service.record_decision,
            intake_id,
            Decision.REQUEST_CHANGES,
            user_id,
            reason,
        )
        return Response(status_code=200)
    click = _parse_click(payload)
    if click is not None:
        action_id, intake_id, user_id, trigger_id = click
        if action_id == APPROVE_ACTION_ID:
            background_tasks.add_task(
                service.record_decision, intake_id, Decision.APPROVE, user_id
            )
        elif action_id == REQUEST_CHANGES_ACTION_ID and trigger_id:
            await service.start_change_request(intake_id, trigger_id)
    return Response(status_code=200)
