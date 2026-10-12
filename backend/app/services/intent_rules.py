"""Deterministic natural-language parser used in demo mode and as the LLM fallback.

It turns a customer message (plus the previous turn's constraints) into a
validated ``ParsedQuery``. It is intentionally conservative: anything it does
not recognise is ignored rather than guessed.
"""

from __future__ import annotations

import re
from decimal import Decimal

from app.models import MenuItem
from app.money import to_money
from app.schemas.assistant import InfoTopic, Intent, ParsedQuery, SearchFilters
from app.services.matching import contains_phrase, find_mentions_with_residual, normalize

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}

# Words that map to structured filters, so they must not also become keywords.
CONTROL_WORDS = {
    "coffee", "coffees", "espresso based", "cold", "hot", "iced", "warm", "sweet", "strong", "drink", "drinks",
    "tea", "teas", "food", "dessert", "desserts", "vegan", "vegetarian", "veg", "milk", "shareable",
    "beverage", "snack", "meal", "chilled", "bold", "mild", "light", "shake", "cooler",
}

REFINEMENT_STARTERS = (
    "something", "make it", "what about", "how about", "and ", "only", "but ", "any ", "anything",
    "cheaper", "less", "more", "with ", "without", "in ", "under", "below", "maybe", "preferably",
    "also", "now ", "ok ", "okay", "iced", "cold", "hot", "not ", "no ", "within", "prefer",
)

SUBJECT_FIELDS = ("item_types", "contains_coffee", "tags_any", "keywords", "caffeine_free")
CARRY_OVER_FIELDS = ("max_price", "min_price", "party_size", "dietary", "exclude_allergens")


def _has(text: str, *patterns: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def _amount(s: str) -> Decimal:
    return to_money(s.replace(",", ""))


def extract_prices(raw: str) -> dict:
    """Budget constraints from the raw (lower-cased) message."""
    text = raw.lower().replace("₹", " rs ").replace("inr", " rs ").replace("rupees", " rs ")
    text = re.sub(r"\s+", " ", text)
    out: dict = {}
    if _has(text, r"\bno budget\b", r"\bany price\b", r"price (?:doesn'?t|does not) matter", r"\b(?:forget|remove|ignore|drop) (?:the |my )?budget\b", r"\bany budget\b"):
        out["max_price"] = None
        out["min_price"] = None
        return out
    num = r"(\d{1,3}(?:,\d{3})+|\d{1,6})(?!\d)"
    rng = re.search(rf"between (?:rs\.? ?)?{num} ?(?:rs\.?)? ?(?:and|to|-) ?(?:rs\.? ?)?{num}", text) or re.search(
        rf"\brs\.? ?{num} ?(?:-|to) ?(?:rs\.? ?)?{num}", text
    )
    if rng:
        out["min_price"], out["max_price"] = _amount(rng.group(1)), _amount(rng.group(2))
        return out
    ceiling = re.search(
        rf"(?:(?:nothing|not|no|never|don['’ ]?t want to spend|don['’ ]?t spend|won['’ ]?t spend|can['’ ]?t spend)\s+"
        rf"(?:anything\s+)?(?:over|above|more than|beyond|exceeding)|"
        rf"under|below|less than|lesser than|within|up ?to|upto|max(?:imum)?|at most|no more than|not more than|"
        rf"cheaper than|budget(?: of| is)?|<=?)\s*(?:rs\.?\s*)?{num}",
        text,
    ) or re.search(rf"{num}\s*(?:rs\.?|/-)?\s*(?:or less|or under|max|budget)\b", text)
    if ceiling:
        out["max_price"] = _amount(ceiling.group(1))
    for floor in re.finditer(rf"\b(?:over|above|more than|at least|minimum|min)\s*(?:rs\.?\s*)?{num}", text):
        # Skip "over" inside a ceiling phrase such as "nothing over 250".
        if ceiling and ceiling.start() <= floor.start() < ceiling.end():
            continue
        out["min_price"] = _amount(floor.group(1))
        break
    if "max_price" not in out and "min_price" not in out:
        m = re.search(rf"\brs\.?\s*{num}", text) or re.search(rf"{num}\s*rs\b", text)
        if m:
            out["max_price"] = _amount(m.group(1))
    return out


def extract_party_size(text: str) -> int | None:
    nums = "|".join(list(NUMBER_WORDS) + [str(i) for i in range(2, 9)])
    m = re.search(rf"\bfor (?:the )?({nums})\b(?! ?(?:rs|rupees|₹|inr|\d))", text) or re.search(
        rf"\b({nums}) (?:people|persons|ppl|of us|friends|pax|adults|guests)\b", text
    )
    if m:
        v = m.group(1)
        return NUMBER_WORDS.get(v) or int(v)
    if _has(text, r"\bcouple\b", r"\bdate\b", r"\bme and my (?:friend|partner|wife|husband|colleague|mom|dad|sister|brother)\b", r"\bfor us both\b"):
        return 2
    return None


def build_vocabulary(items: list[MenuItem]) -> set[str]:
    vocab: set[str] = set()
    for it in items:
        for w in list(it.flavor_tags or []) + list(it.search_keywords or []) + list(it.tags or []):
            w = normalize(w)
            if w and w not in CONTROL_WORDS and len(w) > 2:
                vocab.add(w)
    return vocab


def _info_topic(text: str) -> InfoTopic | None:
    if _has(text, r"allerg", r"\bnuts?\b", r"peanut", r"gluten", r"dairy", r"lactose", r"\begg", r"\bsoy\b", r"sesame", r"\bcontain"):
        return "allergens"
    if _has(text, r"\bvegan\b", r"vegetarian", r"\bveg\b", r"plant based"):
        return "dietary"
    if _has(text, r"ingredient", r"what s in", r"what is in", r"whats in", r"made (?:with|of|from)", r"recipe", r"\bin it\b"):
        return "ingredients"
    if _has(text, r"available", r"in stock", r"sold out", r"\bcan i (?:get|order|have)\b", r"do you have", r"is there"):
        return "availability"
    if _has(text, r"how much", r"\bprice\b", r"\bcost"):
        return "price"
    if _has(text, r"caffein", r"decaf", r"how strong", r"strength"):
        return "caffeine"
    if _has(text, r"^(?:what|tell|describe|how|is|does|explain)"):
        return "general"
    return None


def parse_message(
    message: str,
    items: list[MenuItem],
    previous: SearchFilters | None = None,
    last_item_prices: list[Decimal] | None = None,
) -> ParsedQuery:
    raw = message.strip()
    mentions, ambiguous, residual = find_mentions_with_residual(raw, items)
    text = residual  # normalised, item names removed
    full = normalize(raw)

    delta: dict = {}
    reset = _has(full, r"\bstart over\b", r"\breset\b", r"\bforget (?:that|it|everything|all)\b", r"\bnew search\b", r"\bclear (?:filters|everything)\b")

    # ---- prices / party ---------------------------------------------------
    delta.update(extract_prices(raw))
    party = extract_party_size(full)
    if party:
        delta["party_size"] = party

    # ---- coffee / drink types --------------------------------------------
    no_coffee = _has(text, r"\b(?:without|no|non|not|zero|skip|avoid)[ -]?coffee\b", r"\bcoffee[ -]?free\b", r"\bother than coffee\b", r"\bisn ?t coffee\b", r"\bnot a coffee\b")
    caffeine_free = _has(text, r"caffeine[ -]?free", r"\bdecaf", r"\b(?:no|without|zero) caffeine\b", r"\bnon caffeinated\b")
    if no_coffee:
        delta["contains_coffee"] = False
        delta["item_types"] = ["beverage"]
    elif _has(text, r"\bcoffees?\b", r"\bespresso based\b", r"\bcaffeine fix\b", r"\bcuppa joe\b"):
        delta["contains_coffee"] = True
        delta["item_types"] = ["beverage"]
    if caffeine_free:
        delta["caffeine_free"] = True
        delta["item_types"] = ["beverage"]

    tags: list[str] = []
    if _has(text, r"\btea\b", r"\bteas\b", r"\bchai\b", r"\binfusions?\b", r"\btisane"):
        tags.append("tea")
    if _has(text, r"\bshakes?\b", r"milkshake", r"smoothie"):
        tags.append("shake")
    if _has(text, r"\bcoolers?\b", r"\bjuice", r"lemonade", r"mocktail"):
        tags.append("cooler")
    if tags:
        delta["tags_any"] = tags
        delta.setdefault("item_types", ["beverage"])

    types: list[str] = list(delta.get("item_types", []))
    if _has(text, r"\bdrinks?\b", r"\bbeverages?\b", r"\bsip\b", r"\bthirsty\b", r"something to drink"):
        types.append("beverage")
    if _has(text, r"\bdesserts?\b", r"\bsweet treat", r"\bcakes?\b", r"\bpastr(?:y|ies)\b", r"\bbakes?\b", r"\btreats?\b", r"something sweet to eat"):
        types.append("dessert")
    if _has(text, r"\bfood\b", r"\beat\b", r"\bhungry\b", r"\bsnacks?\b", r"\bbites?\b", r"\bmeals?\b", r"\blunch\b", r"\bbrunch\b", r"\bsavou?ry\b", r"\bsandwich", r"\bdinner\b"):
        types.append("food")
    if types:
        delta["item_types"] = sorted(set(types), key=["beverage", "food", "dessert"].index)

    # ---- temperature / taste ---------------------------------------------
    if _has(text, r"\bcold\b", r"\biced\b", r"\bice\b", r"\bchilled\b", r"\bcool\b", r"refreshing", r"\bfrappe", r"\bsummer"):
        delta["temperature"] = "cold"
    elif _has(text, r"\bhot\b", r"\bwarm\b", r"steaming", r"\bcozy\b", r"\bcosy\b"):
        delta["temperature"] = "hot"

    if _has(text, r"not (?:too |very |that |overly )?sweet", r"less sweet", r"low sugar", r"less sugar", r"unsweetened", r"no sugar", r"mildly sweet", r"not sugary", r"\bnot too sugary"):
        delta["max_sweetness"] = 2
        delta["min_sweetness"] = None
    elif _has(text, r"\bsweet\b", r"sweet tooth", r"indulgent", r"\bsugary\b") and "dessert" not in delta.get("item_types", []):
        delta["min_sweetness"] = 3
        delta["max_sweetness"] = None

    sort = "relevance"
    strongest = _has(text, r"strongest", r"most intense", r"boldest", r"most caffeine", r"highest caffeine")
    if strongest:
        sort = "strength_desc"
        delta.setdefault("contains_coffee", True)
        delta.setdefault("item_types", ["beverage"])
    elif _has(text, r"\bstrong\b", r"\bbold\b", r"\bintense\b", r"\bkick\b", r"wake me up", r"\bpunchy\b"):
        delta["min_strength"] = 4
        delta["max_strength"] = None
        delta.setdefault("contains_coffee", True)
        delta.setdefault("item_types", ["beverage"])
    elif _has(text, r"\bmild\b", r"\bgentle\b", r"not (?:too )?strong", r"\bsmooth\b"):
        delta["max_strength"] = 2
        delta["min_strength"] = None

    cheapest = _has(text, r"cheapest", r"lowest pric", r"least expensive", r"most affordable", r"lowest cost")
    if cheapest or _has(text, r"\bcheap\b", r"budget friendly", r"affordable", r"inexpensive", r"pocket friendly"):
        sort = "price_asc"
    elif _has(text, r"most expensive", r"priciest", r"premium", r"fanciest"):
        sort = "price_desc"

    # "cheaper" refines against what was just shown.
    if _has(text, r"\bcheaper\b", r"less expensive", r"lower price") and "max_price" not in delta:
        if last_item_prices:
            delta["max_price"] = to_money(min(last_item_prices) - Decimal("0.01"))
        else:
            sort = "price_asc"

    # ---- dietary / allergens ---------------------------------------------
    if _has(full, r"\bvegan\b", r"plant based"):
        delta["dietary"] = ["vegan"]
    elif _has(full, r"(?<!non )\bvegetarian\b", r"(?<!non )\bveg\b", r"(?<!non )\bveggie\b") and not _has(full, r"non ?veg"):
        delta["dietary"] = ["vegetarian"]
    allergens: list[str] = []
    if _has(full, r"nut[ -]?free", r"(?:no|without|avoid|allergic to|allergy to) (?:any )?(?:tree )?nuts?\b", r"\bnut allerg"):
        allergens += ["tree nuts", "peanuts"]
    if _has(full, r"peanut[ -]?free", r"(?:no|without|allergic to) peanuts?", r"peanut allerg"):
        allergens.append("peanuts")
    if _has(full, r"dairy[ -]?free", r"lactose", r"(?:no|without|allergic to) (?:dairy|milk)", r"dairy allerg", r"milk allerg"):
        allergens.append("milk")
    if _has(full, r"gluten[ -]?free", r"(?:no|without|allergic to) gluten", r"\bceliac\b", r"coeliac"):
        allergens.append("gluten")
    if _has(full, r"egg[ -]?(?:free|less)", r"(?:no|without|allergic to) eggs?\b", r"egg allerg"):
        allergens.append("egg")
    if _has(full, r"soy[ -]?free", r"(?:no|without|allergic to) soy"):
        allergens.append("soy")
    if allergens:
        delta["exclude_allergens"] = allergens

    # ---- keywords from the menu's own vocabulary ---------------------------
    vocab = build_vocabulary(items)
    keywords = [w for w in sorted(vocab, key=len, reverse=True) if contains_phrase(text, w)]
    keywords += [a for a in ambiguous if a not in CONTROL_WORDS]
    # Avoid keywords that are substrings of longer keywords already found.
    deduped: list[str] = []
    for k in keywords:
        if not any(k != o and k in o for o in keywords) and k not in deduped:
            deduped.append(k)
    if deduped:
        delta["keywords"] = deduped[:5]

    # ---- intent -------------------------------------------------------------
    refers_prev = _has(full, r"\bthese\b", r"\bthose\b", r"\bboth\b", r"\bthem\b", r"\bthe two\b", r"\bthe first\b", r"\bthe second\b", r"\bthe top\b")
    intent: Intent
    info_topic: InfoTopic | None = None
    limit = 4
    if _has(full, r"^(?:hi|hello|hey|hiya|good (?:morning|afternoon|evening)|namaste|yo|thanks?|thank you)(?: there)?[ !.]*$") or (reset and len(full.split()) <= 4):
        intent = "greeting"
    elif _has(full, r"\bcompare\b", r"\bvs\b", r"\bversus\b", r"difference between", r"which is better", r"which one is better", r"which (?:one|of these|of them) should"):
        intent = "compare"
    elif _has(full, r"\bpairs?\b", r"\bpairing\b", r"goes? (?:well )?with", r"\bwith my\b", r"along ?(?:side|with)", r"complement", r"to have with", r"to go with", r"accompan"):
        intent = "pairing"
    elif _has(full, r"(?:place|confirm|submit|track|cancel) (?:my |the |an |a )?order", r"\bcheckout\b", r"\bcheck out\b", r"\bpay(?:ment)?\b", r"order status", r"\bdeliver", r"how (?:do|can) i order"):
        intent = "order_help"
    elif mentions and (_info_topic(full) is not None) and not _has(full, r"\brecommend", r"\bsuggest"):
        intent = "item_info"
        info_topic = _info_topic(full)
    elif (
        previous is not None
        and _has(full, r"^(?:is|does|do|has|can|what s in|whats in|what is in|how much is|how strong is)\s+(?:it|that|this|the first one|the top one)\b")
        and _info_topic(full) is not None
    ):
        intent = "item_info"
        info_topic = _info_topic(full)
        refers_prev = True
    elif cheapest:
        intent = "cheapest"
        limit = 3
    elif _has(full, r"\bmenu\b", r"what do you (?:have|serve|sell)", r"categor", r"what(?: s| is) (?:on|available)") and not (
        set(delta) - {"max_price", "min_price", "party_size"}
    ) and not delta.get("max_price"):
        intent = "menu_overview"
    elif mentions and not (set(delta) - {"party_size"}) and not _has(full, r"\bsimilar\b", r"\blike\b"):
        intent = "item_info"
        info_topic = "general"
    else:
        intent = "recommend"
        if strongest:
            limit = 3

    # ---- merge with previous constraints ----------------------------------
    explicit_unset = {k for k, v in delta.items() if v is None}
    delta_clean = {k: v for k, v in delta.items() if v is not None}
    if reset or previous is None or intent in ("greeting", "menu_overview"):
        base: dict = {}
    else:
        prev = previous.model_dump()
        has_subject = any(k in delta_clean for k in SUBJECT_FIELDS)
        starts_refine = full.startswith(REFINEMENT_STARTERS) or len(full.split()) <= 4
        same_subject = has_subject and all(
            prev.get(k) == delta_clean.get(k) for k in SUBJECT_FIELDS if k in delta_clean
        )
        if intent in ("item_info", "compare", "order_help", "off_topic"):
            base = prev
        elif (not has_subject and starts_refine) or same_subject:
            base = prev  # refinement: keep everything, apply the delta
        else:
            # New subject: keep budget/party/dietary/allergen constraints only.
            base = {k: prev[k] for k in CARRY_OVER_FIELDS}
        base.pop("sort", None)
    merged = {**base, **delta_clean}
    for k in explicit_unset:
        merged[k] = None
    merged["sort"] = sort
    filters = SearchFilters.model_validate(merged)

    if intent == "recommend" and filters.is_empty() and not mentions and previous is None and not refers_prev:
        # Nothing we could act on.
        if not _has(full, r"recommend", r"suggest", r"surprise", r"popular", r"best", r"favou?rite", r"something", r"anything", r"what should", r"what do you"):
            intent = "off_topic" if len(full.split()) > 2 else "clarify"

    return ParsedQuery(
        intent=intent,
        filters=filters,
        mentioned_items=[m.name for m in mentions],
        refers_to_previous=refers_prev,
        info_topic=info_topic,
        limit=limit,
    )
