# Restaurant AI Ordering Assistant

A conversational ordering experience for a café: customers ask things like
**"Recommend a coffee under ₹250"**, get real menu items as rich cards with
reasons, refine over multiple turns ("something cold"), compare items, ask
about dietary/allergen information, and build a cart that the backend
re-validates.

The demo restaurant, **Fernwood Coffee Roasters**, is fictional. It's seeded
with 40 items covering hot and cold coffee, tea and coolers, desserts, food,
variants, add-ons, unavailable items, and verified and unknown attributes.

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
#   App: http://localhost:3000  (redirects to /r/fernwood)
```

### Demo mode vs LLM mode

| Setting | Behaviour |
|---|---|
| `ASSISTANT_DEMO_MODE=true` (default in `.env.example`) | No LLM calls. Rule-based intent parsing and deterministic replies. No key needed. |
| `ASSISTANT_DEMO_MODE=false` + `ANTHROPIC_API_KEY=...` | Claude (`LLM_MODEL`, default `claude-opus-5-5`, `LLM_EFFORT=low`) parses intent and rewords replies. Retrieval stays deterministic. |
| LLM enabled but failing (timeout, refusal, invalid JSON) | Automatically falls back to rules for that message. |

`GET /api/health` reports `assistant_mode: "rules" | "llm"`. With
`LLM_REFUSAL_FALLBACK=true`, requests opt into the Anthropic API's
server-side refusal fallback (`fallbacks: "default"`, beta
`server-side-fallback-2026-07-01`). Disable it if your platform does not
support that beta.

The provider is behind a small `LLMProvider` protocol
(`backend/app/llm/base.py`). To add another vendor, implement
`generate_json()` and register it in `app/llm/factory.py`.

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

Interactive OpenAPI docs are at `/docs`. Money is always serialised as
decimal strings (`"210.00"`), never floats.

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
- **Foundation only:** onboarding. There is a menu-text-to-draft parser and
  `MenuVersion` snapshots, but no owner UI, OCR, or publish flow yet.
- **Images:** the seed has no photos. Cards show a neutral illustrated
  placeholder, never a generated "photo" of the dish.

## Known limitations

- The rule-based parser covers common café phrasings but is not a general
  language model. Unusual phrasings may need the LLM mode.
- The LLM path is covered by tests with a fake provider. It has **not** been
  exercised against the live Anthropic API in this repository's test runs
  (no key was available).
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
