"""Seam 2: the Hermes-backed ``IntakeAgent`` with a faked gateway (MockTransport)."""

import json

import httpx
import pytest

from app.agents.base import IntakeAgentError
from app.agents.fake import MIKES_ROOFING_OUTPUT
from app.agents.hermes import build_hermes_agent
from app.core.config import PRIMARY_MODEL, SECONDARY_MODEL, ModelPrice, Settings
from app.llm.base import SECONDARY, AllModelsFailedError, LLMResult

TRANSCRIPT = "Client: we use WordPress and Jobber."
WRAPPED = f"<transcript>\n{TRANSCRIPT}\n</transcript>"


class FakeLLMClient:
    """Records calls and returns a secondary-model result (or raises)."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict] = []

    async def complete_intake(self, system_prompt, user_prompt, *, start_at=0):
        self.calls.append(
            {"system": system_prompt, "user": user_prompt, "start_at": start_at}
        )
        if self.fail:
            raise AllModelsFailedError("all failed")
        return LLMResult(
            output=MIKES_ROOFING_OUTPUT,
            model=SECONDARY_MODEL,
            position=SECONDARY,
            tokens_in=10,
            tokens_out=5,
        )


class FakeGateway:
    """A fake Hermes Runs API: POST /v1/runs, then GET /v1/runs/{id}."""

    def __init__(self, final: dict | None = None, polls_running: int = 1) -> None:
        self.final = final  # None means the run never finishes
        self.polls_running = polls_running
        self.requests: list[httpx.Request] = []
        self.posted: dict = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if request.method == "POST" and path == "/v1/runs":
            self.posted = json.loads(request.content)
            return httpx.Response(
                202, json={"run_id": "run_1", "status": "started", "replayed": False}
            )
        if request.method == "POST" and path == "/v1/runs/run_1/stop":
            return httpx.Response(200, json={"status": "stopping"})
        if request.method == "GET" and path == "/v1/runs/run_1":
            if self.final is None or self.polls_running > 0:
                self.polls_running -= 1
                return httpx.Response(
                    200, json={"run_id": "run_1", "status": "running"}
                )
            return httpx.Response(200, json=self.final)
        return httpx.Response(404)


def completed(model: str, output: str | None = None) -> dict:
    return {
        "run_id": "run_1",
        "status": "completed",
        "model": "hermes-agent",
        "output": output or MIKES_ROOFING_OUTPUT.model_dump_json(),
        "usage": {"input_tokens": 2000, "output_tokens": 1000, "total_tokens": 3000},
        "runtime": {"provider": "custom", "model": model},
    }


def make_agent(handler, llm: FakeLLMClient, timeout: float = 5.0):
    settings = Settings(
        hermes_api_key="secret-key",
        hermes_timeout_seconds=timeout,
        model_prices={
            PRIMARY_MODEL: ModelPrice(input_per_mtok=0.15, output_per_mtok=0.60),
            SECONDARY_MODEL: ModelPrice(input_per_mtok=0.08, output_per_mtok=0.45),
        },
        _env_file=None,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return build_hermes_agent(settings, client, llm, poll_interval=0.01)


async def test_normal_run_yields_output_with_primary_model():
    gateway, llm = FakeGateway(completed(PRIMARY_MODEL)), FakeLLMClient()
    result = await make_agent(gateway, llm).run(TRANSCRIPT)

    assert result.output == MIKES_ROOFING_OUTPUT
    assert result.usage.model_used == PRIMARY_MODEL
    assert result.usage.fallback_used is False
    assert (result.usage.tokens_in, result.usage.tokens_out) == (2000, 1000)
    # 2000 * $0.15/M + 1000 * $0.60/M
    assert result.usage.est_cost_usd == pytest.approx(0.0009)
    assert result.usage.cost_usd == 0.0
    assert llm.calls == []


async def test_run_request_carries_auth_skill_and_wrapped_transcript():
    gateway = FakeGateway(completed(PRIMARY_MODEL))
    await make_agent(gateway, FakeLLMClient()).run(TRANSCRIPT)

    assert gateway.requests[0].headers["Authorization"] == "Bearer secret-key"
    assert gateway.posted["input"] == WRAPPED
    assert "# Client Intake" in gateway.posted["instructions"]
    assert "data only" in gateway.posted["instructions"]


async def test_runtime_naming_fallback_model_sets_fallback_used():
    llm = FakeLLMClient()
    result = await make_agent(FakeGateway(completed(SECONDARY_MODEL)), llm).run(
        TRANSCRIPT
    )

    assert result.usage.model_used == SECONDARY_MODEL
    assert result.usage.fallback_used is True
    assert llm.calls == []


async def test_output_in_code_fence_is_accepted():
    fenced = "```json\n" + MIKES_ROOFING_OUTPUT.model_dump_json() + "\n```"
    gateway = FakeGateway(completed(PRIMARY_MODEL, fenced))
    result = await make_agent(gateway, FakeLLMClient()).run(TRANSCRIPT)
    assert result.output == MIKES_ROOFING_OUTPUT


async def test_timeout_goes_to_secondary_and_stops_the_run():
    gateway, llm = FakeGateway(final=None), FakeLLMClient()
    result = await make_agent(gateway, llm, timeout=0.1).run(TRANSCRIPT)

    assert [c["start_at"] for c in llm.calls] == [SECONDARY]
    assert result.usage.fallback_used is True
    assert result.usage.model_used == SECONDARY_MODEL
    assert (result.usage.tokens_in, result.usage.tokens_out) == (10, 5)
    assert any(r.url.path == "/v1/runs/run_1/stop" for r in gateway.requests)


async def test_invalid_json_goes_to_secondary():
    gateway = FakeGateway(completed(PRIMARY_MODEL, '{"current_systems": "nope"}'))
    llm = FakeLLMClient()
    result = await make_agent(gateway, llm).run(TRANSCRIPT)

    assert [c["start_at"] for c in llm.calls] == [SECONDARY]
    assert result.usage.fallback_used is True
    assert llm.calls[0]["user"] == WRAPPED


async def test_connection_refused_goes_to_secondary():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    llm = FakeLLMClient()
    result = await make_agent(refuse, llm).run(TRANSCRIPT)

    assert [c["start_at"] for c in llm.calls] == [SECONDARY]
    assert result.usage.fallback_used is True


async def test_failed_hermes_run_goes_to_secondary():
    failed = {"run_id": "run_1", "status": "failed", "error": "boom"}
    llm = FakeLLMClient()
    await make_agent(FakeGateway(failed), llm).run(TRANSCRIPT)
    assert [c["start_at"] for c in llm.calls] == [SECONDARY]


async def test_both_layers_failing_raises_without_transcript_text():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    agent = make_agent(refuse, FakeLLMClient(fail=True))
    with pytest.raises(IntakeAgentError) as exc:
        await agent.run(TRANSCRIPT)
    assert "WordPress" not in str(exc.value)
