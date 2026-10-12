from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CartLineIn(BaseModel):
    item_id: UUID
    variant_id: UUID | None = None
    addon_ids: list[UUID] = Field(default_factory=list, max_length=10)
    quantity: int = Field(ge=1, le=20)
    # The price the client displayed. Informational only: used to tell the
    # customer that a price changed. Never used for totals.
    unit_price: Decimal | None = Field(default=None, ge=0)


class CartValidateRequest(BaseModel):
    restaurant_slug: str = Field(min_length=1, max_length=80)
    lines: list[CartLineIn] = Field(max_length=50)


class CartAddonOut(BaseModel):
    id: UUID
    name: str
    price: Decimal


LineStatus = Literal["ok", "price_changed", "unavailable", "invalid"]


class CartLineOut(BaseModel):
    item_id: UUID
    name: str | None
    variant_id: UUID | None
    variant_name: str | None
    addons: list[CartAddonOut]
    quantity: int
    unit_price: Decimal | None
    line_total: Decimal
    status: LineStatus
    issues: list[str]


class CartValidateResponse(BaseModel):
    valid: bool
    currency: str
    lines: list[CartLineOut]
    subtotal: Decimal
    item_count: int
    ordering_enabled: bool
    message: str
