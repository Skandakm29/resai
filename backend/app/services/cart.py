"""Server-side cart validation. Client prices are never trusted."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Restaurant
from app.money import format_inr, to_money
from app.schemas.cart import CartAddonOut, CartLineOut, CartValidateRequest, CartValidateResponse
from app.services import menu_service


def validate_cart(db: Session, restaurant: Restaurant, req: CartValidateRequest) -> CartValidateResponse:
    items = {i.id: i for i in menu_service.load_items(db, restaurant)}
    lines: list[CartLineOut] = []
    subtotal = Decimal("0.00")
    count = 0

    for line in req.lines:
        issues: list[str] = []
        item = items.get(line.item_id)  # restaurant-scoped: foreign IDs are simply unknown
        if item is None:
            lines.append(
                CartLineOut(
                    item_id=line.item_id, name=None, variant_id=line.variant_id, variant_name=None, addons=[],
                    quantity=line.quantity, unit_price=None, line_total=Decimal("0.00"), status="invalid",
                    issues=["This item is not on the menu."],
                )
            )
            continue

        status = "ok"
        unit = item.price
        variant = None
        if line.variant_id is not None:
            variant = next((v for v in item.variants if v.id == line.variant_id), None)
            if variant is None:
                issues.append("Selected size/variant does not belong to this item.")
                status = "invalid"
            elif not variant.is_available:
                issues.append(f"{variant.name} is currently unavailable.")
                status = "unavailable"
            else:
                unit = variant.price
        elif item.variant_required:
            issues.append("Please choose a size/variant.")
            status = "invalid"
        elif item.variants:
            default = next((v for v in item.variants if v.is_default and v.is_available), None)
            if default is not None:
                variant, unit = default, default.price

        addons_out: list[CartAddonOut] = []
        allowed = {a.id: a for a in item.addons if a.restaurant_id == restaurant.id}
        if len(set(line.addon_ids)) != len(line.addon_ids):
            issues.append("Duplicate add-ons were removed.")
        for addon_id in dict.fromkeys(line.addon_ids):
            addon = allowed.get(addon_id)
            if addon is None:
                issues.append("An add-on is not available for this item.")
                status = "invalid"
            elif not addon.is_available:
                issues.append(f"{addon.name} is currently unavailable.")
                status = "unavailable" if status == "ok" else status
            else:
                addons_out.append(CartAddonOut(id=addon.id, name=addon.name, price=addon.price))
                unit += addon.price

        if not item.is_available:
            issues.append(f"{item.name} is currently unavailable.")
            status = "invalid" if status == "invalid" else "unavailable"

        unit = to_money(unit)
        if status == "ok" and line.unit_price is not None and to_money(line.unit_price) != unit:
            status = "price_changed"
            issues.append(f"Price updated from {format_inr(line.unit_price)} to {format_inr(unit)}.")

        line_total = to_money(unit * line.quantity) if status in ("ok", "price_changed") else Decimal("0.00")
        if status in ("ok", "price_changed"):
            subtotal += line_total
            count += line.quantity
        lines.append(
            CartLineOut(
                item_id=item.id, name=item.name, variant_id=variant.id if variant else line.variant_id,
                variant_name=variant.name if variant else None, addons=addons_out, quantity=line.quantity,
                unit_price=unit, line_total=line_total, status=status, issues=issues,
            )
        )

    valid = bool(lines) and all(l.status == "ok" for l in lines)
    ordering = restaurant.settings.ordering_enabled if restaurant.settings else False
    if not lines:
        message = "Your cart is empty."
    elif valid:
        message = "Your cart is verified against the current menu."
    else:
        message = "Some items need your attention before checkout."
    if valid and not ordering:
        message += " Online ordering isn't connected yet - please place this order at the counter."
    return CartValidateResponse(
        valid=valid,
        currency=restaurant.currency,
        lines=lines,
        subtotal=to_money(subtotal),
        item_count=count,
        ordering_enabled=ordering,
        message=message,
    )
