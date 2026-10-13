"""Input guardrails, applied before any LLM call.

The assistant only helps with one restaurant's menu. Messages that try to
override its instructions, or that ask for something unrelated (code, essays,
homework, news...), never reach the LLM: they cost money and are the main way
to make a model say something it shouldn't. Screening is deterministic and
deliberately conservative - a message that mentions the menu goes through.
"""

from __future__ import annotations

import re
from typing import Literal

from app.models import MenuItem
from app.services.intent_rules import build_vocabulary
from app.services.matching import contains_phrase, find_mentions, normalize

Verdict = Literal["ok", "off_topic", "injection"]

# After this many flagged messages a conversation stops using the LLM.
MAX_STRIKES = 3

_INJECTION = [
    r"\b(?:ignore|disregard|forget|override|bypass)\b.{0,30}\b(?:instructions?|rules|prompts?|guidelines|polic(?:y|ies)|guardrails?|restrictions?)\b",
    r"\b(?:system|developer|hidden|initial|original)\s+(?:prompt|message|instructions?)\b",
    r"\b(?:reveal|show|print|repeat|tell me|what (?:is|are)|leak)\b.{0,20}\b(?:your|the)\s+(?:prompt|instructions|rules|configuration|api key)\b",
    r"\byou are (?:now|no longer)\b",
    r"\b(?:pretend|act|behave|roleplay|role play)\s+(?:to be|as|like)\b",
    r"\bfrom now on\b.{0,40}\byou\b",
    r"\b(?:jailbreak|dan mode|developer mode|god mode|sudo)\b",
    r"\bnew (?:instructions|rules|persona)\b",
    r"<\|?(?:system|im_start|im_end)\|?>|\[/?inst\]|###\s*(?:system|instruction)",
]

# Asking the assistant to *do* an unrelated task - refused even if a menu word
# appears ("write a poem about coffee" is still not ordering help).
_OFF_TOPIC_TASKS = [
    r"\b(?:write|compose|generate|draft|create)\b.{0,25}\b(?:poem|essay|story|song|lyrics|email|letter|article|blog|tweet|code|script|program|function|resume|cv|report|speech|joke)s?\b",
    r"\b(?:python|javascript|typescript|sql|html|css|regex|reactjs|nodejs)\b",
    r"\b(?:debug|compile|refactor)\b",
    r"\btranslate\b",
    r"\b(?:solve|integrate|differentiate|derivative|equation|homework|assignment)\b",
    r"\b(?:summari[sz]e|paraphrase|rewrite)\b.{0,20}\b(?:this|text|article|paragraph|document)\b",
]

# Unrelated subjects - refused only when the message has no menu signal.
_OFF_TOPIC_SUBJECTS = [
    r"\bweather\b", r"\bnews\b", r"\bpolitic", r"\belection", r"\bprime minister\b", r"\bpresident\b",
    r"\bstocks?\s+(?:market|prices?)\b", r"\bshare prices?\b", r"\bcrypto", r"\bbitcoin\b", r"\bcricket\b", r"\bfootball\b",
    r"\bmovies?\b", r"\bcapital of\b", r"\bwho (?:is|was|won)\b", r"\bdiagnos", r"\bsymptoms?\b",
    r"\bmedicine\b", r"\blegal advice\b", r"\blawyer\b", r"\binvest", r"\bhoroscope\b",
    r"\bwhat model\b", r"\bwhich (?:llm|model|ai)\b", r"\b(?:chatgpt|openai|gpt|llama|gemini)\b",
]

# Generic food/ordering words: their presence means the message is about the café.
_MENU_SIGNAL = re.compile(
    r"\b(?:menu|food|eat|hungry|drink|drinks|coffee|tea|latte|dessert|snack|meal|lunch|dinner|breakfast|"
    r"brunch|veg|vegan|vegetarian|allerg\w*|spicy|sweet|cold|hot|iced|price|budget|cheap|order|cart|"
    r"recommend|suggest|starter|main|pizza|pasta|sandwich|salad|soup|cake|share|people|rs|inr)\b"
)


def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def screen(message: str, items: list[MenuItem]) -> Verdict:
    """Classify a customer message before it may be sent to an LLM."""
    text = normalize(message)
    raw = message.lower()
    if _any(_INJECTION, raw) or _any(_INJECTION, text):
        return "injection"
    if _any(_OFF_TOPIC_TASKS, text):
        return "off_topic"
    if _any(_OFF_TOPIC_SUBJECTS, text) and not _has_menu_signal(message, text, items):
        return "off_topic"
    return "ok"


def _has_menu_signal(message: str, text: str, items: list[MenuItem]) -> bool:
    if _MENU_SIGNAL.search(text) or "₹" in message:
        return True
    if find_mentions(message, items)[0]:
        return True
    return any(contains_phrase(text, w) for w in build_vocabulary(items))
