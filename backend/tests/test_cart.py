from sqlalchemy import select

from app.models import MenuAddon, MenuItem


def _item(db, name):
    return db.scalar(select(MenuItem).where(MenuItem.name == name))


def _addon(db, name, restaurant_id):
    return db.scalar(select(MenuAddon).where(MenuAddon.name == name, MenuAddon.restaurant_id == restaurant_id))


def _validate(client, lines, slug="fernwood"):
    r = client.post("/api/cart/validate", json={"restaurant_slug": slug, "lines": lines})
    assert r.status_code == 200, r.text
    return r.json()


def test_cart_totals_are_exact_decimals(client, db):
    cap = _item(db, "Classic Cappuccino")
    large = next(v for v in cap.variants if v.name == "Large")
    oat = _addon(db, "Oat milk", cap.restaurant_id)
    brownie = _item(db, "Dark Chocolate Brownie")
    body = _validate(
        client,
        [
            {"item_id": str(cap.id), "variant_id": str(large.id), "addon_ids": [str(oat.id)], "quantity": 2, "unit_price": "310.00"},
            {"item_id": str(brownie.id), "quantity": 3},
        ],
    )
    assert body["valid"] is True
    assert body["currency"] == "INR"
    assert [l["line_total"] for l in body["lines"]] == ["620.00", "540.00"]
    assert body["subtotal"] == "1160.00"
    assert body["item_count"] == 5
    assert "isn't connected" in body["message"]  # no false order-placement claims


def test_client_price_is_never_trusted(client, db):
    brownie = _item(db, "Dark Chocolate Brownie")
    body = _validate(client, [{"item_id": str(brownie.id), "quantity": 1, "unit_price": "1.00"}])
    line = body["lines"][0]
    assert line["status"] == "price_changed"
    assert line["unit_price"] == "180.00"
    assert body["subtotal"] == "180.00"
    assert body["valid"] is False


def test_required_variant_missing(client, db):
    cap = _item(db, "Classic Cappuccino")
    body = _validate(client, [{"item_id": str(cap.id), "quantity": 1}])
    assert body["lines"][0]["status"] == "invalid"
    assert body["subtotal"] == "0.00"


def test_variant_from_other_item_rejected(client, db):
    cap = _item(db, "Classic Cappuccino")
    latte = _item(db, "Café Latte")
    body = _validate(client, [{"item_id": str(cap.id), "variant_id": str(latte.variants[0].id), "quantity": 1}])
    assert body["lines"][0]["status"] == "invalid"


def test_unavailable_item_and_addon(client, db):
    spanish = _item(db, "Spanish Latte")
    cap = _item(db, "Classic Cappuccino")
    sugar_free = _addon(db, "Sugar-free syrup", cap.restaurant_id)
    body = _validate(
        client,
        [
            {"item_id": str(spanish.id), "quantity": 1},
            {"item_id": str(cap.id), "variant_id": str(cap.variants[0].id), "addon_ids": [str(sugar_free.id)], "quantity": 1},
        ],
    )
    assert [l["status"] for l in body["lines"]] == ["unavailable", "unavailable"]
    assert body["valid"] is False


def test_addon_not_allowed_for_item(client, db):
    brownie = _item(db, "Dark Chocolate Brownie")
    oat = _addon(db, "Oat milk", brownie.restaurant_id)
    body = _validate(client, [{"item_id": str(brownie.id), "addon_ids": [str(oat.id)], "quantity": 1}])
    assert body["lines"][0]["status"] == "invalid"


def test_other_restaurants_items_are_rejected(client, db):
    kahwa = _item(db, "Kashmiri Kahwa")
    body = _validate(client, [{"item_id": str(kahwa.id), "quantity": 1}])
    assert body["lines"][0]["status"] == "invalid"
    assert body["lines"][0]["name"] is None


def test_quantity_bounds(client, db):
    brownie = _item(db, "Dark Chocolate Brownie")
    r = client.post(
        "/api/cart/validate",
        json={"restaurant_slug": "fernwood", "lines": [{"item_id": str(brownie.id), "quantity": 0}]},
    )
    assert r.status_code == 422


def test_empty_cart(client):
    body = _validate(client, [])
    assert body["valid"] is False and body["subtotal"] == "0.00"
