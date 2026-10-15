"""Direct-LLM IntakeAgent seam, with provider HTTP faked at the transport."""

import json
from collections.abc import Callable

import httpx
import pytest
from fastapi import FastAPI

from app.agents.base import IntakeAgent, IntakeAgentError
from app.agents.factory import build_agent
from app.core.config import Settings
from app.deps import get_agent
from app.schemas.intake import IntakeOutput
from tests.llm.test_client import FAILURES, GROQ_URL, OPENROUTER_MODEL, ok

REDACTED = "Mike: call me at [PHONE_1]. We use WordPress."


def make_agent(
    groq: Callable[[httpx.Request], httpx.Response],
    openrouter: Callable[[httpx.Request], httpx.Response],
    calls: list[httpx.Request] | None = None,
) -> IntakeAgent:
    def route(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        return (groq if str(request.url) == GROQ_URL else openrouter)(request)

    settings = Settings(_env_file=None, hermes_enabled=False)
    return build_agent(
        settings, httpx.AsyncClient(transport=httpx.MockTransport(route))
    )


async def test_primary_success_has_no_fallback_and_an_estimated_cost() -> None:
    agent = make_agent(lambda r: ok(prompt=1000, completion=200), lambda r: ok())

    result = await agent.run(REDACTED)

    usage = result.usage
    assert isinstance(result.output, IntakeOutput)
    assert usage.model_used == "openai/gpt-oss-120b"
    assert usage.fallback_used is False
    assert (usage.tokens_in, usage.tokens_out) == (1000, 200)
    assert usage.cost_usd == 0
    # 1000 * $0.15/M + 200 * $0.60/M
    assert usage.est_cost_usd == pytest.approx(0.00027)
    assert usage.duration_ms >= 0


async def test_secondary_is_priced_at_its_own_published_rate() -> None:
    agent = make_agent(
        FAILURES["429"], lambda r: ok(prompt=1_000_000, completion=1_000_000)
    )

    usage = (await agent.run(REDACTED)).usage

    assert usage.model_used == OPENROUTER_MODEL
    assert usage.fallback_used is True
    assert usage.cost_usd == 0
    # $0.08/M in + $0.45/M out
    assert usage.est_cost_usd == pytest.approx(0.53)


async def test_transcript_is_wrapped_in_tags_and_treated_as_data() -> None:
    calls: list[httpx.Request] = []
    agent = make_agent(lambda r: ok(), lambda r: ok(), calls)

    await agent.run(REDACTED)

    messages = json.loads(calls[0].content)["messages"]
    system, user = messages[0]["content"], messages[1]["content"]
    assert user == f"<transcript>\n{REDACTED}\n</transcript>"
    assert "data" in system.lower() and "never" in system.lower()
    assert "<transcript>" in system
    assert REDACTED not in system


async def test_both_models_failing_raises_an_agent_error_without_transcript() -> None:
    agent = make_agent(FAILURES["401"], FAILURES["500"])

    with pytest.raises(IntakeAgentError) as error:
        await agent.run(REDACTED)

    assert "All models failed" in str(error.value)
    assert "WordPress" not in str(error.value)


async def test_direct_agent_completes_an_intake_through_the_api(
    app: FastAPI, api_client: httpx.AsyncClient
) -> None:
    app.dependency_overrides.pop(get_agent)
    app.state.settings.hermes_enabled = False
    app.state.http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: (
                FAILURES["401"](r)
                if str(r.url) == GROQ_URL
                else ok(prompt=2000, completion=500)
            )
        )
    )

    created = await api_client.post(
        "/intakes", json={"client_name": "Mike's Roofing", "transcript": REDACTED}
    )
    body = (await api_client.get(f"/intakes/{created.json()['id']}")).json()

    assert body["status"] == "awaiting_approval"
    assert body["model_used"] == OPENROUTER_MODEL
    assert body["fallback_used"] is True
    assert (body["tokens_in"], body["tokens_out"]) == (2000, 500)
    assert body["cost_usd"] == 0
    assert body["est_cost_usd"] == pytest.approx(0.00016 + 0.000225)
    assert body["output"]["current_systems"]


async def test_primary_success_has_no_fallback_reason() -> None:
    agent = make_agent(lambda r: ok(), lambda r: ok())

    assert (await agent.run(REDACTED)).usage.fallback_reason is None


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        ("timeout", "timeout"),
        ("429", "provider 429"),
        ("503", "provider 503"),
        ("schema_mismatch", "invalid_output"),
        ("connect_error", "gateway_unreachable"),
    ],
)
async def test_fallback_to_the_secondary_records_why(failure: str, reason: str) -> None:
    agent = make_agent(FAILURES[failure], lambda r: ok())

    usage = (await agent.run(REDACTED)).usage

    assert usage.fallback_used is True
    assert usage.fallback_reason == reason
