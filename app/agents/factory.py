"""Selects the ``IntakeAgent`` from configuration (``HERMES_ENABLED``)."""

import httpx

from app.agents.base import IntakeAgent
from app.agents.direct import build_direct_agent
from app.agents.hermes import build_hermes_agent
from app.core.config import Settings
from app.llm.factory import build_llm_client


def build_agent(settings: Settings, http_client: httpx.AsyncClient) -> IntakeAgent:
    """Return the Hermes-backed agent, or the direct-LLM agent when Hermes is off."""
    llm_client = build_llm_client(settings, http_client)
    if settings.hermes_enabled:
        return build_hermes_agent(settings, http_client, llm_client)
    return build_direct_agent(settings, llm_client)
