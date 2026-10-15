"""Menu ingestion - turn an uploaded PDF, photos or pasted text into a draft.

Everything is read locally and with open-source models; no file is sent to
an external document API:

1. PDF pages and photos go through local OCR (``app.ingestion.ocr``). A PDF's
   text layer, when it has one, is only used to correct OCR'd prices.
2. The OCR text (or pasted text) is structured by open-source chat models on
   Groq, in page-sized chunks spread across several models in parallel so a
   long menu fits the free tier's per-model token limits (``text-llm``).
3. Without a working LLM, the deterministic line parser is used (``text-rules``).

Whatever the route, the result is a ``DraftMenu`` for a human to review
before anything is published. Model output is re-validated item by item;
an item with a missing name or an unreadable price is dropped with a warning.
"""

from __future__ import annotations

import io
import logging
import queue
import re
import threading
import time
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from app.config import Settings
from app.ingestion import ocr
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
- Skip taxes, service-charge notes, timings and other non-item text.

The text usually comes from OCR of a designed menu, so:
- Words may be run together or split ("CLASSICPANEERTIKKA", "HA KK A"). Write
  names with normal spacing and Title Case ("Classic Paneer Tikka").
- A price's rupee sign may come out as F, ?, ¥, |, I or Z ("F239", "|379",
  "IF369"): the price is the digits after it (239, 379, 369). Never alter the
  digits themselves.
- Lines can mix two columns; use the layout and headings to keep each price
  with its own dish.
- category must be a section heading printed in the text. Items before the
  first heading in this text belong to the heading the page is about (often
  repeated as the page title), not a heading you make up."""

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


def _restaurant_name(raw: str, profile: DraftProfile) -> str:
    """"THE BREW ROOM - Koramangala, Bengaluru" -> "The Brew Room" when the tail is the address/city."""
    name = " ".join(raw.split())
    parts = re.split(r"(\s+[-–|·]\s+|,\s+)", name, maxsplit=1)
    if len(parts) == 3:
        head, tail = parts[0], parts[2].lower()
        place = " ".join(filter(None, [profile.address_line, profile.city])).lower()
        if place and all(w in place for w in re.findall(r"[a-z]+", tail)):
            name = head
    return _section_name(name)[:160]


_NOT_A_SECTION = re.compile(r"^(page\s*\d+|menu|main|items?|untitled|section)$", re.I)


def _section_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _tidy_sections(items: list[DraftItem]) -> None:
    """Merge section names that differ only in OCR spacing/case/punctuation, and drop made-up ones.

    "-Claypot&Tandoor", "Clay Pot & Tandoor" and "clay pot & tandoor" become one
    section, named by its best-spaced spelling. An item filed under a generic
    or invented name ("Page 24", "Main") joins the section of the item before it.
    """
    for item in items:
        item.category = item.category.strip(" -–•·:|*_.")
        if item.category.islower():
            item.category = item.category.title()
    best: dict[str, str] = {}
    for item in items:
        key = _section_key(item.category)
        current = best.get(key)
        # Prefer the spelling with the most word breaks (OCR tends to glue words).
        if current is None or item.category.count(" ") > current.count(" "):
            best[key] = item.category
    previous = None
    for item in items:
        name = best.get(_section_key(item.category), item.category)
        if not name or _NOT_A_SECTION.match(name):
            name = previous or "Menu"
        item.category = previous = name


def _typical_prices(items: list[DraftItem]) -> dict[str, Decimal]:
    by_section: dict[str, list[Decimal]] = {}
    for item in items:
        by_section.setdefault(item.category, []).append(item.price)
    return {k: sorted(v)[len(v) // 2] for k, v in by_section.items() if len(v) >= 3}


def _fix_misread_prices(items: list[DraftItem]) -> tuple[list[str], list[str]]:
    """Fix "₹379 read as 1379": a 4-digit price starting with 1 that is far above its section's
    typical price, while the last 3 digits sit right in that range. Returns (fixed, still suspicious)."""
    typical = _typical_prices(items)
    fixed, suspicious = [], []
    for item in items:
        mid = typical.get(item.category)
        if mid is None or item.price < 1000 or item.price <= mid * 3:
            continue
        digits = f"{item.price:.0f}"
        candidate = to_money(digits[1:]) if len(digits) == 4 and digits[0] in "17" else None
        if candidate is not None and mid / 2 <= candidate <= mid * 2:
            fixed.append(f"{item.name} ₹{digits} → ₹{candidate:.0f}")
            delta = item.price - candidate
            item.price = candidate
            for v in item.variants:
                if v.price >= 1000 and v.price - delta >= 0:
                    v.price = v.price - delta
        else:
            suspicious.append(f"{item.name} ₹{digits}")
    return fixed[:20], suspicious[:15]


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
        profile.name = _restaurant_name(profile.name, profile)
    _tidy_sections(items)
    fixed, suspicious = _fix_misread_prices(items)
    if fixed:
        warnings.append(f"Corrected prices where the ₹ sign was read as a 1 (please check): {', '.join(fixed)}")
    if suspicious:
        warnings.append(f"Check these prices, they look too high for their section: {', '.join(suspicious)}")
    if not items:
        warnings.append("No priced items were found. Try a clearer scan or paste the menu text.")
    names = [i.name.lower() for i in items]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        warnings.append(f"Duplicate item names (check sections/sizes): {', '.join(dupes)}")
    return DraftMenu(items=items, profile=profile, warnings=warnings, method=method)


def pdf_text_layers(data: bytes) -> list[str]:
    """Each page's embedded text (exact characters, but often scrambled on designed menus)."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        return [page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages]
    except (PdfReadError, ValueError) as exc:
        raise ExtractionError("That PDF could not be read.") from exc


def _merge(results: list[tuple[str, dict[str, Any] | None]], method: str) -> DraftMenu:
    """Combine per-part model outputs (in page order) into one draft; name the parts that failed."""
    items: list[Any] = []
    profile: dict[str, Any] = {}
    failed = []
    for label, data in results:
        if data is None:
            failed.append(label)
            continue
        items += data.get("items") or []
        for k, v in (data.get("profile") or {}).items():
            if v and not profile.get(k):
                profile[k] = v
    draft = draft_from_llm({"items": items, "profile": profile}, method)
    if failed:
        draft.warnings.insert(0, f"Couldn't read {', '.join(failed)}. Add those items by hand, or upload them again.")
    return draft


def _chunks(pages: Iterable[tuple[str, str]], max_chars: int) -> Iterator[tuple[str, str]]:
    """Group consecutive pages into chunks of at most ``max_chars``, yielding each as soon as it's full."""
    labels: list[str] = []
    body = ""

    def flush() -> tuple[str, str]:
        label = labels[0] if len(set(labels)) == 1 else f"{labels[0]} to {labels[-1]}"
        return label, body

    for label, page in pages:
        page = page.strip()
        while page:
            room = max_chars - len(body) - (1 if body else 0)
            if room < min(len(page), max_chars // 4) and body:
                yield flush()
                labels, body = [], ""
                continue
            piece, page = page[: max(room, 1)], page[max(room, 1):]
            body = f"{body}\n{piece}" if body else piece
            labels.append(label)
    if body:
        yield flush()


def _structure_text(
    pages: Iterable[tuple[str, str]], provider: LLMProvider | None, settings: Settings
) -> DraftMenu:
    """Structure page text with the chat models while pages are still arriving (e.g. from OCR).

    Pages are grouped into chunks small enough for free-tier per-minute token
    limits. One worker per model (each model has its own limit) takes chunks
    as they're ready, so OCR and structuring overlap. Chunks not done within
    the time budget are reported in the draft's warnings.
    """
    start = time.monotonic()
    deadline = start + settings.menu_text_budget_seconds
    seen: list[str] = []
    chunks: list[tuple[str, str]] = []
    results: list[dict[str, Any] | None] = []
    failures: list[int] = []
    todo: queue.Queue[int] = queue.Queue()
    produced = threading.Event()
    error: list[BaseException] = []
    lock = threading.Lock()
    order: list[int] = []  # reading order of chunks (split halves sit after their first half)

    skipped: list[str] = []

    def pages_seen() -> Iterator[tuple[str, str]]:
        # OCR is slow on a small server: stop reading new pages when time runs out.
        for label, text in pages:
            seen.append(text)
            yield label, text
            if time.monotonic() > deadline - 20:
                skipped.append(label)
                return

    def produce() -> None:
        try:
            for chunk in _chunks(pages_seen(), settings.menu_text_chunk_chars):
                with lock:
                    chunks.append(chunk)
                    results.append(None)
                    failures.append(0)
                    order.append(len(chunks) - 1)
                if provider is not None:
                    todo.put(len(chunks) - 1)
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller's thread
            error.append(exc)
        finally:
            produced.set()

    def work(model: str) -> None:
        assert provider is not None
        while time.monotonic() < deadline:
            try:
                n = todo.get(timeout=0.5)
            except queue.Empty:
                if produced.is_set() and todo.empty():
                    return
                continue
            label, body = chunks[n]
            try:
                results[n] = provider.generate_json(
                    system=SYSTEM, user=f"Menu text ({label}):\n\n{body}", schema=SCHEMA,
                    max_tokens=settings.menu_text_max_tokens, model=model,
                )
            except LLMError as exc:
                logger.warning("Structuring %s with %s failed: %s", label, model, str(exc)[:200])
                if "truncated" in str(exc) and body.count("\n") >= 4:
                    # Too many items for one answer: split the chunk in two and queue both halves.
                    with lock:
                        lines = body.splitlines()
                        half = len(lines) // 2
                        chunks[n] = (f"{label} (part 1)", "\n".join(lines[:half]))
                        chunks.append((f"{label} (part 2)", "\n".join(lines[half:])))
                        results.append(None)
                        failures.append(0)
                        order.insert(order.index(n) + 1, len(chunks) - 1)
                        todo.put(n)
                        todo.put(len(chunks) - 1)
                elif "rate limited" in str(exc) or "413" in str(exc):
                    todo.put(n)  # another model, or this one once its minute window moves
                    time.sleep(min(8.0, max(0.0, deadline - time.monotonic())))
                else:
                    failures[n] += 1
                    if failures[n] < 3:  # retry an invalid response, possibly on another model
                        todo.put(n)

    producer = threading.Thread(target=produce, daemon=True)
    producer.start()
    workers = [threading.Thread(target=work, args=(m,), daemon=True) for m in settings.menu_text_model_list]
    if provider is not None:
        for t in workers:
            t.start()
    producer.join()
    if error:
        raise error[0]
    if provider is not None:
        for t in workers:
            t.join(max(0.0, deadline - time.monotonic()) + 30)
    logger.info("Menu read: %d chunks in %.0fs", len(chunks), time.monotonic() - start)

    full = "\n".join(seen)
    if skipped:
        logger.warning("Ran out of time after %s", skipped[0])
    if not any(results):
        draft = parse_menu_text(full)
        if provider is not None:
            draft.warnings.insert(
                0, "The AI couldn't read this menu, so only simple 'name price' lines were picked up."
            )
        return draft
    draft = _merge([(chunks[n][0], results[n]) for n in order], "text-llm")
    if skipped:
        draft.warnings.insert(
            0, f"Ran out of time after {skipped[0]}, so later pages weren't read. Upload the rest separately."
        )
    return draft


def _compact(text: str) -> str:
    """Letters and digits only, accents dropped: "Hearth & Bean CAFÉ" -> "hearthbeancafe"."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", plain.lower())


def respace(draft: DraftMenu, reference: str) -> None:
    """Restore word breaks OCR lost ("SouthIndianFilter Coffee") using the PDF's text layer.

    A name is replaced by the text-layer phrase with the same letters and
    digits, keeping the draft's own capitalisation style.
    """
    words = reference.split()
    phrases: dict[str, str] = {}
    for i in range(len(words)):
        for j in range(i + 1, min(i + 9, len(words) + 1)):
            phrase = " ".join(words[i:j]).strip(" ,.:;-–|·•()")
            phrases.setdefault(_compact(phrase), phrase)

    def fix(name: str) -> str:
        found = phrases.get(_compact(name))
        if not found or found.count(" ") <= name.count(" "):
            return name
        return _section_name(found) if found.isupper() or name.istitle() else found

    for item in draft.items:
        item.name, item.category = fix(item.name), fix(item.category)
    if draft.profile.name:
        draft.profile.name = fix(draft.profile.name)


def _pages(uploads: list[Upload], text: str, layers_seen: list[str]) -> Iterator[tuple[str, str]]:
    """Each page's text in order, OCR'd lazily so structuring can start on the first pages."""
    for up in uploads:
        if up.content_type == PDF_TYPE:
            layers = pdf_text_layers(up.data)
            layers_seen += layers
            n = 0
            try:
                for n, lines in enumerate(ocr.pdf_pages_ocr(up.data, layers), start=1):
                    yield f"{up.filename} page {n}", "\n".join(lines)
            except Exception as exc:  # noqa: BLE001 - OCR is best effort; fall back to the text layer
                logger.warning("OCR failed for %s after %d pages, using its text layer: %s", up.filename, n, exc)
                for m, layer in enumerate(layers[n:], start=n + 1):
                    yield f"{up.filename} page {m}", layer
        else:
            try:
                yield up.filename, "\n".join(ocr.ocr_photo(up.data))
            except Exception as exc:  # noqa: BLE001
                raise ExtractionError(f"{up.filename}: couldn't read that image.") from exc
    if text.strip():
        yield "pasted text", text


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
    layers: list[str] = []
    draft = _structure_text(_pages(uploads, text, layers), provider, settings)
    if any(layer.strip() for layer in layers):
        respace(draft, "\n".join(layers))
    if not draft.items and not draft.unparsed_lines:
        raise ExtractionError("No text could be read from that file. Try a clearer photo, or paste the menu text.")
    return draft
