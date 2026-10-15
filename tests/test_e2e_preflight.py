"""The e2e preflight checks, tested without Docker, Hermes or real keys."""

import json

from tests.e2e.preflight import env_file_problems, hermes_problems

GOOD_CONFIG = """
model:
  provider: custom:groq
  default: openai/gpt-oss-120b
"""
NO_TOOLS = json.dumps({"toolsets": [{"name": "web", "enabled": False}]})


def test_env_file_of_key_value_lines_is_fine() -> None:
    text = "# comment\n\nGROQ_API_KEY=abc\nLOG_LEVEL=\nexport X=1\n"

    assert env_file_problems(text) == []


def test_env_file_problems_name_the_line_but_never_the_value() -> None:
    text = "GOOD=1\nGROQ_API_KEY: sk-secret-value\nsk-other-secret\n"

    problems = env_file_problems(text)

    assert [p.split(":")[0] for p in problems] == ["line 2", "line 3"]
    assert "secret" not in " ".join(problems)


def test_hermes_with_no_toolsets_and_the_groq_model_is_fine() -> None:
    assert hermes_problems(NO_TOOLS, GOOD_CONFIG) == []


def test_an_enabled_toolset_is_reported() -> None:
    body = json.dumps({"toolsets": [{"name": "terminal", "enabled": True}]})

    problems = hermes_problems(body, GOOD_CONFIG)

    assert len(problems) == 1
    assert "toolset" in problems[0]


def test_a_different_model_is_reported() -> None:
    config = "model:\n  provider: openrouter\n  default: some/other-model\n"

    problems = hermes_problems(NO_TOOLS, config)

    assert len(problems) == 1
    assert "openai/gpt-oss-120b" in problems[0]


def test_a_missing_config_is_reported() -> None:
    assert len(hermes_problems(NO_TOOLS, None)) == 1
