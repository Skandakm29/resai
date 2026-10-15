"""Menu ingestion - publish a reviewed draft as a live restaurant page.

The draft becomes a seed-style spec and goes through the same code path as
the demo restaurants, so an uploaded café gets the same menu, search,
assistant and cart behaviour at ``/r/<slug>``. Dietary flags are kept only
where the menu marked them; allergens and ingredients stay "unknown".
"""

from __future__ import annotations

import statistics
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.ingestion.text_parser import DraftItem
from app.models import MenuItem, MenuVersion, Restaurant
from app.money import format_inr
from app.seed.seed import seed_restaurant, slugify

SLUG_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
RESERVED_SLUGS = {"admin", "api", "new", "r", "start"}
EMAIL_RE = r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$"


class CafeProfile(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str | None = Field(default=None, max_length=60, pattern=SLUG_RE)
    tagline: str | None = Field(default=None, max_length=240)
    address_line: str | None = Field(default=None, max_length=240)
    city: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    assistant_icon: Literal["coffee", "utensils", "pizza", "drink", "dessert", "tea"] = "coffee"


class Owner(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=254, pattern=EMAIL_RE)


class PublishRequest(BaseModel):
    profile: CafeProfile
    items: list[DraftItem] = Field(min_length=1, max_length=1000)
    # Re-publishing over an existing uploaded café replaces its menu (same URL).
    replace: bool = False


class SelfServePublishRequest(BaseModel):
    """What a restaurant owner sends from the public page (no replacing)."""

    profile: CafeProfile
    items: list[DraftItem] = Field(min_length=1, max_length=1000)
    owner: Owner


class PublishedCafe(BaseModel):
    slug: str
    name: str
    path: str
    item_count: int
    category_count: int
    city: str | None = None
    published_at: str | None = None
    owner_name: str | None = None
    owner_email: str | None = None


class SlugTaken(Exception):
    pass


def _unique(base: str, used: set[str]) -> str:
    slug, n = base, 2
    while slug in used:
        slug, n = f"{base}-{n}", n + 1
    used.add(slug)
    return slug


def _round_budget(value: Decimal) -> int:
    step = 50 if value < 500 else 100
    return int((value // step + 1) * step)


def suggested_prompts(items: list[DraftItem]) -> list[str]:
    prompts: list[str] = []
    drinks = [i for i in items if i.item_type == "beverage"]
    food = [i for i in items if i.item_type == "food"]
    if drinks:
        median = Decimal(statistics.median([i.price for i in drinks]))
        noun = "coffee" if any(i.contains_coffee for i in drinks) else "drink"
        prompts.append(f"Recommend a {noun} under {format_inr(Decimal(_round_budget(median)))}")
        if any(i.temperature == "cold" for i in drinks):
            prompts.append("Something cold and not too sweet")
    if food:
        prompts.append("4 of us, starters and mains, budget 2000")
    if any(i.is_vegetarian for i in items) and not all(i.is_vegetarian for i in items):
        prompts.append("Show me vegetarian options")
    if any(i.item_type == "dessert" for i in items):
        prompts.append("Something sweet to finish")
    prompts.append("Find something for two under ₹500")
    return prompts[:5]


def _address(address: str | None, city: str | None) -> str | None:
    """Drop a trailing city the page already shows ("Koramangala, Bengaluru" + "Bengaluru")."""
    if address and city and address.lower().rstrip(" ,").endswith(city.lower()):
        address = address.rstrip(" ,")[: -len(city)].rstrip(" ,")
    return address or None


def build_spec(profile: CafeProfile, slug: str, items: list[DraftItem]) -> dict:
    categories: dict[str, dict] = {}
    cat_slugs: set[str] = set()
    item_slugs: set[str] = set()
    for draft in items:
        key = draft.category.strip().lower()
        if key not in categories:
            categories[key] = dict(
                name=draft.category.strip(), slug=_unique(slugify(draft.category) or "menu", cat_slugs),
                description=None, items=[],
            )
        # Item slugs are unique per menu and the seeder derives them from the
        # name, so a repeated name gets its section appended.
        name, n = draft.name.strip(), 1
        while slugify(name) in item_slugs:
            n += 1
            suffix = draft.category.strip() if n == 2 else f"{draft.category.strip()} {n - 1}"
            name = f"{draft.name.strip()} ({suffix})"
        item_slugs.add(slugify(name))
        variants, seen = [], set()
        for v in draft.variants:
            if v.name.strip().lower() not in seen:
                seen.add(v.name.strip().lower())
                variants.append(dict(name=v.name.strip(), price=v.price, is_default=not variants, is_available=True))
        veg = draft.is_vegetarian
        categories[key]["items"].append(
            dict(
                name=name, price=variants[0]["price"] if variants else draft.price,
                description=draft.description, item_type=draft.item_type,
                temperature=draft.temperature if draft.item_type == "beverage" else None,
                contains_coffee=draft.contains_coffee, caffeine_level=None, strength=None, sweetness=None,
                is_vegetarian=veg, is_vegan=False if veg is False else None,
                ingredients=None, ingredients_status="unknown", allergens=None, allergens_status="unknown",
                tags=list(dict.fromkeys(t.strip().lower() for t in draft.tags if t.strip())),
                flavor_tags=[], pairs_with=[], search_keywords=[],
                variants=variants, variant_required=len(variants) > 1, addons=[],
                is_featured=False, is_available=True, serves=1, image_url=None,
            )
        )
    return {
        "restaurant": dict(
            slug=slug, name=profile.name.strip(), tagline=profile.tagline,
            address_line=_address(profile.address_line, profile.city),
            city=profile.city, phone=profile.phone, currency="INR",
        ),
        "settings": dict(
            assistant_name="Your Menu Guide",
            welcome_message=(
                f"Hi! Welcome to {profile.name.strip()}. Tell me what you're in the mood for, or your budget, "
                "and I'll find something on the menu."
            ),
            suggested_prompts=suggested_prompts(items),
            ai_enabled=True, pickup_enabled=True, ordering_enabled=False,
            allergen_disclaimer=(
                "Ingredient and allergen details haven't been confirmed by the café yet. "
                "If you have an allergy, please check with the staff before ordering."
            ),
            brand_color=profile.brand_color, assistant_icon=profile.assistant_icon,
        ),
        "addons": [],
        "categories": list(categories.values()),
    }


def _is_uploaded(db: Session, restaurant: Restaurant) -> bool:
    return db.scalar(
        select(MenuVersion.id).where(MenuVersion.restaurant_id == restaurant.id, MenuVersion.source == "upload")
    ) is not None


def _free_slug(db: Session, base: str) -> str:
    """``base``, or ``base-2``, ``base-3``... - the first that isn't taken or reserved."""
    taken = set(db.scalars(select(Restaurant.slug).where(Restaurant.slug.like(f"{base}%"))).all()) | RESERVED_SLUGS
    slug, n = base, 2
    while slug in taken:
        suffix = f"-{n}"
        slug, n = f"{base[: 60 - len(suffix)].rstrip('-')}{suffix}", n + 1
    return slug


def publish(db: Session, req: PublishRequest, *, owner: Owner | None = None, auto_slug: bool = False) -> PublishedCafe:
    """Publish a draft. ``auto_slug`` picks a free link instead of failing on a taken one."""
    slug = req.profile.slug or slugify(req.profile.name)[:60].strip("-") or "cafe"
    if auto_slug:
        slug = _free_slug(db, slug)
    if slug in RESERVED_SLUGS:
        raise SlugTaken(f"'{slug}' is reserved. Pick another URL name.")
    existing = db.scalar(select(Restaurant).where(Restaurant.slug == slug))
    if existing is not None:
        if not req.replace:
            raise SlugTaken(f"/r/{slug} already exists. Pick another URL name, or replace it.")
        if not _is_uploaded(db, existing):
            raise SlugTaken(f"/r/{slug} is a built-in demo and can't be replaced.")
        db.delete(existing)
        db.flush()
    spec = build_spec(req.profile, slug, req.items)
    restaurant = seed_restaurant(
        db, spec, source="upload", notes=f"Uploaded menu, {len(req.items)} items ({utcnow():%Y-%m-%d})"
    )
    if owner is not None:
        restaurant.owner_name, restaurant.owner_email = owner.name.strip(), owner.email.strip().lower()
    db.commit()
    return PublishedCafe(
        slug=slug, name=restaurant.name, path=f"/r/{slug}", item_count=len(req.items),
        category_count=len(spec["categories"]), city=restaurant.city, published_at=utcnow().isoformat(),
        owner_name=restaurant.owner_name, owner_email=restaurant.owner_email,
    )


def list_uploaded(db: Session) -> list[PublishedCafe]:
    rows = db.execute(
        select(Restaurant, MenuVersion.published_at)
        .join(MenuVersion, MenuVersion.restaurant_id == Restaurant.id)
        .where(MenuVersion.source == "upload")
        .order_by(MenuVersion.published_at.desc())
    ).all()
    out = []
    for restaurant, published_at in rows:
        items = db.scalars(select(MenuItem.category_id).where(MenuItem.restaurant_id == restaurant.id)).all()
        out.append(
            PublishedCafe(
                slug=restaurant.slug, name=restaurant.name, path=f"/r/{restaurant.slug}", item_count=len(items),
                category_count=len(set(items)), city=restaurant.city,
                published_at=published_at.isoformat() if published_at else None,
                owner_name=restaurant.owner_name, owner_email=restaurant.owner_email,
            )
        )
    return out


def delete_uploaded(db: Session, slug: str) -> bool:
    restaurant = db.scalar(select(Restaurant).where(Restaurant.slug == slug))
    if restaurant is None or not _is_uploaded(db, restaurant):
        return False
    db.delete(restaurant)
    db.commit()
    return True

