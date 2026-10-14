"""Hermes-backed ``IntakeAgent`` (``HERMES_ENABLED=true``). Owned by #5.

Layer 1 Fallback happens inside Hermes; Layer 2 (timeout, schema-invalid output,
unreachable gateway) calls ``llm_client`` starting at ``SECONDARY`` (ADR 0001).
Until #5 lands, the builder returns ``FakeAgent`` so the walking skeleton runs
end to end.
"""

import httpx

from app.agents.base import IntakeAgent
from app.agents.fake import FakeAgent
from app.core.config import Settings
from app.llm.base import LLMClient


def build_hermes_agent(
    settings: Settings, http_client: httpx.AsyncClient, llm_client: LLMClient
) -> IntakeAgent:
    """Return the agent that runs the ``client-intake`` skill via the Runs API."""
    return FakeAgent()
