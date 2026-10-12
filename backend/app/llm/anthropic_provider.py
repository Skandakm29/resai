"""Anthropic (Claude) implementation of ``LLMProvider`` using structured outputs."""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from app.llm.base import LLMError

logger = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        effort: str = "low",
        timeout: float = 20.0,
        refusal_fallback: bool = True,
    ) -> None:
        # One retry: this sits on an interactive request path with a
        # deterministic fallback, so failing fast beats waiting.
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=1)
        self._model = model
        self._effort = effort
        self._refusal_fallback = refusal_fallback

    def generate_json(self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int) -> dict[str, Any]:
        kwargs: dict[str, Any] = dict(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={
                "effort": self._effort,
                "format": {"type": "json_schema", "schema": schema},
            },
        )
        if self._refusal_fallback:
            # On a safety decline the API re-runs the request on a fallback
            # model inside the same call.
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        try:
            response = self._client.beta.messages.create(**kwargs)
        except anthropic.BadRequestError as exc:
            raise LLMError(f"LLM request rejected: {exc.message}") from exc
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise LLMError("LLM credentials rejected") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("LLM rate limited") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"LLM API error {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:  # includes timeouts
            raise LLMError("LLM unreachable") from exc

        if response.stop_reason == "refusal":
            raise LLMError("LLM declined the request")
        if response.stop_reason == "max_tokens":
            raise LLMError("LLM output truncated")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise LLMError("LLM returned no text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("LLM returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise LLMError("LLM returned non-object JSON")
        logger.debug("LLM call ok (request_id=%s)", getattr(response, "_request_id", None))
        return data
