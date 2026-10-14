"""Hermes-backed ``IntakeAgent`` (``HERMES_ENABLED=true``). Owned by #5.

Layer 1 Fallback happens inside Hermes (``fallback_providers``); Layer 2 (timeout,
schema-invalid output, unreachable gateway) calls ``llm_client`` starting at
``SECONDARY`` with no retry on the primary (ADR 0001).
"""

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from app.agents.base import AgentResult, AgentUsage, IntakeAgent, elapsed_ms
from app.agents.prompts import build_user_prompt
from app.core.config import Settings
from app.llm.base import SECONDARY, LLMClient
from app.llm.pricing import estimate_cost_usd
from app.schemas.intake import IntakeOutput

logger = logging.getLogger(__name__)

SKILL_PATH = Path(__file__).parent / "assets" / "client-intake" / "SKILL.md"
_TERMINAL = {"completed", "failed", "cancelled", "interrupted"}
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


_REASON_DETAIL_CHARS = 200


class _HermesRunError(Exception):
    """A Layer 1 failure that sends the Intake to Layer 2. Carries no Transcript.

    ``reason`` is the short code stored as the Intake's ``fallback_reason``.
    """

    def __init__(self, message: str, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason or message


def _layer1_failure(exc: Exception) -> tuple[str, str]:
    """Return ``(reason, log_message)`` for a Layer 1 failure.

    Neither string contains Transcript, prompt or output text.
    """
    if isinstance(exc, _HermesRunError):
        return exc.reason, str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return f"gateway_http_{code}", str(exc)
    if isinstance(exc, TimeoutError | httpx.TimeoutException):
        return "timeout", f"{type(exc).__name__}: no answer within the budget"
    return "gateway_unreachable", f"{type(exc).__name__}: {exc}"


def load_skill_prompt(path: Path = SKILL_PATH) -> str:
    """Return the SKILL.md body (front matter removed) for use as a system prompt."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.strip()


def _parse_output(raw: object) -> IntakeOutput:
    """Validate Hermes' final text as an Intake Output (tolerating a code fence)."""
    if not isinstance(raw, str):
        raise _HermesRunError("run output missing")
    text = raw.strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        return IntakeOutput.model_validate(json.loads(text))
    except (ValueError, ValidationError) as exc:
        raise _HermesRunError(
            "output failed Intake Output validation", "invalid_output"
        ) from exc


class HermesAgent:
    """Runs the ``client-intake`` skill through the Hermes Runs API."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
        llm_client: LLMClient,
        poll_interval: float = 1.0,
    ) -> None:
        self._settings = settings
        self._http = http_client
        self._llm = llm_client
        self._poll_interval = poll_interval
        self._system_prompt = load_skill_prompt()

    async def run(self, transcript_redacted: str) -> AgentResult:
        """Run Layer 1 (Hermes); on any failure run Layer 2 (secondary model)."""
        started = time.monotonic()
        user_prompt = build_user_prompt(transcript_redacted)
        try:
            return await self._run_hermes(user_prompt, started)
        except (_HermesRunError, httpx.HTTPError, TimeoutError) as exc:
            reason, message = _layer1_failure(exc)
            logger.warning("hermes layer 1 failed (%s); using secondary", message)
        return await self._run_secondary(user_prompt, started, reason)

    def _headers(self) -> dict[str, str]:
        key = self._settings.hermes_api_key.get_secret_value()
        return {"Authorization": f"Bearer {key}"}

    def _url(self, path: str) -> str:
        return self._settings.hermes_base_url.rstrip("/") + path

    async def _run_hermes(self, user_prompt: str, started: float) -> AgentResult:
        run_id: str | None = None
        try:
            async with asyncio.timeout(self._settings.hermes_timeout_seconds):
                response = await self._http.post(
                    self._url("/v1/runs"),
                    headers=self._headers(),
                    json={"input": user_prompt, "instructions": self._system_prompt},
                )
                response.raise_for_status()
                run_id = response.json()["run_id"]
                while True:
                    poll = await self._http.get(
                        self._url(f"/v1/runs/{run_id}"), headers=self._headers()
                    )
                    poll.raise_for_status()
                    body = poll.json()
                    if body.get("status") in _TERMINAL:
                        break
                    await asyncio.sleep(self._poll_interval)
        except TimeoutError:
            if run_id is not None:
                await self._stop_run(run_id)
            raise
        except (KeyError, ValueError) as exc:
            raise _HermesRunError("unexpected gateway response") from exc

        if body.get("status") != "completed":
            status = str(body.get("status"))
            error = body.get("error")
            detail = str(error) if error else status
            raise _HermesRunError(
                f"run ended {status}: {error}" if error else f"run ended {status}",
                "hermes_run_failed: " + detail[:_REASON_DETAIL_CHARS],
            )
        output = _parse_output(body.get("output"))
        return self._to_result(output, body, started)

    async def _stop_run(self, run_id: str) -> None:
        """Best effort: don't leak a running agent after our timeout."""
        try:
            await self._http.post(
                self._url(f"/v1/runs/{run_id}/stop"),
                headers=self._headers(),
                timeout=5.0,
            )
        except httpx.HTTPError:
            logger.warning("could not stop timed-out hermes run")

    def _to_result(
        self, output: IntakeOutput, body: dict[str, Any], started: float
    ) -> AgentResult:
        runtime = body.get("runtime") or {}
        usage = body.get("usage") or {}
        model = runtime.get("model") or "unknown"
        tokens_in = int(usage.get("input_tokens") or 0)
        tokens_out = int(usage.get("output_tokens") or 0)
        return AgentResult(
            output=output,
            usage=AgentUsage(
                model_used=model,
                fallback_used=bool(runtime.get("model"))
                and model != self._settings.groq_model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                duration_ms=elapsed_ms(started),
                est_cost_usd=estimate_cost_usd(
                    self._settings.model_prices, model, tokens_in, tokens_out
                ),
            ),
        )

    async def _run_secondary(
        self, user_prompt: str, started: float, reason: str
    ) -> AgentResult:
        result = await self._llm.complete_intake(
            self._system_prompt, user_prompt, start_at=SECONDARY
        )
        return AgentResult(
            output=result.output,
            usage=AgentUsage(
                model_used=result.model,
                fallback_used=True,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                duration_ms=elapsed_ms(started),
                est_cost_usd=estimate_cost_usd(
                    self._settings.model_prices,
                    result.model,
                    result.tokens_in,
                    result.tokens_out,
                ),
                fallback_reason=reason,
            ),
        )


def build_hermes_agent(
    settings: Settings,
    http_client: httpx.AsyncClient,
    llm_client: LLMClient,
    poll_interval: float = 1.0,
) -> IntakeAgent:
    """Return the agent that runs the ``client-intake`` skill via the Runs API."""
    return HermesAgent(settings, http_client, llm_client, poll_interval)
