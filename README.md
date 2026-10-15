# Restaurant AI Ordering Assistant

A conversational ordering experience for a café: customers ask things like
**"Recommend a coffee under ₹250"**, get real menu items as rich cards with
reasons, refine over multiple turns ("something cold"), compare items, ask
about dietary/allergen information, and build a cart that the backend
re-validates.

The default restaurant is **Moai** (`/r/moai`), Redefined Vegetarian Dining in Jayanagar, Bengaluru: 205 items in 31 sections. The food comes from the restaurant's PDF menu (main, Jain and vegan pages) in `backend/app/seed/moai_food.py`. The drinks and smoothie bowls come from the printed drinks menu in `backend/app/seed/moai.py`. Signature dishes use the menu's own photography, and the green-and-cream theme matches the menu (`frontend/src/lib/brand.ts`). Vegan marks come from the menu's vegan page; allergens are not verified.

**Meloghrano Cafe** (`/r/meloghrano`) is a second demo café (Basavanagudi, Bengaluru): 210
items transcribed from the café's public menu on Zomato (October 2026), in
`backend/app/seed/meloghrano.py`. This is an unofficial demo, not affiliated
with the café. Prices may have changed, and dietary/allergen information is
**not verified**, so the assistant says so. Only items the menu itself shows
contain egg are marked non-vegetarian. Strength and sweetness are coarse
estimates from the drink type, used for ranking.

**Fernwood Coffee Roasters** (`/r/fernwood`) is a fictional café with fully
specified test data (verified and unknown attributes, unavailable items),
used by the automated tests.

```
frontend/   Next.js 14 (App Router) + TypeScript + Tailwind + shadcn-style UI + Lucide
backend/    FastAPI + Pydantic + SQLAlchemy 2 + Alembic + PostgreSQL
docs/       Architecture, deployment and testing notes
scripts/    dev-postgres.sh - a user-owned local PostgreSQL cluster
```

## How it works (short version)

The **LLM is never the source of truth for the menu.**

1. The customer message is parsed into a typed `ParsedQuery` (intent and
   `SearchFilters`). The LLM does this when one is configured. Otherwise a
   deterministic rule-based parser does it. LLM output is schema-validated,
   and invalid output falls back to the rules.
2. Deterministic backend code handles price, category, availability,
   dietary and allergen filtering, ranking, comparison and cart totals, all
   with `Decimal` money and all scoped to one restaurant.
3. A factual reply is built from the results. If an LLM is configured it can
   reword the reply. That output is validated: it may only reference the
   item IDs it was given, may not mention prices that aren't in the data,
   and may not make prohibited claims ("order placed", "nut-free", and so
   on). Anything else is discarded.
4. Conversation state (active filters, last shown items) is stored
   server-side, so "something cold" refines the previous search.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

## Quick start (local)

Prerequisites: Python 3.11+, Node 18.18+, PostgreSQL 14+ server binaries.

```bash
# 1. Database. Either use your own PostgreSQL, or start a self-contained
#    cluster on port 5433 (no sudo; data in ./.pgdata):
scripts/dev-postgres.sh start

# 2. Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env              # edit DATABASE_URL if not using the script above
.venv/bin/alembic upgrade head    # create schema
.venv/bin/python -m app.seed.seed # load demo restaurants (--reset to reload)
.venv/bin/uvicorn app.main:app --reload --port 8000
#   API docs: http://127.0.0.1:8000/docs

# 3. Frontend (new terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev
#   App: http://localhost:3000  (redirects to /r/meloghrano)
```

### Demo mode vs LLM mode

| Setting | Behaviour |
|---|---|
| `ASSISTANT_DEMO_MODE=true` (default in `.env.example`) | No LLM calls. Rule-based intent parsing and deterministic replies. No key needed. |
| `ASSISTANT_DEMO_MODE=false` + `LLM_PROVIDER=groq` + `GROQ_API_KEY=...` (default) | Groq parses intent (`LLM_MODEL`) and rewords replies (`LLM_COMPOSE_MODEL`). Retrieval stays deterministic. |
| `LLM_PROVIDER=xai` + `XAI_API_KEY` / `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` | Same pipeline on xAI Grok or Claude. |
| LLM enabled but failing (timeout, rate limit, refusal, invalid JSON) | Automatically falls back to rules for that message. |

`GET /api/health` reports `assistant_mode` (`"rules"` or `"llm"`) and the
active `provider:model`.

**Groq free tier:** limits are per model (8,000 tokens/minute on the test
account), and each chat message makes two calls of about 1.3k to 2k tokens.
Using different models for `LLM_MODEL` and `LLM_COMPOSE_MODEL` gives each
step its own budget. When a limit is hit, that message is answered by the
rule-based mode, so customers still get correct answers. For real traffic,
use a paid Groq tier.

Groq and xAI share one OpenAI-compatible provider
(`backend/app/llm/openai_compatible.py`). Claude uses the Anthropic SDK
(`anthropic_provider.py`). To add a vendor, implement
`generate_json()` from `backend/app/llm/base.py` and register it in
`app/llm/factory.py`.

## Commands

| Task | Command |
|---|---|
| Backend tests | `cd backend && .venv/bin/pytest` (needs PostgreSQL; uses `TEST_DATABASE_URL`, default `reschatbot_test` on port 5433) |
| Frontend tests | `cd frontend && npm test` |
| Typecheck / lint | `cd frontend && npm run typecheck && npm run lint` |
| New migration | `cd backend && .venv/bin/alembic revision --autogenerate -m "..."` |
| Reseed | `cd backend && .venv/bin/python -m app.seed.seed --reset` |
| Production build | `cd frontend && npm run build && npm start` / `uvicorn app.main:app --workers 2` |

## Deploy

`render.yaml` is a Render Blueprint for Postgres, the API and the frontend.
See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#render-one-click-blueprint).

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness and DB check, assistant mode |
| GET | `/api/restaurants/{slug}` | Restaurant profile and assistant settings |
| GET | `/api/restaurants/{slug}/menu` | Full menu grouped by category |
| GET | `/api/restaurants/{slug}/menu/categories` | Categories with item counts |
| GET | `/api/restaurants/{slug}/menu/items/{item_id}` | One item (404 if it belongs to another restaurant) |
| POST | `/api/restaurants/{slug}/assistant/chat` | Conversational assistant (rate limited) |
| POST | `/api/restaurants/{slug}/assistant/search` | Deterministic structured search (rate limited) |
| POST | `/api/cart/validate` | Re-prices and validates a cart against the canonical menu |
| POST | `/api/onboarding/menu/parse-text` | Menu text to reviewable draft (requires `X-Admin-Key`) |
| POST | `/api/onboarding/menu/extract` | Menu PDF / photos / text (multipart) to reviewable draft (admin) |
| POST | `/api/onboarding/restaurants` | Publish a reviewed draft as `/r/{slug}` (admin) |
| GET / DELETE | `/api/onboarding/restaurants[/{slug}]` | List or take down uploaded cafés (admin) |

Interactive OpenAPI docs are at `/docs`. Money is always serialised as
decimal strings (`"210.00"`), never floats.

## Onboard a café (upload a menu, get a link)

1. Set `ADMIN_API_KEY` (and optionally `ANTHROPIC_API_KEY`) on the backend.
2. Open `/admin`, enter the key, and drop in the menu PDF or photos.
3. Check the draft: café name, link, prices, sections. Fix anything off.
4. **Publish page**. You get the live link, plus a cold email you can copy
   or open in your mail app. Re-publishing to the same link replaces the menu.

## Try these

See [docs/TESTING.md](docs/TESTING.md#sample-conversations) for the full list:

- *Recommend a coffee under ₹250*, then *Something cold*, then *Compare these two drinks*
- *Find something for two under ₹500*
- *Recommend a coffee under ₹100* (an empty result, with clearly flagged over-budget alternatives)
- *Does the mocha have nuts?* (allergens unverified, so the assistant says so)
- *Is the Spanish Latte available?* (unavailable, so it suggests similar items)
- *Nut-free desserts* (excludes items with unverified allergen data and says how many)

## What's real and what's a placeholder

- **Real:** menu, search, recommendations, multi-turn state, comparisons,
  pairings, dietary/allergen answers, cart with variants and add-ons,
  server-side cart validation, rate limiting, tenant isolation.
- **Placeholder:** checkout. "Review & checkout" verifies prices and
  availability against the backend and then tells the customer to order
  at the counter. No order is placed and no payment is taken, and the UI
  never says otherwise (`ordering_enabled` is `false` for the demo).
- **Onboarding (admin only):** `/admin` takes a menu PDF, photos or pasted
  text, shows an editable draft (names, prices, sections, type, veg), and
  publishes it at `/r/{slug}` with a ready-to-send cold email. Claude reads
  photos and scanned PDFs when `ANTHROPIC_API_KEY` is set; otherwise the PDF
  text layer goes through the chat LLM (or the rule parser). Uploaded menus
  start with allergens and ingredients unverified. There are no owner
  accounts yet: one shared `ADMIN_API_KEY` protects the page.
- **Images:** the seed has no photos. Cards show a neutral illustrated
  placeholder, never a generated "photo" of the dish.

## Known limitations

- The rule-based parser covers common café phrasings but is not a general
  language model. Unusual phrasings may need the LLM mode.
- The Groq path has been exercised against the live Groq API. The xAI and
  Anthropic providers are only covered by tests with mocked responses.
- The rate limiter is in-process. Use a shared limiter for multiple replicas
  (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)).
- There is no authentication for customers. Conversations are anonymous and
  keyed by an unguessable UUID.
- Taxes, service charges and discounts are not modelled.

## Future extensions

Owner accounts and dashboard, PDF/image OCR to draft menu to review to
publish, real ordering and payment integration (behind `ordering_enabled`),
streaming responses, per-restaurant branding and photos, analytics on
unanswered queries, and a Redis-backed limiter and conversation TTL cleanup.
# resai
