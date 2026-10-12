"""Resolve free-text references ("the cappuccino") to real menu items."""

from __future__ import annotations

import difflib
import re
import unicodedata

from app.models import MenuItem

_GENERIC = {"the", "a", "an", "classic", "house", "fernwood", "our", "special", "jar", "to", "share", "and", "&"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9₹ ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_phrase(haystack: str, phrase: str) -> bool:
    """Whole-word phrase match on normalised text (allows simple plurals)."""
    if not phrase:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?:e?s)?(?![a-z0-9])", haystack) is not None


def item_aliases(item: MenuItem) -> list[str]:
    name = normalize(item.name)
    aliases = {name}
    stripped = " ".join(w for w in name.split() if w not in _GENERIC)
    if stripped:
        aliases.add(stripped)
    for kw in item.search_keywords or []:
        aliases.add(normalize(kw))
    return sorted((a for a in aliases if a), key=len, reverse=True)


def find_mentions(text: str, items: list[MenuItem]) -> tuple[list[MenuItem], set[str]]:
    found, ambiguous, _ = find_mentions_with_residual(text, items)
    return found, ambiguous


def find_mentions_with_residual(text: str, items: list[MenuItem]) -> tuple[list[MenuItem], set[str], str]:
    """Return items unambiguously referenced in ``text``.

    An alias that matches several items (e.g. "latte") is ambiguous; it is
    returned in the second element so callers can use it as a keyword instead.
    The third element is the normalised text with matched item names removed,
    so that "hot chocolate" does not also read as a request for something hot.
    """
    norm = normalize(text)
    alias_owners: dict[str, list[MenuItem]] = {}
    for item in items:
        for alias in item_aliases(item):
            alias_owners.setdefault(alias, []).append(item)

    found: list[MenuItem] = []
    ambiguous: set[str] = set()
    consumed: list[tuple[int, int]] = []
    for alias in sorted(alias_owners, key=len, reverse=True):
        for m in re.finditer(rf"(?<![a-z0-9]){re.escape(alias)}(?:e?s)?(?![a-z0-9])", norm):
            span = m.span()
            if any(s <= span[0] < e or s < span[1] <= e for s, e in consumed):
                continue
            owners = alias_owners[alias]
            if len(owners) == 1:
                if owners[0] not in found:
                    found.append(owners[0])
                consumed.append(span)
            else:
                exact = [o for o in owners if normalize(o.name) == alias]
                if len(exact) == 1:
                    if exact[0] not in found:
                        found.append(exact[0])
                    consumed.append(span)
                else:
                    ambiguous.add(alias)
    # Order by position in the text so "compare A and B" keeps A first.
    found.sort(key=lambda it: min((norm.find(a) for a in item_aliases(it) if a in norm), default=len(norm)))
    residual = norm
    for s, e in sorted(consumed, reverse=True):
        residual = residual[:s] + " " + residual[e:]
    return found, ambiguous, re.sub(r"\s+", " ", residual).strip()


def resolve_names(names: list[str], items: list[MenuItem]) -> list[MenuItem]:
    """Map LLM-provided item names to real items. Unknown names are dropped."""
    resolved: list[MenuItem] = []
    by_alias = {alias: item for item in items for alias in item_aliases(item)}
    for raw in names:
        norm = normalize(raw)
        if not norm:
            continue
        match = by_alias.get(norm)
        if match is None:
            mentions, _ = find_mentions(raw, items)
            match = mentions[0] if len(mentions) == 1 else None
        if match is None:
            close = difflib.get_close_matches(norm, list(by_alias), n=1, cutoff=0.85)
            match = by_alias[close[0]] if close else None
        if match is not None and match not in resolved:
            resolved.append(match)
    return resolved
