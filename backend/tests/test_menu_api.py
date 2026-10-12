from decimal import Decimal

from sqlalchemy import select

from app.models import MenuItem


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok", "assistant_mode": "rules", "llm": None}


def test_restaurant(client):
    r = client.get("/api/restaurants/fernwood")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Fernwood Coffee Roasters"
    assert body["currency"] == "INR"
    assert body["settings"]["assistant_name"] == "Your Coffee Guide"
    assert "Recommend a coffee under ₹250" in body["settings"]["suggested_prompts"]
    assert body["settings"]["ordering_enabled"] is False


def test_unknown_restaurant_404(client):
    assert client.get("/api/restaurants/nope").status_code == 404
    assert client.get("/api/restaurants/nope/menu").status_code == 404


def test_menu_structure_and_money_format(client):
    r = client.get("/api/restaurants/fernwood/menu")
    assert r.status_code == 200
    menu = r.json()
    assert menu["currency"] == "INR"
    names = [c["name"] for c in menu["categories"]]
    assert names == ["Hot Coffee", "Cold Coffee", "Tea & More", "Desserts & Bakes", "All-Day Food"]
    items = {i["name"]: i for c in menu["categories"] for i in c["items"]}
    cap = items["Classic Cappuccino"]
    # Money is serialised as exact decimal strings, never floats.
    assert cap["price"] == "210.00"
    assert cap["currency"] == "INR"
    assert cap["variant_required"] is True
    assert [(v["name"], v["price"]) for v in cap["variants"]] == [("Regular", "210.00"), ("Large", "250.00")]
    assert any(a["name"] == "Oat milk" and a["price"] == "60.00" for a in cap["addons"])
    assert cap["allergens"] == {"status": "verified", "items": ["milk"]}
    assert cap["dietary_labels"] == ["Vegetarian"]


def test_categories(client):
    r = client.get("/api/restaurants/fernwood/menu/categories")
    assert r.status_code == 200
    cats = r.json()
    assert len(cats) == 5
    assert all(c["item_count"] > 0 for c in cats)


def test_item_detail_and_unavailable_flag(client, db):
    item = db.scalar(select(MenuItem).where(MenuItem.name == "Spanish Latte"))
    r = client.get(f"/api/restaurants/fernwood/menu/items/{item.id}")
    assert r.status_code == 200
    assert r.json()["is_available"] is False


def test_unknown_dietary_and_allergens_are_explicit(client, db):
    mocha = db.scalar(select(MenuItem).where(MenuItem.name == "Mocha"))
    body = client.get(f"/api/restaurants/fernwood/menu/items/{mocha.id}").json()
    assert body["dietary"]["vegan"] == "unknown"
    assert body["allergens"] == {"status": "unknown", "items": []}
    assert body["ingredients"]["status"] == "partial"
    assert "Vegan" not in body["dietary_labels"]


def test_item_with_all_variants_unavailable_is_not_orderable(client, db):
    cap = db.scalar(select(MenuItem).where(MenuItem.name == "Classic Cappuccino"))
    for v in cap.variants:
        v.is_available = False
    db.flush()
    body = client.get(f"/api/restaurants/fernwood/menu/items/{cap.id}").json()
    assert body["is_available"] is False


def test_price_from_uses_cheapest_available_variant(client, db):
    cap = db.scalar(select(MenuItem).where(MenuItem.name == "Classic Cappuccino"))
    regular = next(v for v in cap.variants if v.name == "Regular")
    regular.is_available = False
    db.flush()
    body = client.get(f"/api/restaurants/fernwood/menu/items/{cap.id}").json()
    assert Decimal(body["price_from"]) == Decimal("250.00")


def test_restaurant_branding(client):
    melo = client.get("/api/restaurants/meloghrano").json()["settings"]
    assert melo["brand_color"] == "#8E2433" and melo["assistant_icon"] == "utensils"
    fern = client.get("/api/restaurants/fernwood").json()["settings"]
    assert fern["brand_color"] is None and fern["assistant_icon"] == "coffee"


def test_seed_refreshes_settings_without_touching_menu(db):
    from app.models import Restaurant
    from app.seed.seed import seed

    melo = db.scalar(select(Restaurant).where(Restaurant.slug == "meloghrano"))
    melo.settings.brand_color = "#000000"
    items_before = db.scalar(select(__import__("sqlalchemy").func.count(MenuItem.id)).where(MenuItem.restaurant_id == melo.id))
    db.flush()
    seed(db)
    db.refresh(melo.settings)
    assert melo.settings.brand_color == "#8E2433"
    items_after = db.scalar(select(__import__("sqlalchemy").func.count(MenuItem.id)).where(MenuItem.restaurant_id == melo.id))
    assert items_after == items_before
