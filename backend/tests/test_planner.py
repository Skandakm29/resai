from decimal import Decimal

from sqlalchemy import select

from app.models import Restaurant
from app.schemas.assistant import SearchFilters
from app.services import menu_service
from app.services.intent_rules import parse_message
from app.services.planner import build_plan
from app.services.search import courses_of
from tests.conftest import chat


def _items(db, slug="meloghrano"):
    return menu_service.load_items(db, db.scalar(select(Restaurant).where(Restaurant.slug == slug)))


def test_group_plan_fits_budget_with_real_items_and_exact_totals(db):
    items = _items(db)
    plan = build_plan(items, SearchFilters(party_size=4, max_price=Decimal("2000")), ["starter", "main"])
    assert plan.within_budget
    mains = [p for p in plan.picks if p.course == "main"]
    starters = [p for p in plan.picks if p.course == "starter"]
    assert sum(p.quantity for p in mains) == 4 and sum(p.quantity for p in starters) == 2
    assert len({p.item.id for p in mains}) == 4  # four different mains
    assert all("main" in courses_of(p.item) for p in mains)
    assert all("starter" in courses_of(p.item) for p in starters)
    assert plan.total == sum(p.unit_price * p.quantity for p in plan.picks) <= Decimal("2000")
    assert plan.per_person == plan.total / 4
    assert plan.remaining == Decimal("2000") - plan.total
    for p in plan.picks:
        assert p.unit_price == menu_service.price_from(p.item)
        if p.item.variants:
            assert p.variant is not None and p.variant.price == p.unit_price


def test_impossible_budget_returns_cheapest_plan_flagged(db):
    plan = build_plan(_items(db), SearchFilters(party_size=4, max_price=Decimal("500")), ["starter", "main"])
    assert not plan.within_budget
    assert plan.total > Decimal("500")


def test_plan_respects_verified_dietary_filters(db):
    plan = build_plan(_items(db, "fernwood"), SearchFilters(party_size=2, dietary=["vegan"]), ["main", "drink"])
    assert plan.picks and all(p.item.is_vegan for p in plan.picks)


def test_parse_group_request(db):
    p = parse_message("We are group of 4 people i wanna try starters and main course and my budget is 2000", _items(db))
    assert p.intent == "meal_plan"
    assert p.filters.party_size == 4 and p.filters.max_price == Decimal("2000.00")
    assert p.filters.courses == ["starter", "main"]
    assert p.filters.keywords == []


def test_course_filter_in_normal_search(client):
    resp = chat(client, "show me starters", slug="meloghrano")
    assert resp["recommendations"]
    assert "Starters" in resp["filter_summary"]


def test_plan_conversation(client):
    first = chat(client, "We are group of 4 people i wanna try starters and main course and my budget is 2000", slug="meloghrano")
    assert first["intent"] == "meal_plan"
    plan = first["plan"]
    assert plan["party_size"] == 4 and plan["within_budget"]
    assert Decimal(plan["total"]) <= 2000
    assert sum(Decimal(l["line_total"]) for l in plan["lines"]) == Decimal(plan["total"])
    conv = first["conversation_id"]

    more = chat(client, "make it 2800", conv, slug="meloghrano")
    assert more["plan"]["budget"] == "2800.00"
    pasta = chat(client, "only pasta mains", conv, slug="meloghrano")
    mains = [l for l in pasta["plan"]["lines"] if l["course"] == "main"]
    assert mains and all("Pasta" in l["item"]["name"] for l in mains)
    assert any(l["course"] == "starter" for l in pasta["plan"]["lines"])  # starters kept
    dessert = chat(client, "add desserts", conv, slug="meloghrano")
    assert {l["course"] for l in dessert["plan"]["lines"]} == {"starter", "main", "dessert"}
    no_starters = chat(client, "no starters", conv, slug="meloghrano")
    assert "starter" not in {l["course"] for l in no_starters["plan"]["lines"]}
