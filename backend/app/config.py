"""Application settings, loaded from environment variables / .env."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_MODELS = {"groq": "openai/gpt-oss-120b", "xai": "grok-4", "anthropic": "claude-opus-5-5"}


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
    llm_provider: Literal["groq", "xai", "anthropic", "none"] = "groq"
    # Empty = the provider's default (see DEFAULT_MODELS).
    llm_model: str = ""
    # Model for the reply-wording step. Empty = same as llm_model. Using a
    # different model doubles throughput on per-model rate limits (Groq).
    llm_compose_model: str = ""
    # Sent as `reasoning_effort` to Groq/xAI when non-empty.
    llm_reasoning_effort: str = "low"
    llm_timeout_seconds: float = 20.0

    # Groq and xAI (Grok) - OpenAI-compatible chat completions APIs.
    groq_api_key: SecretStr | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    xai_api_key: SecretStr | None = None
    xai_base_url: str = "https://api.x.ai/v1"

    # Anthropic (Claude).
    anthropic_api_key: SecretStr | None = None
    llm_effort: Literal["low", "medium", "high"] = "low"
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

    # --- Menu upload (onboarding) ----------------------------------------
    # Menu PDFs and photos are read by Claude whenever ANTHROPIC_API_KEY is
    # set, whatever LLM_PROVIDER the chat uses. Without it, PDFs fall back to
    # their text layer and photos are rejected.
    menu_extract_model: str = ""  # empty = DEFAULT_MODELS["anthropic"]
    menu_extract_timeout_seconds: float = Field(default=300.0, ge=10)
    menu_upload_max_mb: int = Field(default=20, ge=1, le=30)

    # Self-serve onboarding on the public landing page (no admin key).
    # Limits are per client IP per hour; reading a menu costs an LLM call.
    public_onboarding_enabled: bool = True
    public_extract_per_hour: int = Field(default=6, ge=1)
    public_publish_per_hour: int = Field(default=3, ge=1)
    public_max_items: int = Field(default=400, ge=1, le=1000)

    @property
    def menu_vision_enabled(self) -> bool:
        key = self.anthropic_api_key
        return key is not None and bool(key.get_secret_value().strip())

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        # Hosting providers (Render, Heroku, ...) hand out postgres:// or
        # postgresql:// URLs; SQLAlchemy needs the psycopg 3 driver named.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_api_key(self) -> str:
        key = {"groq": self.groq_api_key, "xai": self.xai_api_key, "anthropic": self.anthropic_api_key}.get(
            self.llm_provider
        )
        return key.get_secret_value().strip() if key is not None else ""

    @property
    def llm_model_name(self) -> str:
        return self.llm_model.strip() or DEFAULT_MODELS.get(self.llm_provider, "")

    @property
    def llm_compose_model_name(self) -> str:
        return self.llm_compose_model.strip() or self.llm_model_name

    @property
    def llm_enabled(self) -> bool:
        return not self.assistant_demo_mode and self.llm_provider != "none" and bool(self.llm_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
