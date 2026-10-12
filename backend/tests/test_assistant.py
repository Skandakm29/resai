from decimal import Decimal

from sqlalchemy import select

from app.models import MenuItem
from tests.conftest import chat


def _names(resp):
    return [r["item"]["name"] for r in resp["recommendations"]]


def test_recommend_coffee_under_250_returns_real_records(client):
    resp = chat(client, "Recommend a coffee under ₹250")
    assert resp["intent"] == "recommend"
    assert resp["source"] == "rules"
    assert resp["recommendations"], resp["message"]
    for rec in resp["recommendations"]:
        item = rec["item"]
        assert item["contains_coffee"] is True
        assert item["is_available"] is True
        assert Decimal(item["price_from"]) <= Decimal("250")
        assert item["currency"] == "INR"
        assert rec["reasons"]
    menu = client.get("/api/restaurants/fernwood/menu").json()
    real = {i["id"]: i for c in menu["categories"] for i in c["items"]}
    for rec in resp["recommendations"]:
        assert rec["item"]["id"] in real
        assert rec["item"]["price"] == real[rec["item"]["id"]]["price"]
    assert "Up to ₹250" in resp["filter_summary"]
    assert resp["follow_ups"]


def test_multi_turn_refinement_preserves_constraints(client):
    first = chat(client, "Recommend a coffee under ₹250")
    conv = first["conversation_id"]

    second = chat(client, "Something cold", conv)
    assert second["conversation_id"] == conv
    assert second["recommendations"]
    for rec in second["recommendations"]:
        assert rec["item"]["temperature"] == "cold"
        assert rec["item"]["contains_coffee"] is True
        assert Decimal(rec["item"]["price_from"]) <= 250
    assert set(second["filter_summary"]) >= {"Coffee", "Cold", "Up to ₹250"}

    # Switching subject keeps the budget but drops coffee/temperature.
    third = chat(client, "Show me desserts instead", conv)
    assert third["recommendations"]
    assert all(r["item"]["item_type"] == "dessert" for r in third["recommendations"])
    assert all(Decimal(r["item"]["price_from"]) <= 250 for r in third["recommendations"])

    # Explicitly dropping the budget.
    fourth = chat(client, "any price is fine", conv)
    assert fourth["applied_filters"]["max_price"] is None
    assert fourth["applied_filters"]["item_types"] == ["dessert"]


def test_compare_previous_results(client):
    first = chat(client, "Something cold and not too sweet")
    resp = chat(client, "Compare these two drinks", first["conversation_id"])
    assert resp["intent"] == "compare"
    assert resp["comparison"] is not None
    assert resp["comparison"]["item_names"] == _names(first)[:2]
    labels = [r["label"] for r in resp["comparison"]["rows"]]
    assert {"Price", "Strength", "Vegan", "Allergens"} <= set(labels)
    # Comparison does not overwrite the active search constraints.
    after = chat(client, "and vegan", first["conversation_id"])
    assert after["applied_filters"]["temperature"] == "cold"


def test_compare_without_context_asks_for_clarification(client):
    resp = chat(client, "Compare these two drinks")
    assert resp["clarification"] is not None
    assert resp["recommendations"] == []


def test_named_comparison(client):
    resp = chat(client, "Compare the flat white vs cortado")
    assert resp["comparison"]["item_names"] == ["Flat White", "Cortado"]
    assert "₹40 cheaper" in resp["message"]


def test_empty_results_are_explained_not_invented(client):
    resp = chat(client, "Recommend a coffee under ₹100")
    assert "couldn't find" in resp["message"]
    assert resp["recommendations"]  # closest alternatives...
    assert all(r["over_budget"] for r in resp["recommendations"])  # ...clearly flagged


def test_unknown_allergen_info_is_not_presented_as_safe(client):
    resp = chat(client, "Does the mocha have nuts?")
    assert resp["intent"] == "item_info"
    assert "hasn't verified allergen information" in resp["message"]
    assert "free" not in resp["message"].lower()


def test_verified_allergen_answer_includes_cross_contact_note(client):
    resp = chat(client, "Does the americano contain milk?")
    assert "not on the Americano's verified allergen list" in resp["message"]
    assert "cross-contact" in resp["message"]


def test_vegan_question_uses_verified_data(client):
    assert "not vegan" in chat(client, "Is the brownie vegan?")["message"]
    assert "hasn't verified whether the Hot Chocolate is vegan" in chat(client, "Is the hot chocolate vegan?")["message"]


def test_unavailable_item_is_never_claimed_available(client):
    resp = chat(client, "Is the Spanish Latte available?")
    assert "currently unavailable" in resp["message"]
    first = resp["recommendations"][0]["item"]
    assert first["name"] == "Spanish Latte" and first["is_available"] is False
    assert all(r["item"]["is_available"] for r in resp["recommendations"][1:])


def test_no_order_placement_claims(client):
    resp = chat(client, "Please place my order and pay")
    assert resp["intent"] == "order_help"
    assert "can't place" in resp["message"]


def test_pairing_uses_cart_context(client, db):
    cap = db.scalar(select(MenuItem).where(MenuItem.name == "Classic Cappuccino"))
    resp = chat(client, "Suggest a dessert with my order", cart=[{"item_id": str(cap.id), "quantity": 1}])
    assert resp["intent"] == "pairing"
    assert resp["recommendations"]
    assert all(r["item"]["item_type"] == "dessert" for r in resp["recommendations"])
    assert "Cappuccino" in resp["message"]


def test_tenant_isolation_in_chat(client):
    saffron = chat(client, "Recommend a coffee", slug="saffron-leaf")
    assert _names(saffron) == ["Saffron Leaf Secret Coffee"]

    # Another restaurant's conversation id is never reused.
    resp = chat(client, "Recommend a coffee", saffron["conversation_id"])
    assert resp["conversation_id"] != saffron["conversation_id"]
    assert "Saffron Leaf Secret Coffee" not in _names(resp)


def test_tenant_isolation_item_endpoint(client, db):
    foreign = db.scalar(select(MenuItem).where(MenuItem.name == "Kashmiri Kahwa"))
    assert client.get(f"/api/restaurants/fernwood/menu/items/{foreign.id}").status_code == 404
    assert client.get(f"/api/restaurants/saffron-leaf/menu/items/{foreign.id}").status_code == 200


def test_off_topic(client):
    resp = chat(client, "What's the weather in Paris tomorrow?")
    assert resp["intent"] == "off_topic"
    assert resp["recommendations"] == []


def test_conversation_is_persisted(client, db):
    from app.models import Conversation

    resp = chat(client, "Recommend a coffee under ₹250")
    conv = db.get(Conversation, __import__("uuid").UUID(resp["conversation_id"]))
    assert conv.message_count == 2
    assert [m.role for m in conv.messages] == ["user", "assistant"]
    assert conv.state["filters"]["max_price"] == "250.00"


def test_blank_message_rejected(client):
    r = client.post("/api/restaurants/fernwood/assistant/chat", json={"message": "   "})
    assert r.status_code == 422


def test_negated_budget_is_a_ceiling(client):
    resp = chat(client, "fancy an iced coffee, nothing over 250 bucks")
    assert "Up to ₹250" in resp["filter_summary"]
    assert all(Decimal(r["item"]["price_from"]) <= 250 for r in resp["recommendations"])


def test_follow_up_question_about_shown_item(client):
    first = chat(client, "Something cold and not too sweet")
    resp = chat(client, "is that vegan", first["conversation_id"])
    assert resp["intent"] == "item_info"
    assert resp["recommendations"][0]["item"]["name"] == first["recommendations"][0]["item"]["name"]
    # The question does not change the active search.
    again = chat(client, "and hot", first["conversation_id"])
    assert again["applied_filters"]["max_sweetness"] == 2
