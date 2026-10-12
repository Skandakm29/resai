"""``LLMProvider`` for OpenAI-compatible Chat Completions APIs.

Used for Groq (default) and xAI Grok. Requests a JSON-schema
``response_format`` (structured outputs). The result is still re-validated
by the caller; schema enforcement on the provider side is a convenience.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.llm.base import LLMError

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        model: str,
        base_url: str,
        reasoning_effort: str = "",
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.name = name
        self._model = model
        self._reasoning_effort = reasoning_effort.strip()
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    def generate_json(
        self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int, model: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model or self._model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "assistant_output", "schema": schema, "strict": True},
            },
        }
        if self._reasoning_effort:
            body["reasoning_effort"] = self._reasoning_effort
        try:
            response = self._client.post("/chat/completions", json=body)
        except httpx.TimeoutException as exc:
            raise LLMError("LLM request timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError("LLM unreachable") from exc

        if response.status_code in (401, 403):
            raise LLMError("LLM credentials rejected")
        if response.status_code == 429:
            raise LLMError("LLM rate limited")
        if response.status_code >= 400:
            raise LLMError(f"LLM API error {response.status_code}: {response.text[:200]}")

        try:
            choice = response.json()["choices"][0]
            message = choice["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM returned an unexpected response shape") from exc

        if message.get("refusal"):
            raise LLMError("LLM declined the request")
        if choice.get("finish_reason") == "length":
            raise LLMError("LLM output truncated")
        text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            raise LLMError("LLM returned no text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("LLM returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise LLMError("LLM returned non-object JSON")
        return data
