"""OpenAI-compatible provider (Groq / xAI) against a mocked HTTP transport - no network calls."""

import json

import httpx
import pytest

from app.config import Settings
from app.llm.base import LLMError
from app.llm.factory import build_provider
from app.llm.prompts import PARSE_SCHEMA
from app.llm.openai_compatible import OpenAICompatibleProvider


def _provider(handler):
    return OpenAICompatibleProvider(
        name="groq",
        api_key="test-key",
        model="test-model",
        base_url="https://api.groq.com/openai/v1",
        transport=httpx.MockTransport(handler),
    )


def _completion(content, finish_reason="stop", refusal=None):
    return {"choices": [{"message": {"role": "assistant", "content": content, "refusal": refusal}, "finish_reason": finish_reason}]}


def test_sends_structured_output_request_and_parses_json():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion('{"intent": "greeting"}'))

    out = _provider(handler).generate_json(system="sys", user="hi", schema=PARSE_SCHEMA, max_tokens=500)
    assert out == {"intent": "greeting"}
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["auth"] == "Bearer test-key"
    body = seen["body"]
    assert body["model"] == "test-model"
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == PARSE_SCHEMA


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, json={"error": "bad key"}),
        httpx.Response(429, json={"error": "slow down"}),
        httpx.Response(500, text="oops"),
        httpx.Response(200, json=_completion("not json")),
        httpx.Response(200, json=_completion("[1, 2]")),
        httpx.Response(200, json=_completion('{"a": 1', finish_reason="length")),
        httpx.Response(200, json=_completion(None, refusal="I can't help with that")),
        httpx.Response(200, json={"unexpected": True}),
    ],
)
def test_failures_raise_llm_error(response):
    with pytest.raises(LLMError):
        _provider(lambda request: response).generate_json(system="s", user="u", schema={}, max_tokens=10)


def test_network_errors_raise_llm_error():
    def handler(request):
        raise httpx.ConnectTimeout("timeout")

    with pytest.raises(LLMError):
        _provider(handler).generate_json(system="s", user="u", schema={}, max_tokens=10)


def test_factory_selects_provider_only_when_key_present():
    def settings(**kw):
        return Settings(_env_file=None, **{"groq_api_key": "", "xai_api_key": "", **kw})

    assert build_provider(settings(llm_provider="groq", assistant_demo_mode=False)) is None
    assert build_provider(settings(llm_provider="groq", groq_api_key="k", assistant_demo_mode=True)) is None
    groq = build_provider(settings(llm_provider="groq", groq_api_key="k", assistant_demo_mode=False))
    assert isinstance(groq, OpenAICompatibleProvider) and groq.name == "groq"
    xai = build_provider(settings(llm_provider="xai", xai_api_key="k", assistant_demo_mode=False))
    assert isinstance(xai, OpenAICompatibleProvider) and xai.name == "xai"
    assert settings(llm_provider="groq").llm_model_name == "openai/gpt-oss-120b"
    assert settings(llm_provider="xai").llm_model_name == "grok-4"
    assert settings(llm_provider="groq", llm_model="qwen/qwen3.8-27b").llm_model_name == "qwen/qwen3.8-27b"


def test_model_override_and_reasoning_effort():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=_completion("{}"))

    p = OpenAICompatibleProvider(
        name="groq", api_key="k", model="main", base_url="https://api.groq.com/openai/v1",
        reasoning_effort="low", transport=httpx.MockTransport(handler),
    )
    p.generate_json(system="s", user="u", schema={}, max_tokens=10)
    p.generate_json(system="s", user="u", schema={}, max_tokens=10, model="composer")
    assert [b["model"] for b in seen] == ["main", "composer"]
    assert all(b["reasoning_effort"] == "low" for b in seen)
