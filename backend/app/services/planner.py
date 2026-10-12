"""Deterministic meal planner: "4 of us, starters + mains, ₹2000".

Builds a concrete order from real menu items. Assumptions (stated in the
reply): one main / drink each, one starter / dessert per two people. Picks
are greedy by preference score with a feasibility check, so the plan always
fits the budget when any plan can; otherwise the cheapest plan is returned
and flagged. All money is Decimal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal

from app.models import MenuItem
from app.money import format_inr, to_money
from app.schemas.assistant import SearchFilters
from app.services.menu_service import available_variants, is_orderable, price_from
from app.services.search import courses_of, keyword_hits, matches

COURSE_ORDER = ["main", "starter", "dessert", "drink"]  # fill the priciest course first
COURSE_LABEL = {"starter": "starter", "main": "main", "dessert": "dessert", "drink": "drink"}
# Relative share of the budget each course portion should get.
COURSE_WEIGHT = {"main": 1.0, "starter": 0.8, "dessert": 0.75, "drink": 0.6}


def portions(course: str, party: int) -> int:
    if course in ("main", "drink"):
        return party
    return max(1, math.ceil(party / 2))  # starters and desserts are shared


@dataclass
class PlanPick:
    course: str
    item: MenuItem
    variant: object | None
    quantity: int
    unit_price: Decimal

    @property
    def line_total(self) -> Decimal:
        return to_money(self.unit_price * self.quantity)


@dataclass
class PlanResult:
    picks: list[PlanPick]
    party: int
    budget: Decimal | None
    courses: list[str]
    within_budget: bool
    assumptions: list[str] = field(default_factory=list)
    missing_courses: list[str] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return to_money(sum((p.line_total for p in self.picks), Decimal("0")))

    @property
    def per_person(self) -> Decimal:
        return to_money(self.total / self.party)

    @property
    def remaining(self) -> Decimal | None:
        return None if self.budget is None else to_money(self.budget - self.total)

    def subtotal(self, course: str) -> Decimal:
        return to_money(sum((p.line_total for p in self.picks if p.course == course), Decimal("0")))


def _cheapest_variant(item: MenuItem):
    variants = available_variants(item)
    if not variants:
        return None
    return min(variants, key=lambda v: (v.price, v.sort_order))


def _pool(items: list[MenuItem], f: SearchFilters, course: str) -> list[MenuItem]:
    # Dietary/allergen constraints are hard; type/taste/keywords are preferences.
    probe = f.model_copy(update={"max_price": None, "min_price": None, "party_size": 1})
    ignore = frozenset({"keywords", "temperature", "taste", "tags", "item_type", "courses", "coffee"})
    return [
        i for i in items
        if is_orderable(i) and course in courses_of(i) and matches(i, probe.model_copy(update={"contains_coffee": None}), ignore=ignore)
    ]


def _score(item: MenuItem, f: SearchFilters, chosen: list[PlanPick], course: str) -> float:
    score = 0.0
    if item.is_featured:
        score += 2
    tags = set(item.tags or [])
    if course == "main" and tags & {"main", "pasta", "pizza"}:
        score += 1  # proper mains over wraps/sandwiches
    if course == "starter" and "starter" in tags:
        score += 1  # appetizers over plain breads
    if f.keywords:
        name_hits, other = keyword_hits(item, f.keywords)
        score += 3 * name_hits + other
    same_course = [p.item for p in chosen if p.course == course]
    if any(p.category_id == item.category_id for p in same_course):
        score -= 1.0  # variety across categories (pizza + pasta + risotto...)
    if any(set(p.tags or []) & set(item.tags or []) - {"sourdough", "main", "starter"} for p in same_course):
        score -= 0.5
    return score


def build_plan(items: list[MenuItem], f: SearchFilters, courses: list[str]) -> PlanResult:
    party = max(1, f.party_size)
    budget = f.max_price
    courses = [c for c in COURSE_ORDER if c in courses] or ["starter", "main"]
    pools = {c: _pool(items, f, c) for c in courses}
    missing = [c for c in courses if not pools[c]]
    courses = [c for c in courses if pools[c]]

    # Distinct dishes per course: e.g. 4 different mains, 2 different starters.
    slots = [c for c in courses for _ in range(portions(c, party))]
    order_index = {i.id: n for n, i in enumerate(items)}

    def unit(i: MenuItem) -> Decimal:
        return price_from(i)

    def min_cost(rest: list[str], used: set) -> Decimal:
        total = Decimal("0")
        for c in set(rest):
            need = rest.count(c)
            prices = sorted(unit(i) for i in pools[c] if i.id not in used)
            if not prices:
                prices = sorted(unit(i) for i in pools[c])
            while len(prices) < need:
                prices.append(prices[0])
            total += sum(prices[:need])
        return total

    chosen: list[PlanPick] = []
    spent = Decimal("0")
    feasible = True
    for n, course in enumerate(slots):
        rest = slots[n + 1:]
        used = {p.item.id for p in chosen}
        candidates = [i for i in pools[course] if i.id not in used] or pools[course]
        if budget is not None:
            # Aim each slot at its fair share of what's left, so the plan is
            # balanced instead of spending everything on the first dishes.
            weights = sum(COURSE_WEIGHT[c] for c in slots[n:])
            target = float(budget - spent) * COURSE_WEIGHT[course] / weights
            candidates.sort(key=lambda i: (-_score(i, f, chosen, course), abs(float(unit(i)) - target)))
        else:
            candidates.sort(key=lambda i: (-_score(i, f, chosen, course), order_index.get(i.id, 0)))
        pick = None
        for cand in candidates:
            cost = unit(cand)
            if budget is None or spent + cost + min_cost(rest, used | {cand.id}) <= budget:
                pick = cand
                break
        if pick is None:
            feasible = False
            break
        chosen.append(PlanPick(course, pick, _cheapest_variant(pick), 1, unit(pick)))
        spent += unit(pick)

    if not feasible:
        # Nothing fits: return the cheapest possible plan, clearly flagged.
        chosen, used = [], set()
        for course in slots:
            cands = sorted((i for i in pools[course] if i.id not in used), key=unit) or sorted(pools[course], key=unit)
            pick = cands[0]
            used.add(pick.id)
            chosen.append(PlanPick(course, pick, _cheapest_variant(pick), 1, unit(pick)))

    # Merge repeats of the same dish into one line with a quantity.
    merged: dict = {}
    for p in chosen:
        key = (p.course, p.item.id)
        if key in merged:
            merged[key].quantity += 1
        else:
            merged[key] = p
    picks = list(merged.values())
    picks.sort(key=lambda p: (["starter", "main", "dessert", "drink"].index(p.course), p.unit_price))

    assumptions = []
    if "main" in courses:
        assumptions.append("One main course each" if party > 1 else "One main course")
    if "starter" in courses and party > 1:
        n = portions("starter", party)
        assumptions.append(f"{n} starter{'s' if n != 1 else ''} to share (one per two people)")
    if "dessert" in courses and party > 1:
        n = portions("dessert", party)
        assumptions.append(f"{n} dessert{'s' if n != 1 else ''} to share")
    if "drink" in courses:
        assumptions.append("One drink each")
    if any(p.variant is not None and len(available_variants(p.item)) > 1 for p in picks):
        assumptions.append("Where a dish has options (size, pasta shape), the first/lowest-priced one is used - change it when adding to cart")
    assumptions.append("Prices before taxes and add-ons")

    result = PlanResult(
        picks=picks, party=party, budget=budget, courses=courses,
        within_budget=feasible and (budget is None or sum((p.line_total for p in picks), Decimal("0")) <= budget),
        assumptions=assumptions, missing_courses=missing,
    )
    return result


def describe_plan(plan: PlanResult) -> str:
    """Factual summary sentence(s) for the reply."""
    counts = {c: sum(p.quantity for p in plan.picks if p.course == c) for c in plan.courses}
    parts = [f"{n} {COURSE_LABEL[c]}{'s' if n != 1 else ''}" for c, n in counts.items() if n]
    group = f"for {plan.party}" if plan.party > 1 else "for you"
    text = ""
    if plan.budget is not None and plan.within_budget:
        text = (
            f"Here's a plan {group} within {format_inr(plan.budget)}: {', '.join(parts)} - "
            f"{format_inr(plan.total)} in total (about {format_inr(plan.per_person)} per person), "
            f"leaving {format_inr(plan.remaining)}."
        )
    elif plan.budget is not None:
        text = (
            f"A plan with {', '.join(parts)} {group} can't fit {format_inr(plan.budget)} - the cheapest "
            f"combination comes to {format_inr(plan.total)} ({format_inr(plan.total - plan.budget)} over). "
            "Here it is; you could raise the budget or share mains instead."
        )
    else:
        text = f"Here's a plan {group}: {', '.join(parts)} - {format_inr(plan.total)} in total (about {format_inr(plan.per_person)} per person)."
    if plan.missing_courses:
        text += f" I couldn't find any {' or '.join(plan.missing_courses)} options that fit your filters."
    return text
