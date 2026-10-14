"""Harness for the e2e suite: drives the real compose stack from the outside.

Run with ``uv run pytest -m e2e tests/e2e`` (see the README "E2E runbook").
Real keys are read by the containers from ``.env``; this module never reads or
prints them. Test-only values (API key, Slack signing secret) are generated per run
and passed through the process environment.

Environment knobs:
    HERMES_ENABLED   true/false. Default: true if the gateway answers on
                     the configured Hermes URL (HERMES_BASE_URL in the environment
                     or .env, default http://127.0.0.1:8643), otherwise false
                     (direct Groq -> OpenRouter).
    E2E_SUBMIT_GAP   seconds between model calls (default 30; Groq free tier is
                     8K tokens per minute).
    E2E_KEEP_STACK   set to 1 to skip ``down -v`` at the end.
"""

import asyncio
import os
import secrets
import subprocess
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest

from tests.e2e.preflight import env_file_problems, hermes_problems

ROOT = Path(__file__).resolve().parents[2]
API_URL = "http://127.0.0.1:8000"
DEFAULT_HERMES_URL = "http://127.0.0.1:8643"


def _setting(key: str) -> str | None:
    """One setting: environment, then ``.env`` (this key only, never printed)."""
    value = os.environ.get(key)
    env_file = ROOT / ".env"
    if not value and env_file.is_file():
        for line in env_file.read_text().splitlines():
            name, _, raw = line.partition("=")
            if name.strip().upper() == key:
                value = raw.strip().strip("'\"")
    return value


def hermes_base_url() -> str:
    """The configured Hermes URL: environment, then ``.env`` (this one key only)."""
    return (_setting("HERMES_BASE_URL") or DEFAULT_HERMES_URL).rstrip("/")


def preflight(hermes: bool) -> None:
    """Fail fast, with a clear message, before the stack is built and models called.

    Checks every mode's ``.env`` format and, in Hermes mode, that the gateway has no
    enabled toolsets and is configured for Groq ``openai/gpt-oss-120b``. Messages
    never contain ``.env`` or key values.
    """
    problems: list[str] = []
    env_file = ROOT / ".env"
    if env_file.is_file():
        problems += [
            f".env {problem}" for problem in env_file_problems(env_file.read_text())
        ]
    if hermes:
        try:
            response = httpx.get(
                f"{hermes_base_url()}/v1/toolsets",
                headers={"Authorization": f"Bearer {_setting('HERMES_API_KEY') or ''}"},
                timeout=5,
            )
        except httpx.HTTPError:
            problems.append("Hermes /v1/toolsets could not be read")
        else:
            home = Path(os.environ.get("INTAKE_HERMES_HOME", "~/.hermes-intake"))
            config = home.expanduser() / "config.yaml"
            if response.status_code != 200:
                problems.append(f"Hermes /v1/toolsets returned {response.status_code}")
            else:
                problems += hermes_problems(
                    response.text,
                    config.read_text() if config.is_file() else None,
                )
    if problems:
        pytest.fail("e2e preflight failed:\n- " + "\n- ".join(problems), pytrace=False)


DB_DSN = "postgresql://intake:intake@127.0.0.1:5432/intake"
COMPOSE_FILES = ["-f", "compose.yaml", "-f", "tests/e2e/compose.e2e.yaml"]
FALLBACK_FILES = [*COMPOSE_FILES, "-f", "tests/e2e/compose.fallback.yaml"]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark everything under tests/e2e as e2e so the default run skips it."""
    for item in items:
        if "tests/e2e" in str(item.path).replace("\\", "/"):
            item.add_marker(pytest.mark.e2e)


def _hermes_up() -> bool:
    try:
        return httpx.get(f"{hermes_base_url()}/health", timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


@dataclass
class Stack:
    """Handle on the running compose stack."""

    api_key: str
    slack_secret: str
    hermes: bool
    gap: float
    env: dict[str, str]
    _last_model_call: float = 0.0

    def compose(self, files: list[str], *args: str, check: bool = True) -> str:
        """Run ``docker compose --profile dev <files> <args>``; return its output."""
        proc = subprocess.run(
            ["docker", "compose", "--profile", "dev", *files, *args],
            cwd=ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        if check and proc.returncode != 0:
            raise RuntimeError(f"docker compose {args[0]} failed:\n{proc.stderr}")
        return proc.stdout + proc.stderr

    def wait_healthy(self, timeout: float = 120) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{API_URL}/health", timeout=2).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(1)
        raise RuntimeError("api did not become healthy")

    def logs(self) -> str:
        return self.compose(COMPOSE_FILES, "logs", "--no-color", "api")

    def throttle(self) -> None:
        """Sleep so consecutive model calls are ``gap`` seconds apart."""
        wait = self._last_model_call + self.gap - time.monotonic()
        if wait > 0 and self._last_model_call:
            time.sleep(wait)
        self._last_model_call = time.monotonic()

    def submit(self, client_name: str, transcript: str) -> dict[str, Any]:
        """POST an Intake (after throttling) and return the 202 body."""
        self.throttle()
        response = httpx.post(
            f"{API_URL}/intakes",
            headers={"X-API-Key": self.api_key},
            json={"client_name": client_name, "transcript": transcript},
            timeout=30,
        )
        assert response.status_code == 202, response.status_code
        return response.json()

    def wait_for(self, intake_id: str, timeout: float = 240) -> dict[str, Any]:
        """Poll until the Intake leaves ``processing``; return its detail."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            body = httpx.get(f"{API_URL}/intakes/{intake_id}", timeout=10).json()
            if body["status"] != "processing":
                return body
            time.sleep(2)
        raise TimeoutError(f"intake {intake_id} still processing")

    def query(self, sql: str, *params: Any) -> list[asyncpg.Record]:
        async def run() -> list[asyncpg.Record]:
            conn = await asyncpg.connect(DB_DSN)
            try:
                return await conn.fetch(sql, *params)
            finally:
                await conn.close()

        return asyncio.run(run())


@pytest.fixture(scope="session")
def stack() -> Iterator[Stack]:
    hermes_env = os.environ.get("HERMES_ENABLED")
    hermes = (hermes_env.lower() == "true") if hermes_env else _hermes_up()
    if hermes and not _hermes_up():
        pytest.fail(
            f"HERMES_ENABLED=true but the gateway is not up on {hermes_base_url()}"
        )
    preflight(hermes)
    state = Stack(
        api_key=secrets.token_hex(16),
        slack_secret=secrets.token_hex(16),
        hermes=hermes,
        gap=float(os.environ.get("E2E_SUBMIT_GAP", "30")),
        env={},
    )
    state.env = {
        **os.environ,
        "E2E_INTAKE_API_KEY": state.api_key,
        "E2E_SLACK_SIGNING_SECRET": state.slack_secret,
        "E2E_HERMES_ENABLED": "true" if hermes else "false",
    }
    print(f"\n[e2e] mode: {'HERMES' if hermes else 'DIRECT (HERMES_ENABLED=false)'}")
    state.compose(COMPOSE_FILES, "down", "-v", check=False)
    state.compose(COMPOSE_FILES, "up", "-d", "--build", "--wait")
    try:
        state.wait_healthy()
        yield state
    finally:
        if os.environ.get("E2E_KEEP_STACK") != "1":
            state.compose(COMPOSE_FILES, "down", "-v", check=False)


@pytest.fixture(scope="session")
def transcript() -> Callable[[str], str]:
    return lambda name: (ROOT / "transcripts" / f"{name}.txt").read_text()
