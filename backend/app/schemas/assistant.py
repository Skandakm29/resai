from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.money import to_money
from app.schemas.menu import MenuItemOut

ItemType = Literal["beverage", "food", "dessert"]
Course = Literal["starter", "main", "dessert", "drink"]
Intent = Literal[
    "recommend",  # open-ended suggestions with constraints
    "cheapest",  # lowest-priced options
    "meal_plan",  # a combination of dishes across courses for a group/budget
    "compare",  # compare two or more specific items
    "pairing",  # what goes with an anchor item
    "item_info",  # question about a specific item (allergens, vegan, availability...)
    "menu_overview",  # what's on the menu / categories
    "greeting",
    "order_help",  # checkout / placing orders / payments
    "off_topic",
    "clarify",  # the request is too ambiguous to act on
]
InfoTopic = Literal["allergens", "dietary", "ingredients", "availability", "price", "caffeine", "general"]
SortKey = Literal["relevance", "price_asc", "price_desc", "strength_desc"]

KNOWN_ALLERGENS = ("milk", "egg", "gluten", "tree nuts", "peanuts", "soy", "sesame", "coconut")


class SearchFilters(BaseModel):
    """Structured search criteria. Applied deterministically by the backend."""

    item_types: list[ItemType] = Field(default_factory=list)
    courses: list[Course] = Field(default_factory=list)
    contains_coffee: bool | None = None
    temperature: Literal["hot", "cold"] | None = None
    tags_any: list[str] = Field(default_factory=list, max_length=10)
    keywords: list[str] = Field(default_factory=list, max_length=10)
    max_price: Decimal | None = Field(default=None, ge=0, le=100000)
    min_price: Decimal | None = Field(default=None, ge=0, le=100000)
    party_size: int = Field(default=1, ge=1, le=20)
    dietary: list[Literal["vegetarian", "vegan"]] = Field(default_factory=list)
    exclude_allergens: list[str] = Field(default_factory=list, max_length=8)
    caffeine_free: bool = False
    max_sweetness: int | None = Field(default=None, ge=1, le=5)
    min_sweetness: int | None = Field(default=None, ge=1, le=5)
    min_strength: int | None = Field(default=None, ge=1, le=5)
    max_strength: int | None = Field(default=None, ge=1, le=5)
    sort: SortKey = "relevance"
    include_unavailable: bool = False

    @field_validator("max_price", "min_price", mode="before")
    @classmethod
    def _money(cls, v):
        return None if v is None else to_money(v)

    @field_validator("tags_any", "keywords", mode="after")
    @classmethod
    def _clean_words(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for w in v:
            w = w.strip().lower()[:40]
            if w and w not in out:
                out.append(w)
        return out

    @field_validator("exclude_allergens", mode="after")
    @classmethod
    def _allergens(cls, v: list[str]) -> list[str]:
        out = []
        for a in v:
            a = a.strip().lower()
            a = {"nuts": "tree nuts", "nut": "tree nuts", "dairy": "milk", "eggs": "egg", "peanut": "peanuts"}.get(a, a)
            if a in KNOWN_ALLERGENS and a not in out:
                out.append(a)
        return out

    @model_validator(mode="after")
    def _ranges(self):
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            self.min_price, self.max_price = self.max_price, self.min_price
        if self.min_strength and self.max_strength and self.min_strength > self.max_strength:
            self.max_strength = None
        if self.min_sweetness and self.max_sweetness and self.min_sweetness > self.max_sweetness:
            self.min_sweetness = None
        if "vegan" in self.dietary and "vegetarian" in self.dietary:
            self.dietary = ["vegan"]
        return self

    def is_empty(self) -> bool:
        return self == SearchFilters()


class ParsedQuery(BaseModel):
    """Output of intent parsing (rules or LLM). Validated before use."""

    intent: Intent
    filters: SearchFilters = Field(default_factory=SearchFilters)
    # Free-text names of menu items the customer referred to. Resolved against
    # the real menu by the backend; unknown names are discarded.
    mentioned_items: list[str] = Field(default_factory=list, max_length=6)
    # True when the customer refers to previously shown items ("these two").
    refers_to_previous: bool = False
    info_topic: InfoTopic | None = None
    limit: int = Field(default=4, ge=1, le=6)


# ---- API payloads ---------------------------------------------------------


class ChatHistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class CartContextLine(BaseModel):
    item_id: UUID
    quantity: int = Field(default=1, ge=1, le=50)


class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    message: str = Field(min_length=1, max_length=500)
    # Only used when the server has no record of the conversation (e.g. it
    # expired). The server-side transcript is preferred when it exists.
    history: list[ChatHistoryTurn] = Field(default_factory=list, max_length=20)
    cart: list[CartContextLine] = Field(default_factory=list, max_length=50)

    @field_validator("message")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message must not be blank")
        return v


class Recommendation(BaseModel):
    item: MenuItemOut
    reasons: list[str]
    note: str | None = None  # optional LLM-written sentence; never contains prices it can't back up
    suggested_quantity: int = 1
    estimated_total: Decimal  # price_from x suggested_quantity, computed by the backend
    over_budget: bool = False


class ComparisonRow(BaseModel):
    label: str
    values: list[str]


class Comparison(BaseModel):
    item_ids: list[UUID]
    item_names: list[str]
    rows: list[ComparisonRow]


class PlanLine(BaseModel):
    course: Course
    item: MenuItemOut
    variant_id: UUID | None = None
    variant_name: str | None = None
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class CourseSubtotal(BaseModel):
    course: Course
    items: int
    subtotal: Decimal


class MealPlan(BaseModel):
    """A concrete order built by the backend; every amount is computed, never generated."""

    party_size: int
    budget: Decimal | None
    lines: list[PlanLine]
    course_subtotals: list[CourseSubtotal]
    total: Decimal
    per_person: Decimal
    remaining: Decimal | None
    within_budget: bool
    assumptions: list[str]


class Clarification(BaseModel):
    question: str
    options: list[str]


class ChatResponse(BaseModel):
    conversation_id: UUID
    message: str
    intent: Intent
    recommendations: list[Recommendation]
    comparison: Comparison | None = None
    plan: MealPlan | None = None
    clarification: Clarification | None = None
    follow_ups: list[str]
    applied_filters: SearchFilters
    filter_summary: list[str]
    source: Literal["llm", "rules"]


class SearchRequest(BaseModel):
    query: str | None = Field(default=None, max_length=500)
    filters: SearchFilters | None = None
    limit: int = Field(default=10, ge=1, le=50)


class SearchResponse(BaseModel):
    items: list[MenuItemOut]
    total: int
    applied_filters: SearchFilters
    filter_summary: list[str]
