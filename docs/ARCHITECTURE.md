# Architecture

## Request flow

```
Browser ──► Next.js (App Router)
              │  server components fetch restaurant/menu directly from BACKEND_URL
              │  client components call /api/* on the same origin
              ▼
           Next.js rewrite /api/:path* ──► FastAPI
                                             │
             ┌───────────────────────────────┼──────────────────────────────┐
             ▼                               ▼                              ▼
     menu_service (tenant-scoped)   AssistantService.chat()           cart.validate_cart()
                                     1. load conversation state        canonical prices,
                                     2. parse: LLM ─fail─► rules        variants, add-ons,
                                     3. execute intent (search.py)      availability
                                     4. deterministic reply
                                     5. optional LLM rewording (validated)
                                     6. persist messages + state
```

The browser never sees the backend URL or any API key. All LLM calls happen
in FastAPI.

## Backend modules (`backend/app`)

| Module | Responsibility |
|---|---|
| `models.py` | SQLAlchemy models: Restaurant, RestaurantSettings, Menu, MenuVersion, MenuCategory, MenuItem, MenuItemVariant, MenuAddon (+ `menu_item_addons`), Conversation, ConversationMessage |
| `schemas/` | Pydantic request/response and domain schemas (`SearchFilters`, `ParsedQuery`, `ChatResponse`, cart) |
| `services/menu_service.py` | All menu reads, always filtered by `restaurant_id`. Serialisation, variant-aware `price_from`, orderability |
| `services/search.py` | Deterministic filtering, ranking, reasons, alternatives, filter chips |
| `services/intent_rules.py` | Rule-based parser (demo mode and LLM fallback), including multi-turn merge rules |
| `services/matching.py` | Resolves item names and aliases in text to real items; drops unknown names |
| `services/assistant.py` | Orchestration per intent: recommend, cheapest, compare, pairing, item_info, menu_overview, greeting, order_help, off_topic, clarify |
| `services/cart.py` | Server-side cart validation. Client prices are informational only |
| `llm/` | Provider protocol, Anthropic implementation, prompts, JSON schemas, output validators |
| `ratelimit.py` | Sliding-window limiter dependency for public AI endpoints |
| `ingestion/text_parser.py` | Onboarding foundation: menu text to reviewable draft |

## Data model notes

- **Tenant isolation:** every menu row (categories, items, variants, add-ons,
  versions) carries `restaurant_id`, and every query filters on it. Item
  lookups by ID go through the restaurant's active menus, so a foreign ID
  returns 404 (or `invalid` in cart validation). Conversations are bound to a
  restaurant. A conversation ID from another restaurant starts a fresh
  conversation and is never reused.
- **Money:** `NUMERIC(10,2)` in Postgres and `Decimal` in Python. It's
  serialised as a string. The frontend does display arithmetic in integer
  paise, and the backend re-prices everything on validation.
- **Unknown vs. false:** `is_vegetarian`/`is_vegan` are nullable (NULL means
  not verified). `ingredients_status` is `verified|partial|unknown` and
  `allergens_status` is `verified|unknown`. An empty allergen list only means
  "none" when the status is `verified`. The API returns explicit tri-state
  and status fields, and the UI shows "Not verified - please ask staff".
- **Vegetarian** follows the Indian convention (no meat, fish or egg), so
  the egg-based cheesecake is `is_vegetarian = false`.
- **Variants** have absolute prices. `variant_required` forces a choice in
  the UI and in cart validation.
- **MenuVersion** stores an immutable JSON snapshot when a menu is published
  (the seed publishes v1). This is the hook for review, publish and rollback
  in onboarding.

## Assistant design

### Parsing

`ParsedQuery = {intent, filters: SearchFilters, mentioned_items, refers_to_previous, info_topic, limit}`.

- **LLM parse:** the model receives the menu vocabulary (category and item
  names, tags, flavour words), the previous filters, the last shown items,
  recent turns and the message. It returns the *complete* updated filters
  under a strict JSON schema. The output is validated with Pydantic
  (ranges, enums, allergen normalisation). Item names are resolved against
  the real menu and unknown names are dropped.
- **Rule parse:** regexes for budgets (`under ₹250`, `between 200 and 300`,
  `rs 199`), party size, coffee/no-coffee, temperature, sweetness, strength,
  dietary, allergens, sorting, and keywords drawn from the restaurant's own
  vocabulary. Dish names are matched first and removed from the text, so
  "hot chocolate" doesn't also mean "hot".

**Multi-turn merge rules** (rules parser; the LLM is instructed the same
way):

| Situation | Result |
|---|---|
| Refinement ("something cold", short messages, "only vegan") | Previous filters + new constraint |
| New subject ("show me desserts") | Keep budget, party size, dietary, allergens. Drop type/taste |
| "any price is fine" / "no budget" | Clear budget only |
| "start over" | Clear everything |
| Info, compare and order questions | Answer, but don't change the active search filters |

### Execution and safety rules

- Only orderable items are recommended. An unavailable item is only shown
  when the customer asks about it by name, and it's marked unavailable,
  with available similar items suggested alongside.
- Budget comparison is inclusive (`≤`) and variant-aware: the cheapest
  available variant must fit. With a party size above 1, the budget is the
  group total (`quantity × price`, or one unit when the item serves the
  group).
- Allergen exclusion only returns items with **verified** allergen lists.
  The reply says how many unverified items were left out and adds a staff
  confirmation note.
- Empty results are stated plainly. When there's a budget, the two closest
  real items above it are shown and flagged `over_budget`.
- The assistant never claims an order was placed. `order_help` explains the
  checkout placeholder.

### LLM output validation

`validate_compose_output()` rejects the LLM's wording when:

- it mentions any `₹` amount not present in the results, budgets or
  computed differences
- it contains prohibited claims (order placed/confirmed, payment
  received, "allergen-free", "nut-free", "safe for", "guarantee")
- the schema is invalid

Notes attached to unknown item IDs are silently dropped. Any rejection falls
back to the deterministic reply for that message.

## Frontend (`frontend/src`)

| Path | Purpose |
|---|---|
| `app/r/[slug]/layout.tsx` | Fetches restaurant (server), mounts providers and shell |
| `app/r/[slug]/page.tsx` | Assistant page: chat + desktop cart sidebar |
| `app/r/[slug]/menu/page.tsx` | Regular menu with category tabs |
| `components/assistant/*` | Chat state provider (sessionStorage), chat UI, recommendation cards, comparison table |
| `components/cart/*` | Cart reducer (localStorage per restaurant), cart panel with server validation |
| `components/menu/*` | Item dialog (variants, add-ons, quantity, allergen/ingredient status), badges, placeholder image, menu browser |
| `components/ui/*` | shadcn-style primitives (Button, Badge, Dialog, Skeleton) |
| `lib/api.ts` | Typed fetch client with timeouts and retryable error classification |
| `lib/money.ts` | Integer-paise math and INR formatting |

Chat and cart state live in providers mounted in the restaurant layout, so
moving between Assistant and Menu keeps both. A reload restores the chat
(sessionStorage) and the cart (localStorage).
