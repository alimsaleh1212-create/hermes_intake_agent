"""Fail-fast checks for the e2e suite. Pure functions: nothing here prints values.

``hermes_problems`` reads the Hermes gateway's ``/v1/toolsets`` body and the
gateway's ``config.yaml`` (the gateway has no endpoint that names its configured
model; see ``docs/research/hermes.md``).
"""

import json
import re
from typing import Any

import yaml

EXPECTED_HERMES_MODEL = "openai/gpt-oss-120b"
_ENV_LINE = re.compile(r"^(export\s+)?[A-Za-z_][A-Za-z0-9_]*=")


def env_file_problems(text: str) -> list[str]:
    """Return one message per ``.env`` line that is not ``KEY=value``.

    Blank lines and comments are fine. Messages name the line number only, never
    the line's content, because it may be a secret.
    """
    problems = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not _ENV_LINE.match(stripped):
            problems.append(f"line {number}: not KEY=value")
    return problems


def _any_enabled(node: Any) -> bool:
    if isinstance(node, dict):
        return node.get("enabled") is True or any(
            _any_enabled(value) for value in node.values()
        )
    if isinstance(node, list):
        return any(_any_enabled(item) for item in node)
    return False


def hermes_problems(toolsets_body: str, config_text: str | None) -> list[str]:
    """Check the Hermes gateway has no toolsets and uses the expected Groq model."""
    problems = []
    try:
        enabled = _any_enabled(json.loads(toolsets_body))
    except ValueError:
        enabled = bool(re.search(r'"enabled"\s*:\s*true', toolsets_body))
    if enabled:
        problems.append(
            "Hermes has an enabled toolset; /v1/toolsets must show 0 enabled "
            "(platform_toolsets.api_server: [] in config.yaml)"
        )
    if config_text is None:
        problems.append("Hermes config.yaml not found; cannot check its model")
        return problems
    try:
        model = (yaml.safe_load(config_text) or {}).get("model") or {}
    except yaml.YAMLError:
        model = {}
    default = model.get("default") if isinstance(model, dict) else None
    provider = str(model.get("provider", "")) if isinstance(model, dict) else ""
    if default != EXPECTED_HERMES_MODEL or "groq" not in provider:
        problems.append(
            f"Hermes must be configured for Groq {EXPECTED_HERMES_MODEL} "
            f"(model.provider custom:groq, model.default {EXPECTED_HERMES_MODEL})"
        )
    return problems
