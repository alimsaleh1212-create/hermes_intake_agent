"""``LLMClient`` over OpenAI-compatible chat completions (Groq, then OpenRouter).

Fallback triggers (no retry within a provider): timeout or connection error, any
non-200 status, a 200 body that carries ``error`` or no ``choices``, empty content,
and content that is not valid JSON or fails Intake Output validation.

Privacy: failure reasons name only the model and a category. Provider bodies are
never copied into errors, because they could echo prompt text.
"""

import logging
from dataclasses import dataclass, field, replace
from typing import Any

import httpx
from pydantic import ValidationError

from app.llm.base import PRIMARY, AllModelsFailedError, LLMResult
from app.schemas.intake import IntakeOutput

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Provider:
    """One OpenAI-compatible provider in the ordered list.

    Attributes:
        name: Short label used in logs.
        base_url: API base URL (``/chat/completions`` is appended).
        api_key: Bearer token.
        model: Model ID to request.
        extra_body: Extra request fields merged into the JSON body.
        extra_headers: Extra request headers.
    """

    name: str
    base_url: str
    api_key: str = field(repr=False)
    model: str
    extra_body: dict[str, Any] = field(default_factory=dict)
    extra_headers: dict[str, str] = field(default_factory=dict)


class _ProviderFailure(Exception):
    """A provider could not give a valid Intake Output (message is a category).

    ``reason`` is the short code stored as the Intake's ``fallback_reason``.
    """

    def __init__(self, message: str, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason or message


class OpenAICompatLLMClient:
    """Tries providers in order until one returns a valid Intake Output."""

    def __init__(
        self,
        providers: list[Provider],
        http_client: httpx.AsyncClient,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._providers = providers
        self._http = http_client
        self._timeout = timeout_seconds

    async def complete_intake(
        self, system_prompt: str, user_prompt: str, *, start_at: int = PRIMARY
    ) -> LLMResult:
        """Produce an Intake Output, falling through the provider list.

        Raises:
            AllModelsFailedError: No provider from ``start_at`` onwards succeeded.
        """
        failures: list[str] = []
        first_reason: str | None = None
        for position in range(start_at, len(self._providers)):
            provider = self._providers[position]
            try:
                result = await self._call(
                    provider, position, system_prompt, user_prompt
                )
                return replace(result, fallback_reason=first_reason)
            except _ProviderFailure as failure:
                logger.warning("LLM provider %s failed: %s", provider.name, failure)
                first_reason = first_reason or failure.reason
                failures.append(f"{provider.model}: {failure}")
        raise AllModelsFailedError("All models failed (" + "; ".join(failures) + ")")

    async def _call(
        self, provider: Provider, position: int, system_prompt: str, user_prompt: str
    ) -> LLMResult:
        body: dict[str, Any] = {
            "model": provider.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "intake_output",
                    "strict": True,
                    "schema": IntakeOutput.model_json_schema(),
                },
            },
            "stream": False,
            **provider.extra_body,
        }
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            **provider.extra_headers,
        }
        try:
            response = await self._http.post(
                f"{provider.base_url.rstrip('/')}/chat/completions",
                json=body,
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as error:
            raise _ProviderFailure("timeout") from error
        except httpx.HTTPError as error:
            raise _ProviderFailure(
                f"connection error ({type(error).__name__})", "gateway_unreachable"
            ) from error

        if response.status_code != 200:
            raise _ProviderFailure(
                f"HTTP {response.status_code}", f"provider {response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise _ProviderFailure("response was not JSON") from error
        if not isinstance(payload, dict) or "error" in payload:
            raise _ProviderFailure("provider returned an error body")

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise _ProviderFailure("response had no choices") from error
        if not isinstance(content, str) or not content.strip():
            raise _ProviderFailure("empty reply")
        try:
            output = IntakeOutput.model_validate_json(content)
        except ValidationError as error:
            raise _ProviderFailure("invalid Intake Output", "invalid_output") from error

        usage = payload.get("usage") or {}
        return LLMResult(
            output=output,
            model=provider.model,
            position=position,
            tokens_in=int(usage.get("prompt_tokens") or 0),
            tokens_out=int(usage.get("completion_tokens") or 0),
        )
