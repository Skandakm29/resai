from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

TriState = Literal["yes", "no", "unknown"]


class VariantOut(BaseModel):
    id: UUID
    name: str
    price: Decimal
    is_default: bool
    is_available: bool


class AddonOut(BaseModel):
    id: UUID
    name: str
    group_name: str
    price: Decimal
    is_available: bool


class DietaryInfo(BaseModel):
    vegetarian: TriState
    vegan: TriState


class KnownList(BaseModel):
    """A list whose completeness is explicit.

    status="verified": the list is complete per the restaurant.
    status="partial": items listed are correct but the list may be incomplete.
    status="unknown": nothing has been verified; an empty list proves nothing.
    """

    status: Literal["verified", "partial", "unknown"]
    items: list[str]


class MenuItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_id: UUID
    category_name: str
    name: str
    description: str | None
    price: Decimal
    # Lowest currently-available price (variant-aware); equals price otherwise.
    price_from: Decimal
    currency: str
    is_available: bool
    image_url: str | None
    item_type: Literal["beverage", "food", "dessert"]
    temperature: Literal["hot", "cold"] | None
    contains_coffee: bool | None
    caffeine_level: str | None
    strength: int | None
    sweetness: int | None
    serves: int
    dietary: DietaryInfo
    dietary_labels: list[str]
    ingredients: KnownList
    allergens: KnownList
    flavor_tags: list[str]
    variant_required: bool
    variants: list[VariantOut]
    addons: list[AddonOut]
    is_featured: bool


class CategoryOut(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    item_count: int


class CategoryWithItems(CategoryOut):
    items: list[MenuItemOut]


class RestaurantSettingsOut(BaseModel):
    assistant_name: str
    welcome_message: str
    suggested_prompts: list[str]
    ai_enabled: bool
    pickup_enabled: bool
    ordering_enabled: bool
    allergen_disclaimer: str
    brand_color: str | None = None
    assistant_icon: str = "coffee"


class RestaurantOut(BaseModel):
    id: UUID
    slug: str
    name: str
    tagline: str | None
    address_line: str | None
    city: str | None
    phone: str | None
    logo_url: str | None
    currency: str
    settings: RestaurantSettingsOut


class MenuOut(BaseModel):
    restaurant_slug: str
    currency: str
    categories: list[CategoryWithItems]
