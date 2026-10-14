"""Direct-LLM ``IntakeAgent`` (``HERMES_ENABLED=false``). Owned by #4.

Until #4 lands, the builder returns ``FakeAgent`` so the walking skeleton runs
end to end.
"""

import httpx

from app.agents.base import IntakeAgent
from app.agents.fake import FakeAgent
from app.core.config import Settings
from app.llm.base import LLMClient


def build_direct_agent(
    settings: Settings, http_client: httpx.AsyncClient, llm_client: LLMClient
) -> IntakeAgent:
    """Return the agent that calls the models directly, primary then secondary."""
    return FakeAgent()
