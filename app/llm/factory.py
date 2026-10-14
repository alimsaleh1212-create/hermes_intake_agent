"""Builds the ``LLMClient``. Owned by #4."""

import httpx

from app.core.config import Settings
from app.llm.base import LLMClient
from app.llm.client import OpenAICompatLLMClient, Provider


def build_llm_client(settings: Settings, http_client: httpx.AsyncClient) -> LLMClient:
    """Return the ``LLMClient`` for these settings (Groq, then OpenRouter).

    Args:
        settings: Provider keys, base URLs, model IDs, timeout and price table.
        http_client: The shared client created in the app lifespan.
    """
    providers = [
        Provider(
            name="groq",
            base_url=settings.groq_base_url,
            api_key=settings.groq_api_key.get_secret_value(),
            model=settings.groq_model,
        ),
        Provider(
            name="openrouter",
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key.get_secret_value(),
            model=settings.openrouter_model,
            # Only route to endpoints that honour response_format.
            extra_body={"provider": {"require_parameters": True}},
        ),
    ]
    return OpenAICompatLLMClient(providers, http_client, settings.llm_timeout_seconds)
