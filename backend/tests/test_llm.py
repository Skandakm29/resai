"""LLM integration: valid output is used, invalid output and failures fall back."""

from decimal import Decimal

import pytest

from app.llm.base import LLMError
from app.llm.factory import get_provider
from app.llm.prompts import COMPOSE_SCHEMA, PARSE_SCHEMA, validate_compose_output
from app.main import app
from tests.conftest import chat


class FakeProvider:
    name = "fake"

    def __init__(self, parse=None, compose=None):
        self.parse = parse
        self.compose = compose
        self.calls: list[str] = []

    def generate_json(self, *, system, user, schema, max_tokens):
        step = "parse" if schema is PARSE_SCHEMA else "compose"
        assert schema in (PARSE_SCHEMA, COMPOSE_SCHEMA)
        self.calls.append(step)
        value = self.parse if step == "parse" else self.compose
        if isinstance(value, Exception):
            raise value
        if callable(value):
            return value(user)
        return value


def _filters(**overrides):
    base = {
        "item_types": [], "contains_coffee": None, "temperature": None, "tags_any": [], "keywords": [],
        "max_price": None, "min_price": None, "party_size": 1, "dietary": [], "exclude_allergens": [],
        "caffeine_free": False, "max_sweetness": None, "min_sweetness": None, "min_strength": None,
        "max_strength": None, "sort": "relevance",
    }
    base.update(overrides)
    return base


COFFEE_250 = {
    "intent": "recommend",
    "filters": _filters(item_types=["beverage"], contains_coffee=True, max_price=250),
    "mentioned_items": [],
    "refers_to_previous": False,
    "info_topic": None,
}


@pytest.fixture()
def use_provider():
    def _install(provider):
        app.dependency_overrides[get_provider] = lambda: provider
        return provider

    return _install


def _first_id(user_payload: str) -> str:
    import json

    return json.loads(user_payload)["results"][0]["id"]


def test_llm_path_used_when_output_valid(client, use_provider):
    provider = use_provider(
        FakeProvider(
            parse=COFFEE_250,
            compose=lambda user: {
                "message": "Here are some lovely coffees within your ₹250 budget.",
                "item_notes": [{"item_id": _first_id(user), "note": "A smooth house favourite."}],
                "follow_ups": ["Something iced?"],
            },
        )
    )
    resp = chat(client, "fancy a coffee, nothing over 250 bucks")
    assert provider.calls == ["parse", "compose"]
    assert resp["source"] == "llm"
    assert resp["message"] == "Here are some lovely coffees within your ₹250 budget."
    assert resp["recommendations"][0]["note"] == "A smooth house favourite."
    assert all(Decimal(r["item"]["price_from"]) <= 250 for r in resp["recommendations"])
    assert resp["follow_ups"] == ["Something iced?"]


def test_invalid_parse_output_falls_back_to_rules(client, use_provider):
    use_provider(FakeProvider(parse={"intent": "launch_rockets", "filters": {"max_price": -5}}))
    resp = chat(client, "Recommend a coffee under ₹250")
    assert resp["source"] == "rules"
    assert resp["recommendations"]


def test_llm_failure_falls_back_to_rules(client, use_provider):
    use_provider(FakeProvider(parse=LLMError("timeout")))
    resp = chat(client, "Recommend a coffee under ₹250")
    assert resp["source"] == "rules"
    assert "Up to ₹250" in resp["filter_summary"]


def test_compose_with_invented_price_is_rejected(client, use_provider):
    use_provider(
        FakeProvider(
            parse=COFFEE_250,
            compose={"message": "The cappuccino is only ₹99 today!", "item_notes": [], "follow_ups": []},
        )
    )
    resp = chat(client, "coffee under 250")
    assert "₹99" not in resp["message"]
    assert resp["message"].startswith("Here are")  # deterministic reply


def test_compose_cannot_attach_notes_to_unknown_items(client, use_provider):
    use_provider(
        FakeProvider(
            parse=COFFEE_250,
            compose={
                "message": "Try these!",
                "item_notes": [{"item_id": "00000000-0000-0000-0000-000000000000", "note": "Secret menu item"}],
                "follow_ups": [],
            },
        )
    )
    resp = chat(client, "coffee under 250")
    assert resp["message"] == "Try these!"
    assert all(r["note"] is None for r in resp["recommendations"])


def test_compose_failure_keeps_deterministic_reply(client, use_provider):
    use_provider(FakeProvider(parse=COFFEE_250, compose=LLMError("down")))
    resp = chat(client, "coffee under 250")
    assert resp["source"] == "llm"
    assert resp["message"].startswith("Here are")


def test_llm_hallucinated_dish_names_are_ignored(client, use_provider):
    parse = {**COFFEE_250, "intent": "item_info", "mentioned_items": ["Unicorn Frappuccino"], "info_topic": "general"}
    use_provider(FakeProvider(parse=parse, compose=LLMError("skip")))
    resp = chat(client, "tell me about the unicorn frappuccino")
    assert resp["recommendations"] == []
    assert resp["clarification"] is not None


def test_prohibited_claims_rejected():
    with pytest.raises(LLMError):
        validate_compose_output(
            {"message": "Good news, your order has been placed!", "item_notes": [], "follow_ups": []},
            allowed_item_ids=set(),
            allowed_amounts=set(),
        )
    with pytest.raises(LLMError):
        validate_compose_output(
            {"message": "The brownie is completely nut-free.", "item_notes": [], "follow_ups": []},
            allowed_item_ids=set(),
            allowed_amounts=set(),
        )
