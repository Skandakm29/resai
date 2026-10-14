"""Assistant orchestration: parse -> deterministic retrieval -> reply.

Pipeline for each customer message:
1. Load the conversation's structured state (active filters, last shown items).
2. Screen the message (guardrails): off-topic tasks are refused and injection
   attempts are kept away from the LLM. Then parse intent + filters (LLM if
   configured, allowed and valid, else rules).
3. Execute the intent with deterministic menu functions.
4. Build a factual reply. Optionally let the LLM reword it; its output is
   validated (item IDs, prices, prohibited claims) or discarded.
5. Persist both messages and the new state.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.llm.base import LLMError, LLMProvider
from app.llm.prompts import (
    COMPOSE_SCHEMA,
    COMPOSE_SYSTEM,
    PARSE_SCHEMA,
    PARSE_SYSTEM,
    validate_compose_output,
    validate_parse_output,
)
from app.models import Conversation, ConversationMessage, MenuItem, Restaurant
from app.money import format_inr, to_money
from app.schemas.assistant import (
    ChatRequest,
    ChatResponse,
    Clarification,
    Comparison,
    ComparisonRow,
    CourseSubtotal,
    MealPlan,
    PlanLine,
    Intent,
    ParsedQuery,
    Recommendation,
    SearchFilters,
)
from app.services import guardrails, menu_service
from app.services.intent_rules import parse_message
from app.services.matching import find_mentions, normalize, resolve_names
from app.services.planner import build_plan, describe_plan, portions
from app.services.search import ScoredItem, courses_of, describe_filters, matches, quantity_for, search

logger = logging.getLogger(__name__)

# Intents whose filters describe a one-off question; they must not overwrite
# the conversation's active search constraints.
# Dishes eaten with bread (pairing suggests naan/roti/kulcha for them).
GRAVY_TAGS = {"curry", "dal", "sabzi"}

NON_SEARCH_INTENTS = {"item_info", "compare", "order_help", "off_topic", "clarify"}

ALLERGEN_WORDS = {
    "milk": ("milk", "dairy", "lactose", "cream", "cheese"),
    "tree nuts": ("nut", "nuts", "almond", "hazelnut", "walnut", "cashew", "pistachio"),
    "peanuts": ("peanut", "peanuts"),
    "gluten": ("gluten", "wheat"),
    "egg": ("egg", "eggs"),
    "soy": ("soy", "soya"),
    "sesame": ("sesame",),
    "coconut": ("coconut",),
}


@dataclass
class TurnResult:
    intent: Intent
    message: str
    recs: list[ScoredItem] = field(default_factory=list)
    comparison: Comparison | None = None
    plan: MealPlan | None = None
    clarification: Clarification | None = None
    follow_ups: list[str] = field(default_factory=list)
    filters: SearchFilters = field(default_factory=SearchFilters)
    extra_amounts: set[Decimal] = field(default_factory=set)


def _short(name: str) -> str:
    for prefix in ("Classic ", "The "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def _noun(f: SearchFilters, n: int) -> str:
    plural = n != 1
    if f.contains_coffee is True:
        return "coffees" if plural else "coffee"
    if "tea" in f.tags_any and f.item_types == ["beverage"]:
        return "teas" if plural else "tea"
    if f.item_types == ["beverage"]:
        return "drinks" if plural else "drink"
    if f.item_types == ["dessert"]:
        return "desserts" if plural else "dessert"
    if f.item_types == ["food"]:
        return "dishes" if plural else "dish"
    return "options" if plural else "option"


def _qualifier(f: SearchFilters) -> str:
    parts: list[str] = []
    if f.temperature == "cold":
        parts.append("served cold")
    elif f.temperature == "hot":
        parts.append("served hot")
    if f.contains_coffee is False and f.item_types == ["beverage"]:
        parts.append("without coffee")
    if f.keywords:
        parts.append("matching " + " or ".join(f"“{k}”" for k in f.keywords))
    if f.dietary:
        parts.append(f"that are verified {f.dietary[0]}")
    if f.party_size > 1:
        parts.append(f"for {f.party_size}")
    if f.max_price is not None and f.min_price is not None:
        parts.append(f"between {format_inr(f.min_price)} and {format_inr(f.max_price)}")
    elif f.max_price is not None:
        parts.append(f"at or under {format_inr(f.max_price)}" + (" in total" if f.party_size > 1 else ""))
    elif f.min_price is not None:
        parts.append(f"from {format_inr(f.min_price)}")
    return " ".join(parts)


def _possessive(name: str) -> str:
    return name + ("'" if name.endswith("s") else "'s")


def _join(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


class AssistantService:
    def __init__(self, db: Session, settings: Settings, provider: LLMProvider | None):
        self.db = db
        self.settings = settings
        self.provider = provider

    # ------------------------------------------------------------------ API

    def chat(self, restaurant: Restaurant, req: ChatRequest) -> ChatResponse:
        conversation = self._get_or_create_conversation(restaurant, req.conversation_id)
        state = dict(conversation.state or {})
        previous = SearchFilters.model_validate(state["filters"]) if state.get("filters") else None
        last_ids = [uuid.UUID(i) for i in state.get("last_item_ids", [])]

        items = menu_service.load_items(self.db, restaurant)
        self._suggested = self._prompts(restaurant)
        # Only suggest dietary follow-ups the menu can actually answer.
        self._has_verified_vegan = any(i.is_vegan for i in items if menu_service.is_orderable(i))
        by_id = {i.id: i for i in items}
        last_items = [by_id[i] for i in last_ids if i in by_id]
        cart_items = [by_id[c.item_id] for c in req.cart if c.item_id in by_id]

        strikes = int(state.get("strikes", 0))
        verdict = guardrails.screen(req.message, items)
        if verdict == "off_topic":
            parsed, source = ParsedQuery(intent="off_topic", filters=previous or SearchFilters()), "rules"
        else:
            # Injection attempts and repeat offenders get the rule parser only.
            use_llm = verdict == "ok" and strikes < guardrails.MAX_STRIKES
            parsed, source = self._parse(
                req, conversation, items, previous, last_items, state.get("last_intent"), use_llm=use_llm
            )
        # Strikes come from the guardrails or the LLM - never from the rule
        # parser merely not understanding a message.
        if source == "llm" and parsed.intent == "recommend" and parsed.filters.is_empty() and previous is None:
            # The LLM saw nothing to filter on; if the rules do ("mocktail"), use theirs.
            rules = parse_message(req.message, items)
            if rules.intent == "recommend" and not rules.filters.is_empty():
                parsed = rules
        if verdict != "ok" or (source == "llm" and parsed.intent == "off_topic"):
            strikes += 1
            logger.info("Guardrail: %s message in conversation %s (strike %d)", verdict, conversation.id, strikes)
        result = self._execute(restaurant, parsed, items, previous, last_items, cart_items, req.message)

        notes: dict[str, str] = {}
        # Off-topic replies keep their fixed wording; the LLM never words them.
        if source == "llm" and self.provider is not None and result.intent != "off_topic":
            try:
                composed = self._compose(req.message, result)
                result.message = composed.message
                notes = {n.item_id: n.note for n in composed.item_notes}
                if composed.follow_ups:
                    result.follow_ups = composed.follow_ups
            except LLMError as exc:
                logger.warning("LLM compose failed, using deterministic reply: %s", exc)

        recommendations = [
            Recommendation(
                item=menu_service.serialize_item(s.item),
                reasons=s.reasons,
                note=notes.get(str(s.item.id)),
                suggested_quantity=s.quantity,
                estimated_total=s.total,
                over_budget=s.over_budget,
            )
            for s in result.recs
        ]

        # ---- persist ----
        if result.intent in NON_SEARCH_INTENTS or result.clarification is not None:
            new_filters = previous or SearchFilters()
        else:
            new_filters = result.filters
        shown_ids = (
            [str(s.item.id) for s in result.recs]
            or ([str(line.item.id) for line in result.plan.lines] if result.plan else [])
            or [str(i.id) for i in last_items]
        )
        conversation.state = {
            "filters": new_filters.model_dump(mode="json"),
            "last_item_ids": shown_ids[:6],
            "last_intent": result.intent,
            "strikes": strikes,
        }
        self.db.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role="user",
                content=req.message,
                data={"intent": parsed.intent, "filters": parsed.filters.model_dump(mode="json"), "source": source},
            )
        )
        self.db.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=result.message,
                data={"item_ids": [str(s.item.id) for s in result.recs], "intent": result.intent},
            )
        )
        conversation.message_count = (conversation.message_count or 0) + 2
        self.db.commit()

        return ChatResponse(
            conversation_id=conversation.id,
            message=result.message,
            intent=result.intent,
            recommendations=recommendations,
            comparison=result.comparison,
            plan=result.plan,
            clarification=result.clarification,
            follow_ups=result.follow_ups[:3],
            applied_filters=result.filters,
            filter_summary=describe_filters(result.filters) if result.intent not in NON_SEARCH_INTENTS else [],
            source=source,
        )

    # ------------------------------------------------------------ helpers

    def _get_or_create_conversation(self, restaurant: Restaurant, conversation_id: uuid.UUID | None) -> Conversation:
        if conversation_id is not None:
            conv = self.db.scalar(
                select(Conversation).where(
                    Conversation.id == conversation_id, Conversation.restaurant_id == restaurant.id
                )
            )
            if conv is not None:
                return conv
        # Unknown or foreign IDs are never reused: start a fresh conversation.
        conv = Conversation(restaurant_id=restaurant.id, state={}, message_count=0)
        self.db.add(conv)
        self.db.flush()
        return conv

    def _history(self, req: ChatRequest, conversation: Conversation) -> list[dict]:
        window = self.settings.conversation_history_window
        if window == 0:
            return []
        rows = list(
            self.db.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation.id)
                .order_by(ConversationMessage.created_at.desc())
                .limit(window)
            )
        )[::-1]
        if rows:
            return [{"role": r.role, "content": r.content[:400]} for r in rows]
        return [{"role": t.role, "content": t.content[:400]} for t in req.history[-window:]]

    def _parse(
        self,
        req: ChatRequest,
        conversation: Conversation,
        items: list[MenuItem],
        previous: SearchFilters | None,
        last_items: list[MenuItem],
        previous_intent: str | None = None,
        *,
        use_llm: bool = True,
    ) -> tuple[ParsedQuery, str]:
        if self.provider is not None and use_llm:
            try:
                payload = {
                    "menu": {
                        "categories": sorted({i.category.name for i in items}),
                        "items": [i.name for i in items],
                        "tags": sorted({t for i in items for t in (i.tags or [])}),
                        "flavour_words": sorted({t for i in items for t in (i.flavor_tags or [])}),
                    },
                    "previous_filters": previous.model_dump(mode="json") if previous else None,
                    "previous_intent": previous_intent,
                    "last_shown_items": [i.name for i in last_items],
                    "recent_conversation": self._history(req, conversation),
                    "customer_message": req.message,
                }
                data = self.provider.generate_json(
                    system=PARSE_SYSTEM,
                    user=json.dumps(payload, ensure_ascii=False),
                    schema=PARSE_SCHEMA,
                    max_tokens=1200,
                )
                parsed = validate_parse_output(data)
                return parsed, "llm"
            except LLMError as exc:
                logger.warning("LLM parse failed, falling back to rules: %s", exc)
        parsed = parse_message(
            req.message,
            items,
            previous,
            last_item_prices=[menu_service.price_from(i) for i in last_items],
            previous_intent=previous_intent,
        )
        return parsed, "rules"

    def _compose(self, customer_message: str, result: TurnResult):
        assert self.provider is not None
        allowed_amounts: set[Decimal] = set(result.extra_amounts)
        results_payload = []
        for s in result.recs:
            it = s.item
            allowed_amounts |= {to_money(it.price), s.unit_price, s.total} | {to_money(v.price) for v in it.variants}
            results_payload.append(
                {
                    "id": str(it.id),
                    "name": it.name,
                    "category": it.category.name,
                    "description": it.description,
                    "price_from": str(s.unit_price),
                    "quantity_for_group": s.quantity,
                    "total": str(s.total),
                    "over_budget": s.over_budget,
                    "available": menu_service.is_orderable(it),
                    "temperature": it.temperature,
                    "strength_1_to_5": it.strength,
                    "sweetness_1_to_5": it.sweetness,
                    "dietary_labels": menu_service.dietary_labels(it),
                    "flavour_tags": it.flavor_tags,
                    "facts": s.reasons,
                }
            )
        for amount in (result.filters.max_price, result.filters.min_price):
            if amount is not None:
                allowed_amounts.add(amount)
        if result.plan is not None:
            p = result.plan
            allowed_amounts |= {p.total, p.per_person} | {s.subtotal for s in p.course_subtotals}
            allowed_amounts |= {l.unit_price for l in p.lines} | {l.line_total for l in p.lines}
            if p.remaining is not None:
                allowed_amounts.add(p.remaining)
            if p.budget is not None:
                allowed_amounts |= {p.budget, abs(p.total - p.budget)}
        payload = {
            "customer_message": customer_message,
            "intent": result.intent,
            "active_filters": describe_filters(result.filters),
            "draft_reply": result.message,
            "results": results_payload,
            "comparison": result.comparison.model_dump(mode="json") if result.comparison else None,
            "meal_plan": (
                {
                    "party_size": result.plan.party_size,
                    "budget": str(result.plan.budget) if result.plan.budget is not None else None,
                    "within_budget": result.plan.within_budget,
                    "total": str(result.plan.total),
                    "per_person": str(result.plan.per_person),
                    "remaining": str(result.plan.remaining) if result.plan.remaining is not None else None,
                    "lines": [
                        {"course": l.course, "name": l.item.name, "option": l.variant_name, "quantity": l.quantity, "line_total": str(l.line_total)}
                        for l in result.plan.lines
                    ],
                    "assumptions": result.plan.assumptions,
                }
                if result.plan
                else None
            ),
            "suggested_follow_ups": result.follow_ups,
        }
        data = self.provider.generate_json(
            system=COMPOSE_SYSTEM,
            user=json.dumps(payload, ensure_ascii=False, default=str),
            schema=COMPOSE_SCHEMA,
            max_tokens=1200,
            model=self.settings.llm_compose_model_name,
        )
        return validate_compose_output(
            data,
            allowed_item_ids={str(s.item.id) for s in result.recs},
            allowed_amounts={to_money(a) for a in allowed_amounts},
        )

    # ----------------------------------------------------------- dispatch

    def _execute(
        self,
        restaurant: Restaurant,
        parsed: ParsedQuery,
        items: list[MenuItem],
        previous: SearchFilters | None,
        last_items: list[MenuItem],
        cart_items: list[MenuItem],
        message: str,
    ) -> TurnResult:
        mentioned = resolve_names(parsed.mentioned_items, items)
        # Dish names literally present in the message are matched
        # deterministically too, in case the LLM left them out.
        for it in find_mentions(message, items)[0]:
            if it not in mentioned:
                mentioned.append(it)
        f = parsed.filters
        intent = parsed.intent
        if intent == "recommend" and f.is_empty() and not mentioned and previous is None:
            # "What's good here?" / "surprise me": nothing to filter on yet.
            if favourites := self._house_favourites(restaurant, items, "recommend"):
                return favourites
        if intent in ("recommend", "cheapest"):
            return self._recommend(parsed, items, last_items)
        if intent == "meal_plan":
            return self._meal_plan(parsed, items)
        if intent == "compare":
            return self._compare(mentioned, last_items, items, parsed, f)
        if intent == "pairing":
            return self._pairing(mentioned, last_items, cart_items, items, parsed, f)
        if intent == "item_info":
            targets = mentioned or (last_items[:1] if parsed.refers_to_previous else [])
            return self._item_info(restaurant, targets, items, parsed, message, f)
        if intent == "menu_overview":
            return self._menu_overview(restaurant, items)
        if intent == "greeting":
            return TurnResult(
                intent="greeting",
                message=(
                    f"Hi! Welcome to {restaurant.name}. I can recommend drinks and food, "
                    "find options within your budget, or answer questions about the menu."
                ),
                follow_ups=self._prompts(restaurant)[:3],
            )
        if intent == "order_help":
            return self._order_help(restaurant, cart_items, previous or SearchFilters())
        if intent == "off_topic":
            return TurnResult(
                intent="off_topic",
                message=(
                    f"I can only help with {_possessive(restaurant.name)} menu - recommendations, prices, "
                    "dietary information and your cart. What are you in the mood for?"
                ),
                follow_ups=self._prompts(restaurant)[:3],
                filters=previous or SearchFilters(),
            )
        if previous is None and (favourites := self._house_favourites(restaurant, items, "clarify")):
            return favourites
        return TurnResult(
            intent="clarify",
            message="Happy to help! Are you after a drink, something to eat, or a dessert? A budget helps too.",
            clarification=Clarification(
                question="What would you like?",
                options=self._more(4),
            ),
            follow_ups=self._more(3),
            filters=previous or SearchFilters(),
        )

    def _prompts(self, restaurant: Restaurant) -> list[str]:
        return list(restaurant.settings.suggested_prompts) if restaurant.settings else []

    def _house_favourites(self, restaurant: Restaurant, items: list[MenuItem], intent: Intent) -> TurnResult | None:
        featured = [i for i in items if i.is_featured and menu_service.is_orderable(i)]
        if not featured:
            return None
        # Photographed favourites first: they make the best first impression.
        featured.sort(key=lambda i: i.image_url is None)
        recs = [
            ScoredItem(item=i, score=0, reasons=["House favourite"], unit_price=menu_service.price_from(i), quantity=1,
                       total=menu_service.price_from(i))
            for i in featured[:4]
        ]
        return TurnResult(
            intent=intent,
            message=(
                f"Here are a few of {_possessive(restaurant.name)} favourites to start with. Or tell me what you're "
                "in the mood for - and a budget, if you have one."
            ),
            recs=recs,
            follow_ups=self._more(3),
            filters=SearchFilters(),
        )

    def _more(self, n: int) -> list[str]:
        """Generic next steps: this restaurant's own suggested prompts."""
        return (getattr(self, "_suggested", None) or ["Recommend a drink", "Something cold", "Show me the menu"])[:n]

    # ----------------------------------------------------------- intents

    def _recommend(self, parsed: ParsedQuery, items: list[MenuItem], last_items: list[MenuItem]) -> TurnResult:
        f = parsed.filters
        if parsed.intent == "cheapest" and f.sort != "price_asc":
            f = f.model_copy(update={"sort": "price_asc"})
        outcome = search(items, f, limit=parsed.limit)
        f = outcome.filters or f  # carried-over constraints may have been set aside
        noun_n = len(outcome.matches)
        qualifier = _qualifier(f)
        lines: list[str] = []
        recs = outcome.matches
        follow_ups: list[str] = []

        if recs:
            top = recs[0]
            if "keywords" in outcome.relaxed:
                lines.append(
                    f"I couldn't find anything matching {_join(['“' + k + '”' for k in f.keywords])} exactly, "
                    f"but here {'is' if noun_n == 1 else 'are'} {noun_n} {_noun(f, noun_n)} "
                    f"{_qualifier(f.model_copy(update={'keywords': []}))}".rstrip() + "."
                )
            elif parsed.intent == "cheapest" or f.sort == "price_asc":
                lines.append(
                    f"The most affordable {_noun(f, 1)} {('' if not qualifier else qualifier + ' ')}right now is the "
                    f"{top.item.name} at {format_inr(top.unit_price)}."
                    + (f" Next up: {_join([s.item.name for s in recs[1:]])}." if len(recs) > 1 else "")
                )
            elif f.sort == "strength_desc":
                strength = f" (strength {top.item.strength}/5)" if top.item.strength else ""
                lines.append(f"The boldest {_noun(f, 1)} on our menu is the {top.item.name}{strength}.")
                if len(recs) > 1:
                    lines.append(f"Also strong: {_join([s.item.name for s in recs[1:]])}.")
            else:
                lines.append(
                    f"Here {'is' if noun_n == 1 else 'are'} {noun_n} {_noun(f, noun_n)} {qualifier}".rstrip() + "."
                )
                lines.append(f"My top pick is the {top.item.name}.")
            if f.party_size > 1 and f.max_price is not None:
                lines.append("Totals are for the whole group, before add-ons.")
        else:
            lines.append(f"I couldn't find any {_noun(f, 2)} {qualifier}".rstrip() + " on the menu right now.")
            if outcome.alternatives:
                recs = outcome.alternatives
                if recs[0].over_budget:
                    lines.append("The closest options are a little above your budget:")
                    follow_ups.append("Any price is fine")
                else:
                    lines.append("Here are the closest matches if you're flexible:")
            else:
                lines.append("Try widening your budget or removing a filter.")
                follow_ups += ["Start over", "Show me the menu"]
        # Only mention unavailable items that would actually have made the list.
        ceiling = max((s.total for s in recs), default=None)
        unavailable = [
            i for i in outcome.unavailable_matches
            if len(outcome.matches) < parsed.limit or (ceiling is not None and quantity_for(i, f.party_size) * menu_service.price_from(i) <= ceiling)
        ]
        if unavailable:
            names = _join([i.name for i in unavailable])
            verb = "is" if len(unavailable) == 1 else "are"
            lines.append(f"({names} would also fit, but {verb} unavailable right now.)")
        if f.exclude_allergens:
            n_unknown = len(outcome.unknown_allergen_items)
            caveat = "I've only included items with allergen information verified by the restaurant"
            if n_unknown:
                caveat += f"; {n_unknown} item{'s' if n_unknown != 1 else ''} with unverified allergen info {'were' if n_unknown != 1 else 'was'} left out"
            lines.append(caveat + ". Please confirm with staff if you have a severe allergy.")

        if recs:
            follow_ups += self._follow_ups_for_results(f, recs)
        return TurnResult(
            intent=parsed.intent, message=" ".join(lines), recs=recs, follow_ups=follow_ups[:3], filters=f
        )

    def _meal_plan(self, parsed: ParsedQuery, items: list[MenuItem]) -> TurnResult:
        f = parsed.filters
        courses = list(f.courses) or ["starter", "main"]
        result = build_plan(items, f, courses)
        lines = [
            PlanLine(
                course=p.course,  # type: ignore[arg-type]
                item=menu_service.serialize_item(p.item),
                variant_id=p.variant.id if p.variant is not None else None,
                variant_name=p.variant.name if p.variant is not None else None,
                quantity=p.quantity,
                unit_price=p.unit_price,
                line_total=p.line_total,
            )
            for p in result.picks
        ]
        plan = MealPlan(
            party_size=result.party,
            budget=result.budget,
            lines=lines,
            course_subtotals=[
                CourseSubtotal(
                    course=c,  # type: ignore[arg-type]
                    items=sum(p.quantity for p in result.picks if p.course == c),
                    subtotal=result.subtotal(c),
                )
                for c in ["starter", "main", "dessert", "drink"]
                if c in result.courses
            ],
            total=result.total,
            per_person=result.per_person,
            remaining=result.remaining,
            within_budget=result.within_budget,
            assumptions=result.assumptions,
        )
        message = describe_plan(result)
        follow_ups: list[str] = []
        remaining = result.remaining
        if result.within_budget and remaining is not None and "dessert" not in result.courses:
            desserts = sorted(menu_service.price_from(i) for i in items if "dessert" in courses_of(i) and menu_service.is_orderable(i))
            need = portions("dessert", result.party)
            if len(desserts) >= need and sum(desserts[:need]) <= remaining:
                message += f" That's enough left over for {need} dessert{'s' if need != 1 else ''}."
            follow_ups.append("Add desserts")
        elif "dessert" not in result.courses:
            follow_ups.append("Add desserts")
        if result.budget is not None and not result.within_budget:
            follow_ups.append(f"Make it ₹{int((result.total + 99) // 100 * 100)}")
        if "drink" not in result.courses:
            follow_ups.append("Add drinks")
        if "main" in result.courses and not f.keywords:
            follow_ups.append("Only pasta mains")
        return TurnResult(intent="meal_plan", message=message, plan=plan, follow_ups=follow_ups[:3], filters=f)

    def _follow_ups_for_results(self, f: SearchFilters, recs: list[ScoredItem]) -> list[str]:
        out: list[str] = []
        types = set(f.item_types)
        is_drinks = types == {"beverage"} or f.contains_coffee is not None
        if is_drinks and f.temperature != "cold":
            out.append("Something cold instead?")
        elif is_drinks and f.temperature == "cold":
            out.append("Something hot instead?")
        if len(recs) >= 2:
            out.append(f"Compare the {_short(recs[0].item.name)} and {_short(recs[1].item.name)}")
        out.append(f"What pairs well with the {_short(recs[0].item.name)}?")
        if not f.dietary and getattr(self, "_has_verified_vegan", True):
            out.append("Only vegan options")
        return out

    def _compare(self, mentioned, last_items, items, parsed: ParsedQuery, f: SearchFilters) -> TurnResult:
        targets: list[MenuItem] = list(mentioned)
        if len(targets) < 2:
            pool = list(last_items)
            if f.item_types:
                pool = [i for i in pool if i.item_type in f.item_types] or pool
            for it in pool:
                if it not in targets:
                    targets.append(it)
                if len(targets) == 2:
                    break
        targets = targets[:3]
        if len(targets) < 2:
            options = ["Compare the Cappuccino and Flat White", "Compare the Iced Americano and Cold Brew"]
            return TurnResult(
                intent="compare",
                message="Which two items would you like me to compare? Tell me their names, or ask for recommendations first.",
                clarification=Clarification(question="Which items should I compare?", options=options),
                follow_ups=options,
                filters=f,
            )

        def tri(v: bool | None) -> str:
            return "Not verified" if v is None else ("Yes" if v else "No")

        def allergen_str(i: MenuItem) -> str:
            if i.allergens_status != "verified":
                return "Not verified"
            return ", ".join(i.allergens or []) or "None listed"

        rows = [
            ComparisonRow(
                label="Price",
                values=[
                    ("From " if i.variants else "") + format_inr(menu_service.price_from(i)) for i in targets
                ],
            ),
            ComparisonRow(label="Category", values=[i.category.name for i in targets]),
            ComparisonRow(
                label="Served",
                values=[{"hot": "Hot", "cold": "Cold"}.get(i.temperature or "", "—") for i in targets],
            ),
            ComparisonRow(label="Strength", values=[f"{i.strength}/5" if i.strength else "—" for i in targets]),
            ComparisonRow(label="Sweetness", values=[f"{i.sweetness}/5" if i.sweetness else "—" for i in targets]),
            ComparisonRow(
                label="Caffeine", values=[(i.caffeine_level or "Not specified").capitalize() for i in targets]
            ),
            ComparisonRow(label="Vegetarian", values=[tri(i.is_vegetarian) for i in targets]),
            ComparisonRow(label="Vegan", values=[tri(i.is_vegan) for i in targets]),
            ComparisonRow(label="Allergens", values=[allergen_str(i) for i in targets]),
            ComparisonRow(
                label="Available", values=["Yes" if menu_service.is_orderable(i) else "No" for i in targets]
            ),
        ]
        a, b = targets[0], targets[1]
        pa, pb = menu_service.price_from(a), menu_service.price_from(b)
        sentences = []
        diff = abs(pa - pb)
        if diff == 0:
            sentences.append(f"The {a.name} and {b.name} both start at {format_inr(pa)}.")
        else:
            cheaper, pricier = (a, b) if pa < pb else (b, a)
            sentences.append(f"The {cheaper.name} is {format_inr(diff)} cheaper than the {pricier.name}.")
        if a.strength and b.strength and a.strength != b.strength:
            stronger = a if a.strength > b.strength else b
            sentences.append(f"The {stronger.name} is the stronger of the two ({stronger.strength}/5).")
        if a.sweetness and b.sweetness and a.sweetness != b.sweetness:
            sweeter = a if a.sweetness > b.sweetness else b
            sentences.append(f"The {sweeter.name} is sweeter.")
        if a.temperature and b.temperature and a.temperature != b.temperature:
            sentences.append(f"The {a.name} is served {a.temperature} and the {b.name} {b.temperature}.")
        recs = [
            ScoredItem(item=i, score=0, reasons=[], unit_price=menu_service.price_from(i), quantity=1, total=menu_service.price_from(i))
            for i in targets
        ]
        return TurnResult(
            intent="compare",
            message=" ".join(sentences),
            recs=recs,
            comparison=Comparison(item_ids=[i.id for i in targets], item_names=[i.name for i in targets], rows=rows),
            follow_ups=[f"What pairs well with the {_short(a.name)}?", f"Is the {_short(b.name)} vegan?"],
            filters=f,
            extra_amounts={diff},
        )

    def _pairing(self, mentioned, last_items, cart_items, items, parsed: ParsedQuery, f: SearchFilters) -> TurnResult:
        anchor = mentioned[0] if mentioned else None
        if anchor is None and cart_items:
            anchor = cart_items[-1]
        if anchor is None and last_items and parsed.refers_to_previous:
            anchor = last_items[0]
        if anchor is None:
            options = ["What pairs well with a cappuccino?", "What goes with the cold brew?"]
            return TurnResult(
                intent="pairing",
                message="Happy to suggest a pairing! Which drink or dish would you like it to go with?",
                clarification=Clarification(question="Pair with which item?", options=options),
                follow_ups=options,
                filters=f,
            )
        types = [t for t in f.item_types]
        # Curries and dals are eaten with bread: suggest those, not a drink.
        with_bread = not types and bool(set(anchor.tags or []) & GRAVY_TAGS) and any(
            "bread" in (i.tags or []) and menu_service.is_orderable(i) for i in items
        )
        if with_bread:
            types = ["food"]
        elif not types or types == [anchor.item_type]:
            types = ["dessert", "food"] if anchor.item_type == "beverage" else ["beverage"]
        pf = SearchFilters(
            item_types=types,  # type: ignore[arg-type]
            max_price=f.max_price,
            min_price=f.min_price,
            dietary=f.dietary,
            exclude_allergens=f.exclude_allergens,
            party_size=f.party_size,
            contains_coffee=f.contains_coffee if types == ["beverage"] else None,
            temperature=f.temperature if types == ["beverage"] else None,
            tags_any=["bread"] if with_bread else [],
        )
        anchor_pairs = set(anchor.pairs_with or [])
        anchor_flavors = set(anchor.flavor_tags or [])
        scored: list[tuple[float, ScoredItem]] = []
        for it in items:
            if it.id == anchor.id or not matches(it, pf):
                continue
            shared = sorted(anchor_pairs & set(it.flavor_tags or []))
            back = set(it.pairs_with or []) & anchor_flavors
            score = 2 * len(shared) + len(back) + (0.5 if it.is_featured else 0)
            reasons = []
            if shared:
                reasons.append(f"{_join(shared).capitalize()} notes complement the {_short(anchor.name)}")
            unit = menu_service.price_from(it)
            qty = quantity_for(it, pf.party_size)
            if pf.max_price is not None:
                reasons.append(f"{format_inr(unit * qty)} - within your {format_inr(pf.max_price)} budget")
            if it.is_featured:
                reasons.append("House favourite")
            if not reasons and it.flavor_tags:
                reasons.append(f"{_join(list(it.flavor_tags[:2])).capitalize()} notes")
            scored.append(
                (score, ScoredItem(item=it, score=score, reasons=reasons[:3], unit_price=unit, quantity=qty, total=to_money(unit * qty)))
            )
        scored.sort(key=lambda t: (-t[0], t[1].total))
        recs = [s for score, s in scored if score > 0][: parsed.limit] or [s for _, s in scored][: min(3, parsed.limit)]
        type_word = {"dessert": "desserts", "food": "bites", "beverage": "drinks"}
        wanted = "breads" if with_bread else _join([type_word[t] for t in types])
        if recs:
            msg = f"Lovely choice. These {wanted} go well with the {anchor.name}"
            if pf.max_price is not None:
                msg += f" and fit your {format_inr(pf.max_price)} budget"
            msg += f". Try the {recs[0].item.name} first."
        else:
            msg = f"I couldn't find {wanted} that match your filters to pair with the {anchor.name}. Try removing a filter."
        return TurnResult(
            intent="pairing",
            message=msg,
            recs=recs,
            follow_ups=(
                [f"Compare the {_short(recs[0].item.name)} and {_short(recs[1].item.name)}"] if len(recs) > 1 else []
            )
            + (["Something cold instead?"] if "beverage" in types else self._more(1)),
            filters=pf,
        )

    def _item_info(self, restaurant, targets, items, parsed: ParsedQuery, message: str, f: SearchFilters) -> TurnResult:
        if not targets:
            return TurnResult(
                intent="item_info",
                message="Which item would you like to know about? Tell me its name and I'll check the menu details.",
                clarification=Clarification(question="Which item?", options=["Tell me about the Mocha", "Is the brownie vegan?"]),
                filters=f,
            )
        it = targets[0]
        topic = parsed.info_topic or "general"
        price_text = ("from " if it.variants else "") + format_inr(menu_service.price_from(it))
        available = menu_service.is_orderable(it)
        disclaimer = restaurant.settings.allergen_disclaimer if restaurant.settings else ""
        sentences: list[str] = []
        norm = normalize(message)

        if topic == "allergens":
            asked = [a for a, words in ALLERGEN_WORDS.items() if any(f" {w} " in f" {norm} " for w in words)]
            if it.allergens_status != "verified":
                sentences.append(
                    f"The restaurant hasn't verified allergen information for the {it.name}, so I can't confirm "
                    + (f"whether it contains {_join(asked)}." if asked else "what it contains.")
                )
                sentences.append("Please check with our staff before ordering if you have an allergy.")
            else:
                listed = [a.lower() for a in it.allergens or []]
                if asked:
                    present = [a for a in asked if a in listed]
                    absent = [a for a in asked if a not in listed]
                    if present:
                        sentences.append(f"Yes - the {it.name} contains {_join(present)} according to the restaurant's verified allergen list.")
                    if absent:
                        sentences.append(
                            f"{_join(absent).capitalize()} {'is' if len(absent) == 1 else 'are'} not on the {it.name}'s verified allergen list."
                        )
                else:
                    sentences.append(
                        f"The restaurant's verified allergen list for the {it.name}: {', '.join(listed)}."
                        if listed
                        else f"The restaurant lists no major allergens for the {it.name}."
                    )
                if disclaimer:
                    sentences.append(disclaimer)
        elif topic == "dietary":
            veg, vegan = it.is_vegetarian, it.is_vegan
            if vegan is True:
                sentences.append(f"Yes - the {it.name} is verified vegan by the restaurant.")
            elif "vegan" in norm.split():
                if vegan is False:
                    sentences.append(f"No - the {it.name} is not vegan.")
                else:
                    sentences.append(f"The restaurant hasn't verified whether the {it.name} is vegan.")
            if veg is True and vegan is not True:
                sentences.append(f"It is verified vegetarian.")
            elif veg is False:
                sentences.append(f"The {it.name} is not vegetarian.")
            elif veg is None and vegan is not True:
                sentences.append(f"The restaurant hasn't verified whether the {it.name} is vegetarian.")
        elif topic == "ingredients":
            ings = it.ingredients or []
            if it.ingredients_status == "verified" and ings:
                sentences.append(f"The {it.name} is made with {_join(ings)}.")
            elif it.ingredients_status == "partial" and ings:
                sentences.append(f"The {it.name} includes {_join(ings)} - that's not a complete ingredient list.")
            else:
                sentences.append(f"The restaurant hasn't published a verified ingredient list for the {it.name}.")
            if it.description:
                sentences.append(f"Menu description: {it.description}")
        elif topic == "caffeine":
            if it.caffeine_level:
                sentences.append(f"The {it.name} has {it.caffeine_level} caffeine" + (f" and a strength of {it.strength}/5." if it.strength else "."))
            else:
                sentences.append(f"The restaurant hasn't listed caffeine information for the {it.name}.")
        elif topic == "availability":
            pass  # answered below
        elif topic == "price":
            if it.variants:
                opts = ", ".join(f"{v.name} {format_inr(v.price)}" for v in it.variants if v.is_available)
                sentences.append(f"The {it.name} comes in: {opts}.")
            else:
                sentences.append(f"The {it.name} is {format_inr(it.price)}.")
        else:
            sentences.append(f"The {it.name} is {price_text}." + (f" {it.description}" if it.description else ""))

        if topic == "availability" or not available:
            if available:
                sentences.append(f"Good news - the {it.name} is available right now.")
            else:
                sentences.append(f"Sorry, the {it.name} is currently unavailable.")

        recs = [ScoredItem(item=it, score=0, reasons=[], unit_price=menu_service.price_from(it), quantity=1, total=menu_service.price_from(it))]
        if not available:
            similar = [
                i for i in items
                if i.id != it.id and i.category_id == it.category_id and menu_service.is_orderable(i)
            ]
            similar.sort(key=lambda i: abs(menu_service.price_from(i) - menu_service.price_from(it)))
            if similar:
                sentences.append(f"Similar options you can order: {_join([i.name for i in similar[:2]])}.")
                for s in similar[:2]:
                    recs.append(ScoredItem(item=s, score=0, reasons=["Similar and available"], unit_price=menu_service.price_from(s), quantity=1, total=menu_service.price_from(s)))
        return TurnResult(
            intent="item_info",
            message=" ".join(sentences),
            recs=recs,
            follow_ups=[f"What pairs well with the {_short(it.name)}?", *self._more(2)],
            filters=f,
        )

    def _menu_overview(self, restaurant: Restaurant, items: list[MenuItem]) -> TurnResult:
        by_cat: dict[str, list[MenuItem]] = {}
        for it in items:
            if menu_service.is_orderable(it):
                by_cat.setdefault(it.category.name, []).append(it)
        parts = []
        amounts: set[Decimal] = set()
        for name, its in by_cat.items():
            prices = [menu_service.price_from(i) for i in its]
            amounts |= {min(prices), max(prices)}
            lo, hi = min(prices), max(prices)
            parts.append(f"{name} ({format_inr(lo)})" if lo == hi else f"{name} ({format_inr(lo)}–{format_inr(hi)})")
        featured = [i for i in items if i.is_featured and menu_service.is_orderable(i)][:4]
        recs = [
            ScoredItem(item=i, score=0, reasons=["House favourite"], unit_price=menu_service.price_from(i), quantity=1, total=menu_service.price_from(i))
            for i in featured
        ]
        return TurnResult(
            intent="menu_overview",
            message=f"Here's what we serve: {_join(parts)}. A few house favourites are below.",
            recs=recs,
            follow_ups=self._more(3),
            extra_amounts=amounts,
        )

    def _order_help(self, restaurant: Restaurant, cart_items: list[MenuItem], f: SearchFilters) -> TurnResult:
        ordering = restaurant.settings.ordering_enabled if restaurant.settings else False
        if ordering:
            msg = "Open your cart and tap Checkout - I'll re-check prices and availability before your order is sent."
        else:
            msg = (
                "I can't place, pay for or track orders - online ordering isn't connected in this demo yet. "
                "You can build your cart here; Checkout will verify prices and availability, then show your order "
                "for you to place at the counter."
            )
        if cart_items:
            msg += f" Your cart currently has {len(cart_items)} item{'s' if len(cart_items) != 1 else ''}."
        return TurnResult(intent="order_help", message=msg, follow_ups=["What pairs well with my order?", "Recommend a dessert"], filters=f)
