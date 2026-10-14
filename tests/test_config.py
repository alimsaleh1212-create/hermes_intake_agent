"""Settings are read case-insensitively from the environment."""

from pathlib import Path

import pytest

from app.core.config import Settings


def test_keys_are_read_case_insensitively(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("groq_api_key", "lower-case-name")
    monkeypatch.setenv("OPENROUTER_API_KEY", "upper-case-name")

    settings = Settings(_env_file=None)

    assert settings.groq_api_key.get_secret_value() == "lower-case-name"
    assert settings.openrouter_api_key.get_secret_value() == "upper-case-name"


def test_cors_origins_accept_a_comma_separated_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS", "https://intake.vercel.app, http://localhost:5173"
    )

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "https://intake.vercel.app",
        "http://localhost:5173",
    ]


def test_secrets_are_not_revealed_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTAKE_API_KEY", "do-not-print-me")

    settings = Settings(_env_file=None)

    assert "do-not-print-me" not in repr(settings)


def test_env_example_lists_every_setting() -> None:
    env_example = Path(__file__).resolve().parents[1] / ".env.example"
    documented = {
        line.lstrip("# ").split("=", 1)[0].strip().lower()
        for line in env_example.read_text().splitlines()
        if "=" in line
    }

    assert set(Settings.model_fields) - documented == set()
