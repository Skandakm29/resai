"""Upload a menu -> review the draft -> publish a live page."""

from app.config import get_settings
from app.ingestion.extract import draft_from_llm
from tests.conftest import chat

ADMIN = {"X-Admin-Key": "test-admin-key"}

MENU_TEXT = """HOT COFFEE
Cappuccino ............ 210
Cafe Latte ₹230 - velvety microfoam
COLD COFFEE
Iced Americano 190
Cold Brew 240
DESSERTS
Chocolate Brownie: Rs. 180
"""


def _pdf(lines: list[str]) -> bytes:
    """A minimal one-page PDF with a text layer."""
    body = "BT /F1 12 Tf 14 TL 50 750 Td " + " ".join(f"({ln}) Tj T*" for ln in lines) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(body)} >>\nstream\n{body}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = "%PDF-1.4\n", []
    for n, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{obj}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
    return out.encode("latin-1")


def _publish(client, items, name="Bean There", slug="bean-there", **extra):
    profile = {"name": name, "slug": slug, "address_line": "Koramangala, Bengaluru", "city": "Bengaluru",
               "brand_color": "#2f6b3a"}
    body = {"profile": profile, "items": items}
    return client.post("/api/onboarding/restaurants", json={**body, **extra}, headers=ADMIN)


def test_onboarding_endpoints_require_admin_key(client):
    assert client.post("/api/onboarding/menu/extract", data={"text": "Latte 200"}).status_code == 401
    assert client.get("/api/onboarding/restaurants").status_code == 401
    assert client.post("/api/onboarding/restaurants", json={}).status_code == 401


def test_extract_from_pasted_text(client):
    r = client.post("/api/onboarding/menu/extract", data={"text": MENU_TEXT}, headers=ADMIN)
    assert r.status_code == 200, r.text
    draft = r.json()
    assert draft["method"] == "text-rules"
    by_name = {i["name"]: i for i in draft["items"]}
    assert by_name["Iced Americano"]["item_type"] == "beverage"
    assert by_name["Iced Americano"]["temperature"] == "cold"
    assert by_name["Cappuccino"]["temperature"] == "hot"
    assert by_name["Chocolate Brownie"]["item_type"] == "dessert"


def test_extract_from_pdf_text_layer(client):
    pdf = _pdf(["HOT COFFEE", "Cappuccino 210", "Flat White 230"])
    r = client.post(
        "/api/onboarding/menu/extract", files=[("files", ("menu.pdf", pdf, "application/pdf"))], headers=ADMIN
    )
    assert r.status_code == 200, r.text
    assert [(i["name"], i["price"]) for i in r.json()["items"]] == [("Cappuccino", "210.00"), ("Flat White", "230.00")]


def test_extract_rejects_photos_without_vision_and_bad_types(client):
    assert not get_settings().menu_vision_enabled
    photo = ("files", ("menu.jpg", b"\xff\xd8\xff", "image/jpeg"))
    r = client.post("/api/onboarding/menu/extract", files=[photo], headers=ADMIN)
    assert r.status_code == 422 and "ANTHROPIC_API_KEY" in r.json()["detail"]
    r = client.post("/api/onboarding/menu/extract", files=[("files", ("m.heic", b"x", "image/heic"))], headers=ADMIN)
    assert r.status_code == 422 and "HEIC" in r.json()["detail"]
    assert client.post("/api/onboarding/menu/extract", data={"text": ""}, headers=ADMIN).status_code == 422


def test_llm_output_is_validated():
    draft = draft_from_llm(
        {
            "profile": {"name": "BEAN THERE", "tagline": None, "address_line": None, "city": "Bengaluru", "phone": None},
            "items": [
                {"category": "Coffee", "name": "Latte", "price": "₹1,200", "description": None, "item_type": "beverage",
                 "temperature": "hot", "contains_coffee": True, "is_vegetarian": True, "tags": ["Coffee"],
                 "variants": [{"name": "Regular", "price": "200"}, {"name": "Large", "price": "abc"}]},
                {"category": "Food", "name": "", "price": "100"},
                {"category": "Food", "name": "Mystery", "price": "market price", "item_type": "soup"},
                {"category": "ALL  DAY BITES", "name": "Toast", "price": "90", "item_type": "soup", "temperature": "warm"},
            ],
        },
        "vision",
    )
    assert [(i.name, str(i.price)) for i in draft.items] == [("Latte", "1200.00"), ("Toast", "90.00")]
    assert [v.name for v in draft.items[0].variants] == ["Regular"]
    assert draft.items[0].tags == ["coffee"]
    assert draft.items[1].item_type == "food" and draft.items[1].temperature is None
    assert draft.items[1].category == "All Day Bites"
    assert draft.profile.name == "Bean There" and draft.profile.city == "Bengaluru"
    assert len(draft.warnings) == 2


def test_publish_creates_a_working_cafe(client):
    draft = client.post("/api/onboarding/menu/extract", data={"text": MENU_TEXT}, headers=ADMIN).json()
    r = _publish(client, draft["items"])
    assert r.status_code == 201, r.text
    assert r.json()["path"] == "/r/bean-there"
    assert r.json()["item_count"] == 5 and r.json()["category_count"] == 3

    profile = client.get("/api/restaurants/bean-there").json()
    assert profile["name"] == "Bean There"
    assert (profile["address_line"], profile["city"]) == ("Koramangala", "Bengaluru")
    menu = client.get("/api/restaurants/bean-there/menu").json()
    names = [i["name"] for c in menu["categories"] for i in c["items"]]
    assert "Cold Brew" in names

    reply = chat(client, "Recommend a coffee under ₹200", slug="bean-there")
    shown = [r["item"]["name"] for r in reply["recommendations"]]
    assert shown and set(shown) <= {"Iced Americano", "Cappuccino"}

    listed = client.get("/api/onboarding/restaurants", headers=ADMIN).json()
    assert [c["slug"] for c in listed] == ["bean-there"]


def test_publish_variants_duplicates_and_dietary(client):
    items = [
        {"category": "Coffee", "name": "Latte", "price": "200", "item_type": "beverage",
         "variants": [{"name": "Regular", "price": "200"}, {"name": "Large", "price": "250"}]},
        {"category": "Iced", "name": "Latte", "price": "240", "item_type": "beverage", "temperature": "cold"},
        {"category": "Food", "name": "Egg Sandwich", "price": "220", "is_vegetarian": False},
    ]
    assert _publish(client, items).status_code == 201
    menu = client.get("/api/restaurants/bean-there/menu").json()
    items_out = {i["name"]: i for c in menu["categories"] for i in c["items"]}
    assert set(items_out) == {"Latte", "Latte (Iced)", "Egg Sandwich"}
    assert [v["name"] for v in items_out["Latte"]["variants"]] == ["Regular", "Large"]
    assert items_out["Egg Sandwich"]["dietary"] == {"vegetarian": "no", "vegan": "no"}
    assert items_out["Latte"]["allergens"]["status"] == "unknown"


def test_publish_slug_conflicts_and_replace(client):
    items = [{"category": "Coffee", "name": "Latte", "price": "200"}]
    assert _publish(client, items).status_code == 201
    assert _publish(client, items).status_code == 409
    r = _publish(client, [{"category": "Tea", "name": "Masala Chai", "price": "90"}], replace=True)
    assert r.status_code == 201
    menu = client.get("/api/restaurants/bean-there/menu").json()
    assert [i["name"] for c in menu["categories"] for i in c["items"]] == ["Masala Chai"]

    # Built-in demos and reserved paths are protected.
    assert _publish(client, items, slug="fernwood", replace=True).status_code == 409
    assert _publish(client, items, slug="admin").status_code == 409
    assert _publish(client, items, slug="Not A Slug").status_code == 422


def test_delete_uploaded_cafe(client):
    assert _publish(client, [{"category": "Coffee", "name": "Latte", "price": "200"}]).status_code == 201
    assert client.delete("/api/onboarding/restaurants/fernwood", headers=ADMIN).status_code == 404
    assert client.delete("/api/onboarding/restaurants/bean-there", headers=ADMIN).status_code == 204
    assert client.get("/api/restaurants/bean-there").status_code == 404
