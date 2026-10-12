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

from pydantic import BaseModel, Field

from app.money import to_money

_PRICE_LINE = re.compile(
    r"^(?P<name>[^\d₹]{2,80}?)\s*(?:\.{2,}|-{2,}|\s{2,}|:|–|-)?\s*(?:₹|rs\.?|inr)?\s*(?P<price>\d{1,5}(?:\.\d{1,2})?)\s*(?:/-)?\s*(?:[-–:]\s*(?P<desc>.+))?$",
    re.IGNORECASE,
)


class DraftItem(BaseModel):
    category: str
    name: str
    price: Decimal
    description: str | None = None
    # Always unverified at import time; the owner must confirm these.
    dietary_status: str = "unknown"
    allergens_status: str = "unknown"
    source_line: int


class DraftMenu(BaseModel):
    items: list[DraftItem]
    unparsed_lines: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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
                DraftItem(
                    category=category,
                    name=re.sub(r"\s+", " ", m.group("name")).strip(" .-:–"),
                    price=to_money(m.group("price")),
                    description=(m.group("desc") or "").strip() or None,
                    source_line=n,
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
    return DraftMenu(items=items, unparsed_lines=unparsed, warnings=warnings)
