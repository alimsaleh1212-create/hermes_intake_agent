"""Slack interactivity routes (``POST /slack/actions``). Owned by #7.

The handler must verify Slack's signature and timestamp, acknowledge within
3 seconds, and apply the Approval via ``IntakeService.record_decision``.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/slack", tags=["slack"])
