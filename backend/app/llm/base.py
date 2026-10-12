"""Provider-neutral LLM interface.

The assistant only needs one capability: "given a system prompt, a user
payload and a JSON schema, return a JSON object". Providers translate that to
their own structured-output feature. Callers always re-validate the result
with Pydantic - a provider's schema enforcement is never trusted on its own.
"""

from typing import Any, Protocol


class LLMError(Exception):
    """Any failure to obtain a usable structured response (network, refusal,
    truncation, invalid JSON). Callers fall back to deterministic logic."""


class LLMProvider(Protocol):
    name: str

    def generate_json(self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int) -> dict[str, Any]:
        ...
