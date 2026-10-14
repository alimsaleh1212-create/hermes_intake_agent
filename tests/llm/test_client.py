"""LLMClient seam: ordered providers over OpenAI-compatible APIs (MockTransport)."""

import json
from collections.abc import Callable

import httpx
import pytest

from app.agents.fake import MIKES_ROOFING_OUTPUT
from app.core.config import Settings
from app.llm.base import PRIMARY, SECONDARY, AllModelsFailedError, LLMClient, LLMResult
from app.llm.factory import build_llm_client

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"
OPENROUTER_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

Handler = Callable[[httpx.Request], httpx.Response]


def ok(
    content: str | None = None, prompt: int = 100, completion: int = 50
) -> httpx.Response:
    body = {
        "choices": [
            {
                "message": {
                    "content": (
                        content
                        if content is not None
                        else MIKES_ROOFING_OUTPUT.model_dump_json()
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
    }
    return httpx.Response(200, json=body)


def make_client(
    groq: Handler, openrouter: Handler, calls: list[httpx.Request]
) -> LLMClient:
    def route(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        handler = groq if str(request.url) == GROQ_URL else openrouter
        return handler(request)

    settings = Settings(
        _env_file=None, groq_api_key="g-key", openrouter_api_key="o-key"
    )
    http = httpx.AsyncClient(transport=httpx.MockTransport(route))
    return build_llm_client(settings, http)


async def complete(client: LLMClient, start_at: int = PRIMARY) -> LLMResult:
    return await client.complete_intake(
        "system", "<transcript>t</transcript>", start_at=start_at
    )


async def test_primary_success_returns_parsed_output_and_usage() -> None:
    calls: list[httpx.Request] = []
    client = make_client(
        lambda r: ok(prompt=1000, completion=200), lambda r: ok(), calls
    )

    result = await complete(client)

    assert result.output == MIKES_ROOFING_OUTPUT
    assert result.model == GROQ_MODEL
    assert result.position == PRIMARY
    assert (result.tokens_in, result.tokens_out) == (1000, 200)
    assert len(calls) == 1
    assert calls[0].headers["authorization"] == "Bearer g-key"


async def test_request_uses_strict_json_schema_structured_output() -> None:
    calls: list[httpx.Request] = []
    client = make_client(lambda r: ok(), lambda r: ok(), calls)

    await complete(client)

    body = json.loads(calls[0].content)
    assert body["model"] == GROQ_MODEL
    assert body["stream"] is False
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    fmt = body["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True
    schema = fmt["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "current_systems",
        "architecture",
        "access_checklist",
        "feasibility",
    }


async def test_openrouter_requires_parameters_support() -> None:
    calls: list[httpx.Request] = []
    client = make_client(lambda r: ok(), lambda r: ok(), calls)

    await complete(client, start_at=SECONDARY)

    body = json.loads(calls[0].content)
    assert body["provider"] == {"require_parameters": True}
    assert calls[0].headers["authorization"] == "Bearer o-key"


def raise_timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("slow", request=request)


def raise_connect(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("down", request=request)


FAILURES: dict[str, Handler] = {
    "timeout": raise_timeout,
    "connect_error": raise_connect,
    "401": lambda r: httpx.Response(401, json={"error": {"message": "bad key"}}),
    "403": lambda r: httpx.Response(403, json={}),
    "404": lambda r: httpx.Response(404, json={}),
    "429": lambda r: httpx.Response(429, headers={"retry-after": "5"}, json={}),
    "400": lambda r: httpx.Response(400, json={}),
    "500": lambda r: httpx.Response(500, json={}),
    "503": lambda r: httpx.Response(503, json={}),
    "invalid_json": lambda r: ok("this is not json"),
    "schema_mismatch": lambda r: ok('{"current_systems": "WordPress"}'),
    "empty_content": lambda r: ok(""),
    "null_content": lambda r: httpx.Response(
        200, json={"choices": [{"message": {"content": None}}], "usage": {}}
    ),
    "error_in_200": lambda r: httpx.Response(
        200, json={"error": {"code": 502, "message": "model down"}}
    ),
    "non_json_body": lambda r: httpx.Response(200, text="<html>"),
}


@pytest.mark.parametrize("failure", FAILURES)
async def test_each_failure_moves_to_the_secondary(failure: str) -> None:
    calls: list[httpx.Request] = []
    client = make_client(FAILURES[failure], lambda r: ok(prompt=7, completion=3), calls)

    result = await complete(client)

    assert result.model == OPENROUTER_MODEL
    assert result.position == SECONDARY
    assert (result.tokens_in, result.tokens_out) == (7, 3)
    assert [str(c.url) for c in calls] == [GROQ_URL, OPENROUTER_URL]


async def test_no_retry_within_a_provider() -> None:
    calls: list[httpx.Request] = []
    client = make_client(FAILURES["429"], lambda r: ok(), calls)

    await complete(client)

    assert sum(str(c.url) == GROQ_URL for c in calls) == 1


async def test_starting_at_secondary_skips_the_primary() -> None:
    calls: list[httpx.Request] = []
    client = make_client(lambda r: ok(), lambda r: ok(), calls)

    result = await complete(client, start_at=SECONDARY)

    assert result.position == SECONDARY
    assert [str(c.url) for c in calls] == [OPENROUTER_URL]


async def test_all_models_failing_raises_a_clear_error_without_secrets() -> None:
    client = make_client(FAILURES["401"], FAILURES["timeout"], [])

    with pytest.raises(AllModelsFailedError) as error:
        await complete(client)

    message = str(error.value)
    assert "All models failed" in message
    assert GROQ_MODEL in message and OPENROUTER_MODEL in message
    assert "g-key" not in message and "o-key" not in message
    assert "<transcript>" not in message


async def test_failure_at_the_secondary_start_raises() -> None:
    client = make_client(lambda r: ok(), FAILURES["500"], [])

    with pytest.raises(AllModelsFailedError):
        await complete(client, start_at=SECONDARY)
