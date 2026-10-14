"""Builds the ``LLMClient``. Owned by #4."""

import httpx

from app.core.config import Settings
from app.llm.base import PRIMARY, AllModelsFailedError, LLMClient, LLMResult


class _UnavailableLLMClient:
    """Placeholder until #4 lands: every call fails like an all-models failure."""

    async def complete_intake(
        self, system_prompt: str, user_prompt: str, *, start_at: int = PRIMARY
    ) -> LLMResult:
        raise AllModelsFailedError("LLMClient is not implemented yet")


def build_llm_client(settings: Settings, http_client: httpx.AsyncClient) -> LLMClient:
    """Return the ``LLMClient`` for these settings (Groq, then OpenRouter).

    Args:
        settings: Provider keys, base URLs, model IDs, timeout and price table.
        http_client: The shared client created in the app lifespan.
    """
    return _UnavailableLLMClient()
