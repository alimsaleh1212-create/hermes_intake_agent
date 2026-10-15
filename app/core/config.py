"""Application settings, read from the environment and ``.env`` (case-insensitive).

Every configuration field the spec needs lives here with a safe default, so later
tickets read settings rather than add them. Secrets are ``SecretStr`` and are
empty by default; an empty secret means "not configured".
"""

from typing import Annotated

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class ModelPrice(BaseModel):
    """Published paid price of one model, in USD per million tokens."""

    input_per_mtok: float = 0.0
    output_per_mtok: float = 0.0


PRIMARY_MODEL = "openai/gpt-oss-120b"
SECONDARY_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"


def _default_model_prices() -> dict[str, ModelPrice]:
    """Published paid prices in USD per million tokens, retrieved 2026-10-14.

    Sources:
    - Groq ``openai/gpt-oss-120b``: $0.15 input / $0.60 output.
      https://console.groq.com/docs/model/openai/gpt-oss-120b
      https://console.groq.com/docs/models
    - OpenRouter ``nvidia/nemotron-3-super-120b-a12b`` (the paid sibling of the
      ``:free`` model): $0.08 input / $0.45 output, the model-level listed price
      (``pricing.prompt`` 0.00000008, ``pricing.completion`` 0.00000045 per token).
      https://openrouter.ai/api/v1/models
      https://openrouter.ai/api/v1/models/nvidia/nemotron-3-super-120b-a12b/endpoints

    Reasoning tokens are billed as output and are included in completion tokens.
    """
    return {
        PRIMARY_MODEL: ModelPrice(input_per_mtok=0.15, output_per_mtok=0.60),
        SECONDARY_MODEL: ModelPrice(input_per_mtok=0.08, output_per_mtok=0.45),
    }


class Settings(BaseSettings):
    """All runtime configuration for the API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- General ---
    log_level: str = "INFO"

    # --- Database (production: Supabase EU, port 5432, never the 6543 pooler) ---
    database_url: str = "postgresql+asyncpg://intake:intake@localhost:5432/intake"

    # --- Models (OpenAI-compatible providers, primary then secondary) ---
    groq_api_key: SecretStr = SecretStr("")
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = PRIMARY_MODEL
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = SECONDARY_MODEL
    llm_timeout_seconds: float = 60.0
    model_prices: dict[str, ModelPrice] = Field(default_factory=_default_model_prices)

    # --- Hermes gateway (on the host) ---
    hermes_enabled: bool = True
    hermes_base_url: str = "http://127.0.0.1:8643"
    hermes_api_key: SecretStr = SecretStr("")
    hermes_timeout_seconds: float = 60.0

    # --- Slack Approval ---
    slack_bot_token: SecretStr = SecretStr("")
    slack_signing_secret: SecretStr = SecretStr("")
    slack_channel_id: str = ""
    slack_signature_max_age_seconds: int = 300
    dashboard_url: str = ""  # base URL for the Slack message's dashboard link

    # --- API surface ---
    intake_api_key: SecretStr = SecretStr("")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string as well as a list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value
