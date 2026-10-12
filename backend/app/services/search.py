"""Deterministic menu search: filtering, ranking and fact-based reasons.

The LLM never touches this module's inputs other than through a validated
``SearchFilters`` object, and never sees or sets prices except as read-only
context. All money arithmetic is Decimal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal

from app.models import MenuItem
from app.money import format_inr, to_money
from app.schemas.assistant import SearchFilters
from app.services.matching import contains_phrase, normalize
from app.services.menu_service import is_orderable, price_from


@dataclass
class ScoredItem:
    item: MenuItem
    score: float
    reasons: list[str]
    unit_price: Decimal
    quantity: int
    total: Decimal
    over_budget: bool = False


@dataclass
class SearchOutcome:
    matches: list[ScoredItem]
    # Closest real items when nothing matched (e.g. just above budget).
    alternatives: list[ScoredItem] = field(default_factory=list)
    # Which soft constraints were dropped to produce ``matches``.
    relaxed: list[str] = field(default_factory=list)
    # Items that match everything except availability.
    unavailable_matches: list[MenuItem] = field(default_factory=list)
    # Items excluded only because their allergen data is unverified.
    unknown_allergen_items: list[MenuItem] = field(default_factory=list)


def quantity_for(item: MenuItem, party_size: int) -> int:
    if party_size <= 1:
        return 1
    return max(1, math.ceil(party_size / max(item.serves, 1)))


def _haystack(item: MenuItem) -> str:
    parts = [item.name, item.description or "", item.category.name if item.category else ""]
    parts += list(item.tags or []) + list(item.flavor_tags or []) + list(item.search_keywords or [])
    return normalize(" ".join(parts))


def keyword_hits(item: MenuItem, keywords: list[str]) -> tuple[int, int]:
    """(name hits, other hits)."""
    name = normalize(item.name)
    hay = _haystack(item)
    in_name = sum(1 for k in keywords if contains_phrase(name, normalize(k)))
    elsewhere = sum(1 for k in keywords if contains_phrase(hay, normalize(k)))
    return in_name, elsewhere


class _Reject(Exception):
    def __init__(self, reason: str):
        self.reason = reason


def _check(item: MenuItem, f: SearchFilters, *, ignore: frozenset[str] = frozenset()) -> None:
    if not f.include_unavailable and not is_orderable(item):
        raise _Reject("unavailable")
    if f.item_types and item.item_type not in f.item_types:
        raise _Reject("item_type")
    if f.contains_coffee is not None and item.contains_coffee is not f.contains_coffee:
        raise _Reject("coffee")
    if f.temperature and "temperature" not in ignore and item.temperature != f.temperature:
        raise _Reject("temperature")
    if f.tags_any and "tags" not in ignore and not set(f.tags_any) & set(item.tags or []):
        raise _Reject("tags")
    if f.keywords and "keywords" not in ignore and sum(keyword_hits(item, f.keywords)) == 0:
        raise _Reject("keywords")
    if "vegan" in f.dietary and item.is_vegan is not True:
        raise _Reject("dietary")
    if "vegetarian" in f.dietary and item.is_vegetarian is not True:
        raise _Reject("dietary")
    if f.exclude_allergens:
        if item.allergens_status != "verified":
            raise _Reject("allergen_unknown")
        if set(f.exclude_allergens) & {a.lower() for a in item.allergens or []}:
            raise _Reject("allergen")
    if f.caffeine_free and item.caffeine_level != "none":
        raise _Reject("caffeine")
    if "taste" not in ignore:
        if f.max_sweetness is not None and (item.sweetness is None or item.sweetness > f.max_sweetness):
            raise _Reject("sweetness")
        if f.min_sweetness is not None and (item.sweetness is None or item.sweetness < f.min_sweetness):
            raise _Reject("sweetness")
        if f.min_strength is not None and (item.strength is None or item.strength < f.min_strength):
            raise _Reject("strength")
        if f.max_strength is not None and (item.strength is None or item.strength > f.max_strength):
            raise _Reject("strength")
    if "price" not in ignore:
        unit = price_from(item)
        total = unit * quantity_for(item, f.party_size)
        if f.max_price is not None and total > f.max_price:
            raise _Reject("price")
        if f.min_price is not None and unit < f.min_price:
            raise _Reject("price")


def matches(item: MenuItem, f: SearchFilters, *, ignore: frozenset[str] = frozenset()) -> bool:
    try:
        _check(item, f, ignore=ignore)
        return True
    except _Reject:
        return False


def reasons_for(item: MenuItem, f: SearchFilters, quantity: int, total: Decimal, *, over_budget=False) -> list[str]:
    """Short, verifiable facts explaining why the item fits."""
    reasons: list[str] = []
    unit = price_from(item)
    has_variants = bool(item.variants)
    if f.party_size > 1:
        if item.serves >= f.party_size:
            reasons.append(f"Serves {item.serves} - {format_inr(total)} total")
        else:
            reasons.append(f"{quantity} × {format_inr(unit)} = {format_inr(total)} for {f.party_size}")
    elif f.max_price is not None and not over_budget:
        prefix = "From " if has_variants else ""
        reasons.append(f"{prefix}{format_inr(unit)} - within your {format_inr(f.max_price)} budget")
    if over_budget and f.max_price is not None:
        reasons.append(f"{format_inr(total)} - {format_inr(total - f.max_price)} over your {format_inr(f.max_price)} budget")
    if f.temperature and item.temperature == f.temperature:
        reasons.append("Served iced" if item.temperature == "cold" else "Served hot")
    if f.contains_coffee is False and item.contains_coffee is False:
        reasons.append("Coffee-free")
    if f.caffeine_free and item.caffeine_level == "none":
        reasons.append("Caffeine-free")
    if (f.min_strength or f.sort == "strength_desc") and item.strength:
        reasons.append(f"Strength {item.strength}/5")
    if f.max_sweetness is not None and item.sweetness is not None:
        reasons.append(f"Sweetness {item.sweetness}/5")
    if f.min_sweetness is not None and item.sweetness is not None:
        reasons.append(f"Sweetness {item.sweetness}/5")
    if "vegan" in f.dietary and item.is_vegan:
        reasons.append("Verified vegan")
    elif "vegetarian" in f.dietary and item.is_vegetarian:
        reasons.append("Verified vegetarian")
    if f.exclude_allergens and item.allergens_status == "verified":
        ex = f.exclude_allergens
        listed = ex[0] if len(ex) == 1 else ", ".join(ex[:-1]) + " or " + ex[-1]
        reasons.append(f"No {listed} on its verified allergen list")
    if f.keywords:
        name_hits, _ = keyword_hits(item, f.keywords)
        hits = [k for k in f.keywords if contains_phrase(_haystack(item), normalize(k))]
        if hits and not name_hits:
            reasons.append(f"Matches “{hits[0]}”")
    if f.sort == "price_asc" and not reasons:
        reasons.append(f"{format_inr(unit)}")
    if item.is_featured and len(reasons) < 3:
        reasons.append("House favourite")
    if not reasons:
        if item.temperature:
            reasons.append("Served iced" if item.temperature == "cold" else "Served hot")
        if item.flavor_tags:
            reasons.append(", ".join(item.flavor_tags[:2]).capitalize() + " notes")
    return reasons[:3]


def _score(item: MenuItem, f: SearchFilters) -> float:
    score = 0.0
    if f.keywords:
        name_hits, other_hits = keyword_hits(item, f.keywords)
        score += 3 * name_hits + other_hits
    if item.is_featured:
        score += 1.0
    if f.party_size > 1 and item.serves >= f.party_size:
        score += 1.5
    if f.max_sweetness is not None and item.sweetness is not None:
        score += 0.2 * (f.max_sweetness - item.sweetness)
    if f.min_strength is not None and item.strength is not None:
        score += 0.3 * (item.strength - f.min_strength)
    return score


def _sort(scored: list[ScoredItem], f: SearchFilters) -> list[ScoredItem]:
    if f.sort == "price_asc":
        return sorted(scored, key=lambda s: (s.total, s.item.name))
    if f.sort == "price_desc":
        return sorted(scored, key=lambda s: (-s.total, s.item.name))
    if f.sort == "strength_desc":
        return sorted(scored, key=lambda s: (-(s.item.strength or 0), -s.score, s.total))
    ranked = sorted(scored, key=lambda s: (-s.score, s.total, s.item.name))
    # Without a type/keyword focus, interleave categories for variety.
    if not f.item_types and not f.keywords and not f.tags_any:
        buckets: dict = {}
        for s in ranked:
            buckets.setdefault(s.item.category_id, []).append(s)
        mixed: list[ScoredItem] = []
        while any(buckets.values()):
            for key in list(buckets):
                if buckets[key]:
                    mixed.append(buckets[key].pop(0))
        return mixed
    return ranked


def _scored(item: MenuItem, f: SearchFilters, *, over_budget=False) -> ScoredItem:
    qty = quantity_for(item, f.party_size)
    unit = price_from(item)
    total = to_money(unit * qty)
    return ScoredItem(
        item=item,
        score=_score(item, f),
        reasons=reasons_for(item, f, qty, total, over_budget=over_budget),
        unit_price=unit,
        quantity=qty,
        total=total,
        over_budget=over_budget,
    )


def search(items: list[MenuItem], f: SearchFilters, *, limit: int = 4) -> SearchOutcome:
    hits = [_scored(i, f) for i in items if matches(i, f)]
    outcome = SearchOutcome(matches=_sort(hits, f)[:limit])

    if not outcome.matches and f.keywords:
        # Keywords are soft: retry without them, and say so in the reply.
        relaxed = [_scored(i, f) for i in items if matches(i, f, ignore=frozenset({"keywords"}))]
        if relaxed and (f.item_types or f.contains_coffee is not None or f.tags_any or f.temperature):
            outcome.matches = _sort(relaxed, f)[:limit]
            outcome.relaxed.append("keywords")

    if not outcome.matches:
        if f.max_price is not None or f.min_price is not None:
            # Closest real options outside the budget, clearly flagged.
            near = [
                _scored(i, f, over_budget=True)
                for i in items
                if matches(i, f, ignore=frozenset({"price", "keywords"}))
            ]
            outcome.alternatives = sorted(near, key=lambda s: s.total)[:2]
        elif f.temperature or f.max_sweetness or f.min_sweetness or f.min_strength or f.max_strength or f.tags_any:
            near = [_scored(i, f) for i in items if matches(i, f, ignore=frozenset({"temperature", "taste", "tags"}))]
            outcome.alternatives = _sort(near, f)[:2]

    unavailable_f = f.model_copy(update={"include_unavailable": True})
    outcome.unavailable_matches = [
        i for i in items if not is_orderable(i) and matches(i, unavailable_f)
    ][:2]
    if f.exclude_allergens:
        probe = f.model_copy(update={"exclude_allergens": []})
        outcome.unknown_allergen_items = [
            i for i in items if i.allergens_status != "verified" and matches(i, probe)
        ]
    return outcome


def describe_filters(f: SearchFilters) -> list[str]:
    """Human-readable chips for the active constraints."""
    out: list[str] = []
    type_names = {"beverage": "Drinks", "food": "Food", "dessert": "Desserts"}
    if f.contains_coffee is True:
        out.append("Coffee")
    elif f.contains_coffee is False:
        out.append("No coffee")
    for t in f.item_types:
        if not (t == "beverage" and f.contains_coffee is not None):
            out.append(type_names[t])
    if f.temperature:
        out.append("Cold" if f.temperature == "cold" else "Hot")
    out += [t.capitalize() for t in f.tags_any]
    out += [f"“{k}”" for k in f.keywords]
    if f.party_size > 1:
        out.append(f"For {f.party_size}")
    if f.max_price is not None and f.min_price is not None:
        out.append(f"{format_inr(f.min_price)}–{format_inr(f.max_price)}")
    elif f.max_price is not None:
        out.append(f"Up to {format_inr(f.max_price)}" + (" total" if f.party_size > 1 else ""))
    elif f.min_price is not None:
        out.append(f"From {format_inr(f.min_price)}")
    out += [d.capitalize() for d in f.dietary]
    out += [f"No {a}" for a in f.exclude_allergens]
    if f.caffeine_free:
        out.append("Caffeine-free")
    if f.max_sweetness is not None:
        out.append("Not too sweet" if f.max_sweetness <= 2 else f"Sweetness ≤ {f.max_sweetness}")
    if f.min_sweetness is not None:
        out.append("Sweet")
    if f.min_strength is not None:
        out.append("Strong")
    if f.max_strength is not None:
        out.append("Mild")
    if f.sort == "price_asc":
        out.append("Cheapest first")
    elif f.sort == "strength_desc":
        out.append("Strongest first")
    elif f.sort == "price_desc":
        out.append("Priciest first")
    return out
