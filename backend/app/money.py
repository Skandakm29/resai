"""Decimal-only money helpers. Never use float for prices or totals."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TWO_PLACES = Decimal("0.01")


def to_money(value: Decimal | int | str | float) -> Decimal:
    """Normalise a value to a 2-dp Decimal.

    Floats are converted through ``str`` so that e.g. 249.99 stays 249.99
    (LLM JSON output arrives as float).
    """
    if isinstance(value, float):
        value = str(value)
    try:
        return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid money amount: {value!r}") from exc


def format_inr(value: Decimal) -> str:
    """₹250 / ₹249.50 - drop the paise when they are zero."""
    value = to_money(value)
    if value == value.to_integral_value():
        return f"₹{int(value):,}"
    return f"₹{value:,.2f}"
