from decimal import Decimal

from sqlalchemy import select

from app.models import MenuItem, Restaurant
from app.schemas.assistant import SearchFilters
from app.services import menu_service
from app.services.intent_rules import extract_prices, parse_message
from app.services.search import search


def _items(db, slug="fernwood"):
    restaurant = db.scalar(select(Restaurant).where(Restaurant.slug == slug))
    return menu_service.load_items(db, restaurant)


def test_exact_price_filtering_is_inclusive_and_variant_aware(db):
    items = _items(db)
    f = SearchFilters(item_types=["beverage"], contains_coffee=True, max_price=Decimal("250"))
    outcome = search(items, f, limit=50)
    names = {s.item.name for s in outcome.matches}
    assert "Cold Coffee Frappé" in names  # exactly ₹250.00 is within budget
    assert "Mocha" not in names  # ₹260
    assert "Classic Cappuccino" in names  # Regular ₹210 fits even though Large is ₹250
    for s in outcome.matches:
        assert s.unit_price <= Decimal("250.00")
        assert s.item.contains_coffee is True
    # The exact set of matching coffee records in the seed data:
    assert names == {
        "Espresso", "Americano", "Classic Cappuccino", "Café Latte", "Flat White", "Cortado",
        "South Indian Filter Coffee", "Iced Americano", "Classic Cold Brew", "Iced Latte", "Cold Coffee Frappé",
    }


def test_one_paisa_over_budget_is_excluded(db):
    items = _items(db)
    outcome = search(items, SearchFilters(contains_coffee=True, max_price=Decimal("249.99")), limit=50)
    assert "Cold Coffee Frappé" not in {s.item.name for s in outcome.matches}


def test_unavailable_items_are_excluded(db):
    items = _items(db)
    outcome = search(items, SearchFilters(contains_coffee=True), limit=50)
    names = {s.item.name for s in outcome.matches}
    assert "Spanish Latte" not in names
    assert "Nitro Cold Brew" not in names
    assert {i.name for i in outcome.unavailable_matches} <= {"Spanish Latte", "Nitro Cold Brew", "Tiramisu Jar"}


def test_empty_result_offers_flagged_alternatives(db):
    outcome = search(_items(db), SearchFilters(contains_coffee=True, max_price=Decimal("100")))
    assert outcome.matches == []
    assert outcome.alternatives
    assert all(a.over_budget for a in outcome.alternatives)
    assert outcome.alternatives[0].item.name == "Espresso"


def test_vegan_filter_only_uses_verified_data(db):
    outcome = search(_items(db), SearchFilters(dietary=["vegan"]), limit=50)
    assert outcome.matches
    assert all(s.item.is_vegan is True for s in outcome.matches)
    assert "Mocha" not in {s.item.name for s in outcome.matches}  # vegan status unknown


def test_allergen_exclusion_drops_unverified_items(db):
    f = SearchFilters(item_types=["dessert"], exclude_allergens=["tree nuts"])
    outcome = search(_items(db), f, limit=50)
    names = {s.item.name for s in outcome.matches}
    assert "Almond Croissant" not in names  # verified to contain tree nuts
    assert "Cinnamon Roll" not in names  # allergens unknown -> never presented as nut-free
    assert "Cinnamon Roll" in {i.name for i in outcome.unknown_allergen_items}
    assert all(s.item.allergens_status == "verified" for s in outcome.matches)


def test_party_budget_is_for_the_group(db):
    f = SearchFilters(party_size=2, max_price=Decimal("300"))
    outcome = search(_items(db), f, limit=50)
    for s in outcome.matches:
        assert s.total <= Decimal("300")
        assert s.total == s.unit_price * s.quantity
    assert "Flat White" not in {s.item.name for s in outcome.matches}  # 2 x 230 = 460


def test_price_extraction():
    assert extract_prices("Recommend a coffee under ₹250") == {"max_price": Decimal("250.00")}
    assert extract_prices("anything below rs. 1,200") == {"max_price": Decimal("1200.00")}
    assert extract_prices("between 200 and 300") == {"min_price": Decimal("200.00"), "max_price": Decimal("300.00")}
    assert extract_prices("something for ₹199") == {"max_price": Decimal("199.00")}
    assert extract_prices("any price is fine") == {"max_price": None, "min_price": None}
    assert extract_prices("for two people") == {}


def test_rules_parser_examples(db):
    items = _items(db)
    p = parse_message("Recommend a coffee under ₹250", items)
    assert p.intent == "recommend"
    assert p.filters.contains_coffee is True and p.filters.max_price == Decimal("250.00")

    p = parse_message("Something cold and not too sweet", items)
    assert p.filters.temperature == "cold" and p.filters.max_sweetness == 2

    p = parse_message("What pairs well with a cappuccino?", items)
    assert p.intent == "pairing" and p.mentioned_items == ["Classic Cappuccino"]

    p = parse_message("Find something for two under ₹500", items)
    assert p.filters.party_size == 2 and p.filters.max_price == Decimal("500.00")

    p = parse_message("I want something without coffee", items)
    assert p.filters.contains_coffee is False

    p = parse_message("What is the cheapest drink available?", items)
    assert p.intent == "cheapest" and p.filters.item_types == ["beverage"]

    p = parse_message("Is the hot chocolate vegan?", items)
    assert p.intent == "item_info" and p.mentioned_items == ["Hot Chocolate"]
    assert p.filters.temperature is None  # "hot" belongs to the dish name


def test_search_endpoint_and_tenant_isolation(client):
    r = client.post("/api/restaurants/fernwood/assistant/search", json={"query": "coffee under 250", "limit": 50})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 11
    assert all(Decimal(i["price_from"]) <= 250 for i in body["items"])
    assert "Saffron Leaf Secret Coffee" not in {i["name"] for i in body["items"]}

    r = client.post(
        "/api/restaurants/fernwood/assistant/search",
        json={"filters": {"item_types": ["dessert"], "sort": "price_asc"}, "limit": 3},
    )
    prices = [Decimal(i["price_from"]) for i in r.json()["items"]]
    assert prices == sorted(prices)
