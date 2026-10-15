"""Menu ingestion - turn an uploaded PDF, photos or pasted text into a draft.

Three routes, best first:

1. ``vision``: Claude reads the PDF/photos directly (needs ANTHROPIC_API_KEY).
2. ``text-llm``: the PDF's text layer (or pasted text) is structured by the
   configured chat LLM (Groq by default).
3. ``text-rules``: the same text through the deterministic line parser.

Whatever the route, the result is a ``DraftMenu`` for a human to review
before anything is published. Model output is re-validated item by item;
an item with a missing name or an unreadable price is dropped with a warning.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from app.config import DEFAULT_MODELS, Settings
from app.ingestion.text_parser import DraftItem, DraftMenu, DraftProfile, DraftVariant, parse_menu_text
from app.llm.base import LLMError, LLMProvider
from app.money import to_money

logger = logging.getLogger(__name__)

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
PDF_TYPE = "application/pdf"


class ExtractionError(Exception):
    """The upload could not be turned into a draft (shown to the admin)."""


@dataclass
class Upload:
    filename: str
    content_type: str
    data: bytes


SYSTEM = """You transcribe restaurant and café menus into structured data.

Rules:
- Transcribe only what is printed. Never invent items, prices or descriptions.
- One entry per orderable item, under the section heading it appears in.
- price is the number only, as printed, without currency ("250", "249.50").
- If an item has several sizes/options with their own prices (Regular/Large,
  Half/Full, Hot/Iced...), list them in variants and set price to the first one.
  Otherwise variants is [].
- item_type: "beverage" for anything drunk, "dessert" for sweets, else "food".
- temperature: "hot" or "cold" for beverages when clear from the name or
  section, otherwise null. null for food.
- contains_coffee: true/false for beverages when clear, otherwise null.
- is_vegetarian: true ONLY when the menu marks it (a green veg symbol, "(V)",
  an all-veg restaurant statement). false when the menu marks it non-veg or
  the item's name or description names meat, fish, seafood or egg.
  Otherwise null. Vegetarian follows the Indian convention: no meat, fish or egg.
- tags: up to 4 short lowercase words useful for search, chosen from things
  like coffee, tea, espresso, milk-based, juice, shake, smoothie, mocktail,
  starter, soup, salad, main, pasta, pizza, burger, sandwich, wrap, bowl,
  rice, noodles, bread, breakfast, shareable, spicy.
- description: the printed description, or null. Do not write your own.
- profile: the restaurant's name, tagline, address, city and phone if they are
  printed on the menu, otherwise null.
- Skip taxes, service-charge notes, timings and other non-item text."""

_NULLABLE_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}
_NULLABLE_BOOL = {"anyOf": [{"type": "boolean"}, {"type": "null"}]}

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["profile", "items"],
    "properties": {
        "profile": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "tagline", "address_line", "city", "phone"],
            "properties": {k: _NULLABLE_STR for k in ("name", "tagline", "address_line", "city", "phone")},
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "category", "name", "price", "description", "item_type", "temperature",
                    "contains_coffee", "is_vegetarian", "tags", "variants",
                ],
                "properties": {
                    "category": {"type": "string"},
                    "name": {"type": "string"},
                    "price": {"type": "string"},
                    "description": _NULLABLE_STR,
                    "item_type": {"type": "string", "enum": ["beverage", "food", "dessert"]},
                    "temperature": {"anyOf": [{"type": "string", "enum": ["hot", "cold"]}, {"type": "null"}]},
                    "contains_coffee": _NULLABLE_BOOL,
                    "is_vegetarian": _NULLABLE_BOOL,
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "variants": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["name", "price"],
                            "properties": {"name": {"type": "string"}, "price": {"type": "string"}},
                        },
                    },
                },
            },
        },
    },
}


def _money(raw: Any) -> Decimal | None:
    text = str(raw or "").replace(",", "").replace("₹", "").strip()
    try:
        value = to_money(text)
    except (ValueError, InvalidOperation):
        return None
    return value if value >= 0 else None


def _section_name(raw: Any) -> str:
    name = " ".join(str(raw or "").split())[:120] or "Menu"
    # Menus often print names in capitals; "HOT COFFEE" reads better as "Hot Coffee".
    return name.title() if name.isupper() else name


def draft_from_llm(data: dict[str, Any], method: str) -> DraftMenu:
    """Validate model output into a DraftMenu, dropping (and reporting) bad items."""
    items: list[DraftItem] = []
    warnings: list[str] = []
    for raw in data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        variants = []
        for v in raw.get("variants") or []:
            price = _money(v.get("price")) if isinstance(v, dict) else None
            if price is not None and str(v.get("name") or "").strip():
                variants.append(DraftVariant(name=str(v["name"]).strip()[:80], price=price))
        price = _money(raw.get("price"))
        if price is None and variants:
            price = variants[0].price
        if not name or price is None:
            warnings.append(f"Skipped an item with no readable name or price: {name or raw!r}"[:200])
            continue
        try:
            items.append(
                DraftItem(
                    category=_section_name(raw.get("category")),
                    name=name[:160],
                    price=price,
                    description=(str(raw.get("description") or "").strip() or None),
                    item_type=raw.get("item_type") if raw.get("item_type") in ("beverage", "food", "dessert") else "food",
                    temperature=raw.get("temperature") if raw.get("temperature") in ("hot", "cold") else None,
                    contains_coffee=raw.get("contains_coffee") if isinstance(raw.get("contains_coffee"), bool) else None,
                    is_vegetarian=raw.get("is_vegetarian") if isinstance(raw.get("is_vegetarian"), bool) else None,
                    tags=[str(t).strip().lower()[:40] for t in (raw.get("tags") or []) if str(t).strip()][:12],
                    variants=variants[:12],
                )
            )
        except ValidationError:
            warnings.append(f"Skipped an item that failed validation: {name}"[:200])
    profile_raw = data.get("profile") if isinstance(data.get("profile"), dict) else {}
    profile = DraftProfile(**{k: (str(v).strip() or None) if v else None for k, v in profile_raw.items()
                              if k in DraftProfile.model_fields})
    if profile.name:
        profile.name = _section_name(profile.name)[:160]
    if not items:
        warnings.append("No priced items were found. Try a clearer scan or paste the menu text.")
    names = [i.name.lower() for i in items]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        warnings.append(f"Duplicate item names (check sections/sizes): {', '.join(dupes)}")
    return DraftMenu(items=items, profile=profile, warnings=warnings, method=method)


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except (PdfReadError, ValueError) as exc:
        raise ExtractionError("That PDF could not be read.") from exc


def _vision(uploads: list[Upload], text: str, settings: Settings) -> DraftMenu:
    import anthropic

    content: list[dict[str, Any]] = []
    for up in uploads:
        b64 = base64.standard_b64encode(up.data).decode()
        if up.content_type == PDF_TYPE:
            content.append({"type": "document", "source": {"type": "base64", "media_type": PDF_TYPE, "data": b64}})
        else:
            content.append({"type": "image", "source": {"type": "base64", "media_type": up.content_type, "data": b64}})
    if text.strip():
        content.append({"type": "text", "text": f"Additional menu text:\n{text}"})
    content.append({"type": "text", "text": "Transcribe this menu (all pages/photos) into the schema."})

    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key.get_secret_value().strip(),
        timeout=settings.menu_extract_timeout_seconds,
        max_retries=1,
    )
    try:
        # Streamed because a long menu can take a few minutes to write out.
        with client.messages.stream(
            model=settings.menu_extract_model.strip() or DEFAULT_MODELS["anthropic"],
            max_tokens=64000,
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        ) as stream:
            response = stream.get_final_message()
    except anthropic.APIStatusError as exc:
        raise LLMError(f"Claude API error {exc.status_code}: {getattr(exc, 'message', '')}"[:300]) from exc
    except anthropic.APIConnectionError as exc:
        raise LLMError("Claude unreachable or timed out") from exc
    if response.stop_reason == "refusal":
        raise LLMError("Claude declined to read this file")
    if response.stop_reason == "max_tokens":
        raise LLMError("The menu is too long to read in one go; upload it in parts")
    raw = next((b.text for b in response.content if b.type == "text"), "")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError("Claude returned invalid JSON") from exc
    return draft_from_llm(data, "vision")


def _structure_text(text: str, provider: LLMProvider | None) -> DraftMenu:
    if provider is not None:
        try:
            data = provider.generate_json(
                system=SYSTEM, user=f"Menu text (extracted from a PDF or pasted):\n\n{text}", schema=SCHEMA,
                max_tokens=16000,
            )
            draft = draft_from_llm(data, "text-llm")
            if draft.items:
                return draft
        except LLMError as exc:
            logger.warning("LLM menu structuring failed, using the line parser: %s", exc)
    return parse_menu_text(text)


def extract_menu(
    uploads: list[Upload], text: str, *, settings: Settings, provider: LLMProvider | None
) -> DraftMenu:
    if not uploads and not text.strip():
        raise ExtractionError("Upload a menu file or paste the menu text.")
    for up in uploads:
        if up.content_type != PDF_TYPE and up.content_type not in IMAGE_TYPES:
            raise ExtractionError(
                f"{up.filename}: unsupported file type ({up.content_type or 'unknown'}). "
                "Use PDF, JPG, PNG or WebP (convert iPhone HEIC photos to JPG)."
            )

    if uploads and settings.menu_vision_enabled:
        try:
            draft = _vision(uploads, text, settings)
            if draft.items:
                return draft
            logger.warning("Vision extraction found no items; trying the text route")
        except LLMError as exc:
            logger.warning("Vision extraction failed: %s", exc)
            if not any(u.content_type == PDF_TYPE for u in uploads) and not text.strip():
                raise ExtractionError(f"Couldn't read the photos: {exc}") from exc

    if any(u.content_type in IMAGE_TYPES for u in uploads) and not settings.menu_vision_enabled:
        if not text.strip() and all(u.content_type in IMAGE_TYPES for u in uploads):
            raise ExtractionError(
                "Reading photos needs ANTHROPIC_API_KEY on the server. Upload a PDF or paste the menu text instead."
            )

    parts = [pdf_text(u.data) for u in uploads if u.content_type == PDF_TYPE]
    if text.strip():
        parts.append(text)
    combined = "\n".join(p for p in parts if p.strip())
    if not combined.strip():
        raise ExtractionError(
            "The PDF has no text layer (it's a scan). Set ANTHROPIC_API_KEY to read scans, or paste the menu text."
        )
    return _structure_text(combined[:60_000], provider)
