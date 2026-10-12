"""Seed the database with demo restaurants.

    python -m app.seed.seed            # insert if missing
    python -m app.seed.seed --reset    # delete demo restaurants first, then insert
"""

from __future__ import annotations

import argparse
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, utcnow
from app.models import (
    Menu,
    MenuAddon,
    MenuCategory,
    MenuItem,
    MenuItemVariant,
    MenuVersion,
    Restaurant,
    RestaurantSettings,
)
from app.seed.data import RESTAURANTS as DEMO_RESTAURANTS
from app.seed.meloghrano import MELOGHRANO
from app.services import menu_service


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def seed_restaurant(db: Session, spec: dict) -> Restaurant:
    restaurant = Restaurant(**spec["restaurant"])
    db.add(restaurant)
    db.flush()
    db.add(RestaurantSettings(restaurant_id=restaurant.id, **spec["settings"]))
    menu = Menu(restaurant_id=restaurant.id, name="Main menu")
    db.add(menu)
    db.flush()

    addons: dict[str, MenuAddon] = {}
    for n, a in enumerate(spec["addons"]):
        addon = MenuAddon(restaurant_id=restaurant.id, menu_id=menu.id, sort_order=n, **a)
        db.add(addon)
        addons[addon.name] = addon
    db.flush()

    for c_order, cat in enumerate(spec["categories"]):
        category = MenuCategory(
            restaurant_id=restaurant.id, menu_id=menu.id, name=cat["name"], slug=cat["slug"],
            description=cat["description"], sort_order=c_order,
        )
        db.add(category)
        db.flush()
        for i_order, raw in enumerate(cat["items"]):
            data = dict(raw)
            variants = data.pop("variants")
            addon_names = data.pop("addons")
            it = MenuItem(
                restaurant_id=restaurant.id, menu_id=menu.id, category_id=category.id, slug=slugify(data["name"]),
                currency=restaurant.currency, sort_order=i_order, **data,
            )
            it.addons = [addons[n] for n in addon_names]
            db.add(it)
            db.flush()
            for v_order, v in enumerate(variants):
                db.add(MenuItemVariant(restaurant_id=restaurant.id, item_id=it.id, sort_order=v_order, **v))
    db.flush()

    # Publish version 1 with an immutable snapshot of what customers see.
    db.expire_all()
    restaurant = db.get(Restaurant, restaurant.id)
    snapshot = menu_service.build_menu(db, restaurant).model_dump(mode="json")
    db.add(
        MenuVersion(
            restaurant_id=restaurant.id, menu_id=menu.id, version_number=1, status="published", source="seed",
            snapshot=snapshot, notes="Initial demo menu", published_at=utcnow(),
        )
    )
    return restaurant


RESTAURANTS = [*DEMO_RESTAURANTS, MELOGHRANO]


def seed(db: Session, *, reset: bool = False) -> list[str]:
    created = []
    for spec in RESTAURANTS:
        slug = spec["restaurant"]["slug"]
        existing = db.scalar(select(Restaurant).where(Restaurant.slug == slug))
        if existing is not None:
            if not reset:
                # Keep the menu and conversations; refresh profile + branding.
                for key, value in spec["restaurant"].items():
                    setattr(existing, key, value)
                if existing.settings is not None:
                    for key, value in spec["settings"].items():
                        setattr(existing.settings, key, value)
                continue
            db.delete(existing)
            db.flush()
        seed_restaurant(db, spec)
        created.append(slug)
    db.commit()
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Replace existing demo restaurants")
    args = parser.parse_args()
    with SessionLocal() as db:
        created = seed(db, reset=args.reset)
    print(f"Seeded: {', '.join(created) or 'none new'}; refreshed settings for existing restaurants")


if __name__ == "__main__":
    main()
