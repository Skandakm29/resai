"""Application settings, loaded from environment variables / .env."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Restaurant AI Assistant API"
    environment: Literal["development", "test", "production"] = "development"

    database_url: str = "postgresql+psycopg://reschat:reschat@127.0.0.1:5433/reschatbot"
    sql_echo: bool = False

    # Comma-separated list of browser origins allowed to call the API directly.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Assistant / LLM -------------------------------------------------
    # When true the assistant never calls an LLM: intent parsing and replies
    # are fully deterministic. Also the effective mode when no key is set.
    assistant_demo_mode: bool = False
    llm_provider: Literal["anthropic", "none"] = "anthropic"
    anthropic_api_key: SecretStr | None = None
    llm_model: str = "claude-opus-5-5"
    llm_effort: Literal["low", "medium", "high"] = "low"
    llm_timeout_seconds: float = 20.0
    # Server-side refusal fallback (Anthropic API beta). Disable if your
    # deployment target does not support it.
    llm_refusal_fallback: bool = True

    # --- Rate limiting (per client IP, in-process sliding window) --------
    rate_limit_enabled: bool = True
    rate_limit_chat_per_minute: int = Field(default=20, ge=1)
    rate_limit_search_per_minute: int = Field(default=60, ge=1)
    # Only trust X-Forwarded-For when running behind a proxy you control.
    trust_proxy_headers: bool = False

    # Conversations: how many prior messages are passed to the LLM parser.
    conversation_history_window: int = Field(default=8, ge=0, le=40)

    # Protects onboarding/admin endpoints. Unset = those endpoints are disabled.
    admin_api_key: SecretStr | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        return (
            not self.assistant_demo_mode
            and self.llm_provider != "none"
            and self.anthropic_api_key is not None
            and bool(self.anthropic_api_key.get_secret_value())
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
