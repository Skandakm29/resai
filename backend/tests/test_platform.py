from app.config import get_settings
from app.ingestion.text_parser import parse_menu_text


def test_rate_limit_on_chat(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_chat_per_minute", 2)
    url = "/api/restaurants/fernwood/assistant/chat"
    assert client.post(url, json={"message": "hi"}).status_code == 200
    assert client.post(url, json={"message": "hi"}).status_code == 200
    r = client.post(url, json={"message": "hi"})
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1


def test_onboarding_requires_admin_key(client):
    url = "/api/onboarding/menu/parse-text"
    assert client.post(url, json={"text": "Latte 200"}).status_code == 401
    r = client.post(url, json={"text": "HOT COFFEE\nLatte ...... 220\n"}, headers={"X-Admin-Key": "test-admin-key"})
    assert r.status_code == 200
    assert r.json()["items"][0]["name"] == "Latte"


def test_menu_text_parser():
    draft = parse_menu_text(
        "HOT COFFEE\nCappuccino ............ 210\nFlat White  ₹230 - velvety microfoam\n\nDESSERTS\nBrownie: Rs. 180\n???\n"
    )
    rows = [(i.category, i.name, str(i.price), i.description) for i in draft.items]
    assert rows == [
        ("Hot Coffee", "Cappuccino", "210.00", None),
        ("Hot Coffee", "Flat White", "230.00", "velvety microfoam"),
        ("Desserts", "Brownie", "180.00", None),
    ]
    assert all(i.allergens_status == "unknown" for i in draft.items)


def test_openapi_docs_available(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for p in [
        "/api/health",
        "/api/restaurants/{slug}",
        "/api/restaurants/{slug}/menu",
        "/api/restaurants/{slug}/menu/categories",
        "/api/restaurants/{slug}/menu/items/{item_id}",
        "/api/restaurants/{slug}/assistant/chat",
        "/api/restaurants/{slug}/assistant/search",
        "/api/cart/validate",
    ]:
        assert p in paths
