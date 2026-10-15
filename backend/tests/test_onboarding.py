"""Upload a menu -> review the draft -> publish a live page."""

import io
import json

from app.config import get_settings
from app.ingestion import extract
from app.ingestion.extract import draft_from_llm
from app.ingestion.ocr import fix_prices
from app.llm.base import LLMError
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


def _photo(lines: list[str]) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 120 + 70 * len(lines)), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=44)
    for n, line in enumerate(lines):
        draw.text((40, 40 + 70 * n), line, fill="black", font=font)
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def test_extract_reads_photos_with_ocr(client):
    assert client.get("/api/start/status").json()["reads_photos_and_scans"] is True
    photo = ("files", ("menu.jpg", _photo(["HOT DRINKS", "Masala Chai 90", "Filter Coffee 110"]), "image/jpeg"))
    r = client.post("/api/onboarding/menu/extract", files=[photo], headers=ADMIN)
    assert r.status_code == 200, r.text
    assert [(i["name"], i["price"]) for i in r.json()["items"]] == [("Masala Chai", "90.00"), ("Filter Coffee", "110.00")]


def test_extract_rejects_broken_images_and_bad_types(client):
    broken = ("files", ("menu.jpg", b"\xff\xd8\xff", "image/jpeg"))
    r = client.post("/api/onboarding/menu/extract", files=[broken], headers=ADMIN)
    assert r.status_code == 422 and "couldn't read that image" in r.json()["detail"]
    r = client.post("/api/onboarding/menu/extract", files=[("files", ("m.heic", b"x", "image/heic"))], headers=ADMIN)
    assert r.status_code == 422 and "HEIC" in r.json()["detail"]
    assert client.post("/api/onboarding/menu/extract", data={"text": ""}, headers=ADMIN).status_code == 422


def test_ocr_price_fixes_use_the_text_layer():
    known = {"239", "309", "369", "379"}
    assert fix_prices("BAKEDPESHAWARIALOOIF379", known) == "BAKEDPESHAWARIALOO₹379"
    assert fix_prices("PURANI DELHI KE SOYA   1369", known) == "PURANI DELHI KE SOYA   ₹369"
    assert fix_prices("HALF I FULL   F239|F309", known) == "HALF I FULL   ₹239 ₹309"
    # Without exact numbers to check against, nothing is rewritten.
    assert fix_prices("SOYA 1369", set()) == "SOYA 1369"
    assert fix_prices("Serves 2   125 ml", known) == "Serves 2   125 ml"


class _FakeModels:
    """A provider whose first call per model is rate limited, then answers from the chunk text."""

    def __init__(self):
        self.calls: list[str] = []

    def generate_json(self, *, system, user, schema, max_tokens, model=None):
        import time

        self.calls.append(model)
        time.sleep(0.05)  # a real call takes a while, so both workers get chunks
        if self.calls.count(model) == 1:
            raise LLMError("LLM rate limited")
        items = []
        for line in user.splitlines():
            parts = line.rsplit(" ", 1)
            if len(parts) == 2 and parts[1].isdigit():
                items.append({"category": "Menu", "name": parts[0], "price": parts[1]})
        return {"profile": {"name": None}, "items": items}


def test_structuring_spreads_chunks_across_models(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "menu_text_models", "model-a,model-b")
    monkeypatch.setattr(settings, "menu_text_chunk_chars", 1000)
    monkeypatch.setattr(extract, "time", _FastTime())
    pages = [(f"page {n}", "\n".join(f"Dish {n}-{i} {100 + i}" for i in range(60))) for n in range(1, 4)]
    fake = _FakeModels()
    draft = extract._structure_text(iter(pages), fake, settings)
    assert len(draft.items) == 180 and draft.method == "text-llm" and not draft.warnings
    assert {"model-a", "model-b"} <= set(fake.calls)


class _FastTime:
    """time module stand-in: sleeping is instant (rate-limit waits in tests)."""

    def __init__(self):
        import time as _t

        self._t = _t

    def monotonic(self):
        return self._t.monotonic()

    def sleep(self, _seconds):
        return None


def test_misread_rupee_prices_are_fixed_or_flagged():
    prices = ["369", "379", "1379", "349", "5200"]
    items = [{"category": "Mains", "name": f"Dish {i}", "price": p} for i, p in enumerate(prices)]
    draft = draft_from_llm({"profile": {}, "items": items}, "text-llm")
    assert [str(i.price) for i in draft.items] == ["369.00", "379.00", "379.00", "349.00", "5200.00"]
    assert any("Dish 2 ₹1379 → ₹379" in w for w in draft.warnings)
    assert any("Dish 4 ₹5200" in w for w in draft.warnings)


def test_ocr_section_names_are_merged():
    cats = ["Clay Pot & Tandoor", "-Claypot&Tandoor", "clay pot & tandoor", "Page 24", "DESSERTS", "desserts"]
    items = [{"category": c, "name": f"Dish {i}", "price": "300"} for i, c in enumerate(cats)]
    draft = draft_from_llm({"profile": {}, "items": items}, "text-llm")
    assert [i.category for i in draft.items] == ["Clay Pot & Tandoor"] * 4 + ["Desserts"] * 2


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


# --- Self-serve (public landing page) ---------------------------------------

OWNER = {"name": "Asha", "email": "Asha@BeanThere.in"}


def _self_publish(client, items, slug="bean-there", **owner):
    profile = {"name": "Bean There", "slug": slug, "city": "Bengaluru"}
    return client.post("/api/start/publish", json={"profile": profile, "items": items, "owner": {**OWNER, **owner}})


def test_self_serve_extract_and_publish_without_admin_key(client):
    draft = client.post("/api/start/extract", data={"text": MENU_TEXT}).json()
    r = _self_publish(client, draft["items"])
    assert r.status_code == 201, r.text
    assert r.json()["path"] == "/r/bean-there"
    assert client.get("/api/restaurants/bean-there/menu").status_code == 200

    # Owner contact is stored for the admin list, never on the public profile.
    assert "owner_email" not in client.get("/api/restaurants/bean-there").json()
    listed = client.get("/api/onboarding/restaurants", headers=ADMIN).json()
    assert (listed[0]["owner_name"], listed[0]["owner_email"]) == ("Asha", "asha@beanthere.in")


def test_self_serve_never_overwrites_and_picks_a_free_link(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "public_publish_per_hour", 10)
    items = [{"category": "Coffee", "name": "Latte", "price": "200"}]
    assert _self_publish(client, items).json()["path"] == "/r/bean-there"
    assert _self_publish(client, items).json()["path"] == "/r/bean-there-2"
    assert _self_publish(client, items, slug="fernwood").json()["path"] == "/r/fernwood-2"
    assert _self_publish(client, items, slug="admin").json()["path"] == "/r/admin-2"
    assert [i["name"] for c in client.get("/api/restaurants/fernwood/menu").json()["categories"] for i in c["items"]] != ["Latte"]


def test_self_serve_validation_and_limits(client, monkeypatch):
    items = [{"category": "Coffee", "name": "Latte", "price": "200"}]
    assert _self_publish(client, items, email="not-an-email").status_code == 422
    monkeypatch.setattr(get_settings(), "public_max_items", 1)
    assert _self_publish(client, items * 2).status_code == 422

    monkeypatch.setattr(get_settings(), "public_extract_per_hour", 2)
    for _ in range(2):
        assert client.post("/api/start/extract", data={"text": MENU_TEXT}).status_code == 200
    r = client.post("/api/start/extract", data={"text": MENU_TEXT})
    assert r.status_code == 429 and "hourly limit" in r.json()["detail"]

    monkeypatch.setattr(get_settings(), "public_onboarding_enabled", False)
    assert client.get("/api/start/status").status_code == 404


def test_restaurant_name_drops_a_trailing_location():
    def name(raw, address=None, city=None):
        profile = {"name": raw, "tagline": None, "address_line": address, "city": city, "phone": None}
        return draft_from_llm({"profile": profile, "items": []}, "vision").profile.name

    assert name("THE BREW ROOM - Koramangala, Bengaluru", "Koramangala, Bengaluru", "Bengaluru") == "The Brew Room"
    assert name("Brew Room, Bengaluru", None, "Bengaluru") == "Brew Room"
    assert name("Toit - Brewpub", "Indiranagar", "Bengaluru") == "Toit - Brewpub"
    assert name("Café Noir", None, None) == "Café Noir"


def test_respace_restores_word_breaks_from_the_text_layer():
    from app.ingestion.extract import respace
    from app.ingestion.text_parser import DraftItem, DraftMenu, DraftProfile

    draft = DraftMenu(
        items=[DraftItem(category="Tea&Notcoffee", name="SouthIndianFilter Coffee", price="110")],
        profile=DraftProfile(name="Hearth&Beancafe"),
    )
    respace(draft, "HEARTH & BEAN CAFÉ\nTEA & NOT COFFEE\nSouth Indian Filter Coffee ₹110")
    assert (draft.items[0].category, draft.items[0].name) == ("Tea & Not Coffee", "South Indian Filter Coffee")
    assert draft.profile.name == "Hearth & Bean Café"


def test_two_column_pages_are_read_column_by_column():
    from app.ingestion.ocr import _lines

    def box(x0, x1, y, text):
        return [[[x0, y - 10], [x1, y - 10], [x1, y + 10], [x0, y + 10]], text, 0.9]

    rows = [("Espresso", "130", "Peri Peri Fries", "180"), ("Americano", "160", "Tomato Soup", "190"),
            ("Flat White", "210", "Pesto Pasta", "360"), ("Cold Brew", "220", "Tiramisu", "280"),
            ("Mocha", "240", "Brownie", "170")]
    result = []
    for n, (a, pa, b, pb) in enumerate(rows):
        y = 100 + 40 * n
        result += [box(40, 200, y, a), box(330, 370, y, pa), box(460, 640, y, b), box(760, 800, y, pb)]
    lines = _lines(result, 840)
    assert lines[:2] == ["Espresso   130", "Americano   160"]
    assert lines[5:7] == ["Peri Peri Fries   180", "Tomato Soup   190"]


def test_extract_accepts_pages_ocrd_in_the_browser(client):
    pages = [
        {"label": "menu.pdf page 1", "text": "HOT COFFEE\nCappuccino   %210\nSouthIndianFilter Coffee   1110",
         "layer": "HOT COFFEE Cappuccino ₹210 South Indian Filter Coffee ₹110"},
    ]
    r = client.post("/api/start/extract", data={"pages": json.dumps(pages)})
    assert r.status_code == 200, r.text
    assert [(i["name"], i["price"]) for i in r.json()["items"]] == [
        ("Cappuccino", "210.00"), ("South Indian Filter Coffee", "110.00"),
    ]
    assert client.post("/api/start/extract", data={"pages": "not json"}).status_code == 422
    assert client.post("/api/start/extract", data={"pages": "[]"}).status_code == 422


def test_without_server_ocr_pdfs_use_their_text_layer_and_photos_ask_for_a_retry(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "server_ocr_enabled", False)
    pdf = _pdf(["HOT COFFEE", "Cappuccino 210"])
    r = client.post("/api/start/extract", files=[("files", ("menu.pdf", pdf, "application/pdf"))])
    assert [i["name"] for i in r.json()["items"]] == ["Cappuccino"]
    photo = ("files", ("menu.jpg", _photo(["Masala Chai 90"]), "image/jpeg"))
    r = client.post("/api/start/extract", files=[photo])
    assert r.status_code == 422 and "browser" in r.json()["detail"]


def test_condense_keeps_menu_lines_and_drops_the_rest():
    from app.ingestion.extract import condense

    page = "\n".join([
        "HEARTH & BEAN CAFE", "14, 12th Main, Indiranagar · +91 98450 12345",
        "HOT COFFEE", "Espresso   130", "Single origin Chikmagalur, pulled short",
        "Americano   Reg 160 / Large 190", "A warm bowl of soup that evokes timeless tales.",
        "All prices exclusive of 5% GST", "@hearthandbean", "Committed to Quality.",
    ])
    assert condense(page, keep_header=True).splitlines() == [
        "HEARTH & BEAN CAFE", "14, 12th Main, Indiranagar · +91 98450 12345",
        "HOT COFFEE", "Espresso   130", "Americano   Reg 160 / Large 190",
    ]
    # A page without prices (an "about us" page) is skipped; years aren't prices.
    assert condense("Our Story\nRoasting since 2019, in Bengaluru.\nEst. 2019") == ""


def test_compact_model_output_is_filled_in_by_rules():
    draft = draft_from_llm({"profile": {}, "items": [
        {"section": "Cold Coffee", "name": "Iced Latte", "price": "220", "sizes": [], "veg": True, "type": "beverage"},
        {"section": "Mains", "name": "Pesto Pasta", "price": "360", "sizes": [
            {"name": "Half", "price": "260"}, {"name": "Full", "price": "360"}], "veg": None, "type": "food"},
    ]}, "text-llm")
    latte, pasta = draft.items
    assert (latte.temperature, latte.contains_coffee, latte.is_vegetarian) == ("cold", True, True)
    assert "coffee" in latte.tags and {"pasta", "main"} <= set(pasta.tags)
    assert [v.name for v in pasta.variants] == ["Half", "Full"]
