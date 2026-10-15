"""Menu ingestion - step 1 of onboarding: turn raw menu text into a draft.

Input is plain text, e.g. the output of OCR on a PDF/photo of a menu:

    HOT COFFEE
    Cappuccino ............ 210
    Flat White  ₹230 - velvety microfoam

The output is a *draft* for an owner to review and correct. Nothing is
published, and nothing is inferred beyond name/price/category/description:
dietary and allergen fields always start as "unknown" until the owner
verifies them. OCR and LLM-assisted extraction plug in before this step.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.money import to_money

_PRICE_LINE = re.compile(
    r"^(?P<name>[^\d₹]{2,80}?)\s*(?:\.{2,}|-{2,}|\s{2,}|:|–|-)?\s*(?:₹|rs\.?|inr)?\s*(?P<price>\d{1,5}(?:\.\d{1,2})?)\s*(?:/-)?\s*(?:[-–:]\s*(?P<desc>.+))?$",
    re.IGNORECASE,
)


class DraftVariant(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class DraftItem(BaseModel):
    category: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    description: str | None = Field(default=None, max_length=1000)
    # Coarse classification used for search and ranking (a guess until reviewed).
    item_type: Literal["beverage", "food", "dessert"] = "food"
    temperature: Literal["hot", "cold"] | None = None
    contains_coffee: bool | None = None
    # Only set when the menu itself marks it (e.g. a veg/non-veg symbol).
    is_vegetarian: bool | None = None
    tags: list[str] = Field(default_factory=list, max_length=12)
    variants: list[DraftVariant] = Field(default_factory=list, max_length=12)
    # Always unverified at import time; the owner must confirm these.
    dietary_status: str = "unknown"
    allergens_status: str = "unknown"
    source_line: int | None = None


class DraftProfile(BaseModel):
    """Restaurant details read off the menu, to prefill the publish form."""

    name: str | None = None
    tagline: str | None = None
    address_line: str | None = None
    city: str | None = None
    phone: str | None = None


class DraftMenu(BaseModel):
    items: list[DraftItem]
    profile: DraftProfile = Field(default_factory=DraftProfile)
    unparsed_lines: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # How the draft was produced: "text-rules", "text-llm" or "vision".
    method: str = "text-rules"


_DRINK_WORDS = (
    "coffee", "espresso", "latte", "cappuccino", "mocha", "americano", "frappe", "tea", "chai", "matcha",
    "juice", "shake", "smoothie", "drink", "beverage", "cooler", "mojito", "lemonade", "soda", "lassi",
    "chocolate", "brew", "macchiato", "cortado", "affogato", "kombucha", "mocktail", "water",
)
_DESSERT_WORDS = (
    "dessert", "cake", "brownie", "ice cream", "gelato", "pastry", "cheesecake", "tiramisu", "waffle",
    "sundae", "cookie", "pudding", "mousse", "tart", "sweet",
)
_COLD_WORDS = ("iced", "ice ", "cold", "frappe", "shake", "smoothie", "cooler", "mojito", "lemonade", "soda")
_COFFEE_WORDS = ("coffee", "espresso", "latte", "cappuccino", "mocha", "americano", "frappe", "macchiato",
                 "cortado", "affogato", "flat white")


def _has(text: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(w.strip())}", text) for w in words)


def classify(item: DraftItem) -> DraftItem:
    """Guess type/temperature/coffee from the item and category names (rules only)."""
    name, category = item.name.lower(), item.category.lower()
    if _has(category, _DESSERT_WORDS) or _has(name, _DESSERT_WORDS) and not _has(name, ("shake", "smoothie")):
        item.item_type = "dessert"
    elif _has(category, _DRINK_WORDS) or _has(name, _DRINK_WORDS):
        item.item_type = "beverage"
    if item.item_type == "beverage":
        both = f"{category} {name}"
        if _has(both, _COLD_WORDS):
            item.temperature = "cold"
        elif "hot" in both:
            item.temperature = "hot"
        item.contains_coffee = True if _has(both, _COFFEE_WORDS) else None
    return item


def parse_menu_text(text: str) -> DraftMenu:
    category = "Uncategorised"
    items: list[DraftItem] = []
    unparsed: list[str] = []
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        m = _PRICE_LINE.match(line)
        if m and m.group("name").strip(" .-:"):
            items.append(
                classify(
                    DraftItem(
                        category=category,
                        name=re.sub(r"\s+", " ", m.group("name")).strip(" .-:–"),
                        price=to_money(m.group("price")),
                        description=(m.group("desc") or "").strip() or None,
                        source_line=n,
                    )
                )
            )
        elif not re.search(r"\d", line) and len(line) <= 60:
            category = line.strip(" :-").title()
        else:
            unparsed.append(line)
    warnings = []
    if not items:
        warnings.append("No priced items were found. Check the text or try a clearer scan.")
    names = [i.name.lower() for i in items]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        warnings.append(f"Duplicate item names: {', '.join(dupes)}")
    return DraftMenu(items=items, unparsed_lines=unparsed, warnings=warnings, method="text-rules")
