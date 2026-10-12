"""Tenant-scoped menu access. Every query here filters by restaurant_id."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Menu, MenuCategory, MenuItem, Restaurant
from app.schemas.menu import (
    AddonOut,
    CategoryOut,
    CategoryWithItems,
    DietaryInfo,
    KnownList,
    MenuItemOut,
    MenuOut,
    RestaurantOut,
    RestaurantSettingsOut,
    VariantOut,
)


class NotFound(Exception):
    pass


def get_restaurant(db: Session, slug: str) -> Restaurant:
    restaurant = db.scalar(
        select(Restaurant)
        .where(Restaurant.slug == slug, Restaurant.is_active.is_(True))
        .options(selectinload(Restaurant.settings))
    )
    if restaurant is None:
        raise NotFound(f"Restaurant '{slug}' not found")
    return restaurant


def _active_menu_ids(db: Session, restaurant_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        db.scalars(select(Menu.id).where(Menu.restaurant_id == restaurant_id, Menu.is_active.is_(True)))
    )


def _item_query(restaurant_id: uuid.UUID, menu_ids: list[uuid.UUID]):
    return (
        select(MenuItem)
        .join(MenuCategory, MenuItem.category_id == MenuCategory.id)
        .where(
            MenuItem.restaurant_id == restaurant_id,
            MenuCategory.restaurant_id == restaurant_id,
            MenuCategory.is_active.is_(True),
            MenuItem.menu_id.in_(menu_ids),
        )
        .options(
            selectinload(MenuItem.variants),
            selectinload(MenuItem.addons),
            selectinload(MenuItem.category),
        )
        .order_by(MenuCategory.sort_order, MenuItem.sort_order, MenuItem.name)
    )


def load_items(db: Session, restaurant: Restaurant) -> list[MenuItem]:
    """All items on the restaurant's active menus (available or not)."""
    menu_ids = _active_menu_ids(db, restaurant.id)
    if not menu_ids:
        return []
    return list(db.scalars(_item_query(restaurant.id, menu_ids)))


def get_item(db: Session, restaurant: Restaurant, item_id: uuid.UUID) -> MenuItem:
    menu_ids = _active_menu_ids(db, restaurant.id)
    item = db.scalar(_item_query(restaurant.id, menu_ids).where(MenuItem.id == item_id)) if menu_ids else None
    if item is None:
        raise NotFound("Menu item not found")
    return item


def load_categories(db: Session, restaurant: Restaurant) -> list[MenuCategory]:
    menu_ids = _active_menu_ids(db, restaurant.id)
    if not menu_ids:
        return []
    return list(
        db.scalars(
            select(MenuCategory)
            .where(
                MenuCategory.restaurant_id == restaurant.id,
                MenuCategory.menu_id.in_(menu_ids),
                MenuCategory.is_active.is_(True),
            )
            .order_by(MenuCategory.sort_order, MenuCategory.name)
        )
    )


# ---- price helpers ---------------------------------------------------------


def available_variants(item: MenuItem):
    return [v for v in item.variants if v.is_available]


def price_from(item: MenuItem) -> Decimal:
    """Lowest price a customer can currently pay for the item (excl. add-ons)."""
    variants = available_variants(item)
    if variants:
        return min(v.price for v in variants)
    return item.price


def is_orderable(item: MenuItem) -> bool:
    if not item.is_available:
        return False
    if item.variants and not available_variants(item):
        return False
    return True


# ---- serialisation ---------------------------------------------------------


def _tri(value: bool | None) -> str:
    return "unknown" if value is None else ("yes" if value else "no")


def dietary_labels(item: MenuItem) -> list[str]:
    """Only labels the restaurant has explicitly verified."""
    if item.is_vegan:
        return ["Vegan", "Vegetarian"] if item.is_vegetarian is not False else ["Vegan"]
    if item.is_vegetarian:
        return ["Vegetarian"]
    if item.is_vegetarian is False:
        return ["Non-vegetarian"]
    return []


def serialize_item(item: MenuItem) -> MenuItemOut:
    return MenuItemOut(
        id=item.id,
        category_id=item.category_id,
        category_name=item.category.name,
        name=item.name,
        description=item.description,
        price=item.price,
        price_from=price_from(item),
        currency=item.currency,
        is_available=is_orderable(item),
        image_url=item.image_url,
        item_type=item.item_type,  # type: ignore[arg-type]
        temperature=item.temperature,  # type: ignore[arg-type]
        contains_coffee=item.contains_coffee,
        caffeine_level=item.caffeine_level,
        strength=item.strength,
        sweetness=item.sweetness,
        serves=item.serves,
        dietary=DietaryInfo(vegetarian=_tri(item.is_vegetarian), vegan=_tri(item.is_vegan)),  # type: ignore[arg-type]
        dietary_labels=dietary_labels(item),
        ingredients=KnownList(
            status=item.ingredients_status,  # type: ignore[arg-type]
            items=list(item.ingredients or []) if item.ingredients_status != "unknown" else [],
        ),
        allergens=KnownList(
            status=item.allergens_status,  # type: ignore[arg-type]
            items=list(item.allergens or []) if item.allergens_status == "verified" else [],
        ),
        flavor_tags=list(item.flavor_tags or []),
        variant_required=item.variant_required,
        variants=[
            VariantOut(id=v.id, name=v.name, price=v.price, is_default=v.is_default, is_available=v.is_available)
            for v in item.variants
        ],
        addons=[
            AddonOut(id=a.id, name=a.name, group_name=a.group_name, price=a.price, is_available=a.is_available)
            for a in item.addons
            if a.restaurant_id == item.restaurant_id
        ],
        is_featured=item.is_featured,
    )


def serialize_restaurant(restaurant: Restaurant) -> RestaurantOut:
    s = restaurant.settings
    return RestaurantOut(
        id=restaurant.id,
        slug=restaurant.slug,
        name=restaurant.name,
        tagline=restaurant.tagline,
        address_line=restaurant.address_line,
        city=restaurant.city,
        phone=restaurant.phone,
        logo_url=restaurant.logo_url,
        currency=restaurant.currency,
        settings=RestaurantSettingsOut(
            assistant_name=s.assistant_name if s else "Your Guide",
            welcome_message=s.welcome_message if s else "Hi! How can I help you today?",
            suggested_prompts=list(s.suggested_prompts) if s else [],
            ai_enabled=s.ai_enabled if s else True,
            pickup_enabled=s.pickup_enabled if s else True,
            ordering_enabled=s.ordering_enabled if s else False,
            allergen_disclaimer=s.allergen_disclaimer if s else "",
            brand_color=s.brand_color if s else None,
            assistant_icon=(s.assistant_icon or "coffee") if s else "coffee",
        ),
    )


def build_menu(db: Session, restaurant: Restaurant) -> MenuOut:
    categories = load_categories(db, restaurant)
    items = load_items(db, restaurant)
    by_cat: dict[uuid.UUID, list[MenuItemOut]] = {c.id: [] for c in categories}
    for item in items:
        if item.category_id in by_cat:
            by_cat[item.category_id].append(serialize_item(item))
    return MenuOut(
        restaurant_slug=restaurant.slug,
        currency=restaurant.currency,
        categories=[
            CategoryWithItems(
                id=c.id,
                name=c.name,
                slug=c.slug,
                description=c.description,
                item_count=len(by_cat[c.id]),
                items=by_cat[c.id],
            )
            for c in categories
        ],
    )


def category_summaries(db: Session, restaurant: Restaurant) -> list[CategoryOut]:
    menu = build_menu(db, restaurant)
    return [CategoryOut(**c.model_dump(exclude={"items"})) for c in menu.categories]
