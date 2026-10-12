# Testing

## Backend (pytest)

```bash
scripts/dev-postgres.sh start       # or point TEST_DATABASE_URL at any empty Postgres DB
cd backend && .venv/bin/pytest
```

The tests run against **PostgreSQL** (`TEST_DATABASE_URL`, default
`postgresql+psycopg://reschat:reschat@127.0.0.1:5433/reschatbot_test`). The
schema is recreated and seeded once per session, and each test runs in a
rolled-back transaction. The tests force demo mode and inject a fake LLM
provider where needed, so they never call a real LLM.

| File | Covers |
|---|---|
| `test_menu_api.py` | health, restaurant, menu, categories, item detail, decimal money format, unknown dietary/allergen representation, variant-aware availability and pricing |
| `test_search.py` | exact (inclusive, paisa-precise) price filtering, unavailable exclusion, empty results with flagged alternatives, verified-only vegan filter, allergen exclusion of unverified items, group budgets, price/intent parsing, search endpoint, tenant isolation |
| `test_assistant.py` | "coffee under ₹250" returns real records, multi-turn refinement / subject switch / budget clearing, comparison (contextual and named), clarification, unknown allergen answers, cross-contact note, unavailable item handling, no order claims, cart-context pairing, chat tenant isolation, persistence, validation |
| `test_llm.py` | valid LLM output used, invalid parse output falls back, LLM failure falls back, invented prices rejected, notes for unknown item IDs dropped, compose failure keeps the deterministic reply, hallucinated dish names ignored, prohibited claims rejected |
| `test_cart.py` | exact totals with variants and add-ons, client price ignored, required variant, foreign variant, unavailable item/add-on, disallowed add-on, other restaurant's item, quantity bounds, empty cart |
| `test_platform.py` | rate limiting (429 + Retry-After), onboarding admin key, menu text parser, OpenAPI paths |

## Frontend (Vitest + Testing Library)

```bash
cd frontend && npm test
```

| File | Covers |
|---|---|
| `components/assistant/chat.test.tsx` | suggested prompts submit, Enter-to-send, loading indicator, send disabled while pending, blank messages ignored, recommendation cards (price, reasons, badges, sizes/add-ons), follow-up chips, unavailable item cannot be added, error + retry without duplicate bubble, new chat, required size selection and add-on pricing into the cart, cart context sent to the API |
| `components/cart/cart.test.tsx` | empty state, add/merge/increase/decrease/remove, subtotal in paise, localStorage persistence, server validation request shape and canonical price update |
| `components/layout.test.tsx` | responsive contract: cart sidebar hidden below `lg`, chat column can shrink on phones, mobile cart bar appears with items |
| `lib/money.test.ts` | paise conversion and INR formatting |

jsdom has no layout engine, so responsive behaviour was additionally checked
in headless Chrome at 390×844 (phone) and 1366×860 (desktop). The check
covered no horizontal page scroll on the phone, recommendation carousel,
size-required dialog, cart bar, cart drawer and verification, comparison
table, menu page, and zero console errors.

## Sample conversations

These run against the seed data in demo mode. Expected behaviour is in
brackets.

**Budget filtering**
- Recommend a coffee under ₹250. [11 matching coffees exist; shows the top
  4, each at or under ₹250]
- What can I get for under ₹300? [mixed categories, all at or under ₹300]
- What is the cheapest drink available? [Masala Chai ₹120, then Espresso and
  Filter Coffee]

**Category filtering**
- Find vegetarian food. [food only, verified vegetarian]
- I want something without coffee. [teas, coolers, shakes]
- Show me desserts.

**Multi-turn refinement**
- Recommend a coffee under ₹250, then Something cold [cold coffees at or
  under ₹250], then Show me desserts instead [desserts, budget kept], then
  any price is fine [budget cleared].
- Something cold and not too sweet, then and vegan.

**Empty results**
- Recommend a coffee under ₹100. [says none match; Espresso ₹140 and Filter
  Coffee ₹150 flagged "Above budget"]

**Comparison**
- Something cold and not too sweet, then Compare these two drinks.
- Compare the flat white vs cortado. [Cortado is ₹40 cheaper]
- Compare these two drinks, with no context. [asks which two]

**Dietary and allergen information**
- Does the mocha have nuts? [allergens not verified, so it can't confirm
  and suggests asking staff]
- Does the americano contain milk? [not on the verified list, plus a
  cross-contact note]
- Is the brownie vegan? [no; it is verified vegetarian]
- Is the hot chocolate vegan? [not verified]
- Nut-free desserts. [verified-only; says 1 unverified item was left out]

**Availability**
- Is the Spanish Latte available? [unavailable; suggests Hazelnut Latte and
  Mocha]

**Pairing, groups and other**
- What pairs well with a cappuccino? / Suggest a dessert with my order (with
  a cappuccino in the cart).
- Find something for two under ₹500. [Loaded Nachos (serves 2) first; other
  items shown as 2× price]
- Can you place my order? [explains that the checkout is a placeholder]
- What's the weather in Paris? [polite off-topic redirect]
