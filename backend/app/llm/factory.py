from functools import lru_cache

from app.config import Settings, get_settings
from app.llm.base import LLMProvider


def build_provider(settings: Settings) -> LLMProvider | None:
    """Return the configured provider, or None for deterministic demo mode."""
    if not settings.llm_enabled:
        return None
    if settings.llm_provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        assert settings.anthropic_api_key is not None
        return AnthropicProvider(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.llm_model,
            effort=settings.llm_effort,
            timeout=settings.llm_timeout_seconds,
            refusal_fallback=settings.llm_refusal_fallback,
        )
    return None


@lru_cache
def get_provider() -> LLMProvider | None:
    return build_provider(get_settings())
