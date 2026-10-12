from functools import lru_cache

from app.config import Settings, get_settings
from app.llm.base import LLMProvider


def build_provider(settings: Settings) -> LLMProvider | None:
    """Return the configured provider, or None for deterministic demo mode."""
    if not settings.llm_enabled:
        return None
    if settings.llm_provider in ("groq", "xai"):
        from app.llm.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider(
            name=settings.llm_provider,
            api_key=settings.llm_api_key,
            model=settings.llm_model_name,
            base_url=settings.groq_base_url if settings.llm_provider == "groq" else settings.xai_base_url,
            reasoning_effort=settings.llm_reasoning_effort,
            timeout=settings.llm_timeout_seconds,
        )
    if settings.llm_provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=settings.llm_api_key,
            model=settings.llm_model_name,
            effort=settings.llm_effort,
            timeout=settings.llm_timeout_seconds,
            refusal_fallback=settings.llm_refusal_fallback,
        )
    return None


@lru_cache
def get_provider() -> LLMProvider | None:
    return build_provider(get_settings())
