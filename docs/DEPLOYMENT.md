# Deployment

## Render (one-click Blueprint)

`render.yaml` at the repo root defines three free-tier resources, all in the
Singapore region:

| Resource | What it runs |
|---|---|
| `resai-coffee-db` | PostgreSQL |
| `resai-coffee-api` | FastAPI. On every start it runs `alembic upgrade head`, then the idempotent seed, then uvicorn. Health check: `/api/health` |
| `resai-coffee-web` | Next.js. Proxies `/api/*` to `BACKEND_URL` |

Steps:

1. Push the repo to GitHub.
2. Render dashboard → **New → Blueprint** → select the repo → **Apply**.
3. When the first deploy finishes, open the `resai-coffee-api` service and
   check its URL. If it isn't exactly `https://resai-coffee-api.onrender.com`
   (Render adds a suffix when a name is taken), set `BACKEND_URL` on
   `resai-coffee-web` to the real URL and click **Manual Deploy**. The URL is
   baked into the proxy at build time, so a redeploy is required. Also update
   `CORS_ORIGINS` on the API to the web service's real URL.
4. Open the `resai-coffee-web` URL.

Free-tier caveats:

- Services sleep when idle. The first request after a pause can take about a
  minute while both services wake up. Server-side fetches allow 70 seconds
  for this.
- Free Postgres databases expire after a limited period. Check the Render
  dashboard for the date, and upgrade the plan to keep the data.
- The demo runs with `ASSISTANT_DEMO_MODE=true`. To use Claude, set it to
  `false` and add `ANTHROPIC_API_KEY` as a secret env var on
  `resai-coffee-api`.
- `TRUST_PROXY_HEADERS=true` is required because Render's proxy hides the
  client IP. The limiter keys on the first `X-Forwarded-For` entry, which a
  client can forge. That's acceptable for a demo; for production, enforce
  limits at an edge you control.

## Components

| Component | Runs as | Notes |
|---|---|---|
| PostgreSQL 14+ | Managed DB (RDS, Cloud SQL, Neon, Supabase…) | Use TLS and a least-privilege role |
| Backend | Container (`backend/Dockerfile`) or any ASGI host | Stateless except the in-process rate limiter |
| Frontend | Vercel, or `next build && next start` in a container | Needs `BACKEND_URL` reachable from the server |

## Backend

```bash
cd backend
docker build -t restaurant-assistant-api .
# Release step (run once per deploy, before starting new instances):
docker run --rm -e DATABASE_URL=... restaurant-assistant-api alembic upgrade head
# Optional, for a demo environment only:
docker run --rm -e DATABASE_URL=... restaurant-assistant-api python -m app.seed.seed
# Serve:
docker run -p 8000:8000 --env-file prod.env restaurant-assistant-api
```

Production environment (see `backend/.env.example`):

- `ENVIRONMENT=production`
- `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB?sslmode=require`
- `CORS_ORIGINS=https://your-frontend.example`. Only needed if browsers call
  the API directly. With the Next.js proxy, browsers never do.
- `ASSISTANT_DEMO_MODE=false`, `ANTHROPIC_API_KEY=<from your secret
  manager>`. To run without an LLM, keep demo mode on.
- `TRUST_PROXY_HEADERS=true` **only** when the service sits behind a load
  balancer that sets `X-Forwarded-For`. Otherwise clients can spoof their
  IP and dodge rate limits.
- `ADMIN_API_KEY` only if you want the onboarding endpoints enabled.

Health check: `GET /api/health` (returns `degraded` if the DB is unreachable).

### Rate limiting at scale

`app/ratelimit.py` is an in-process sliding window, which is correct for a
single instance. With multiple replicas, either:

1. enforce limits at the edge (API gateway, Cloudflare, NGINX
   `limit_req`), or
2. swap `SlidingWindowLimiter` for a Redis-backed implementation with the
   same `check(key, limit, window)` signature.

Also put a budget alert on your LLM provider account. The chat endpoint
makes up to two LLM calls per message.

### Data retention

Conversations and messages are stored for multi-turn context. Add a
scheduled job to delete conversations older than your retention window
(for example `DELETE FROM conversations WHERE updated_at < now() - interval '30 days'`;
messages cascade).

## Frontend

```bash
cd frontend
npm ci
npm run build
BACKEND_URL=https://api.internal.example npm start   # port 3000
```

- On **Vercel**, set `BACKEND_URL` (and optionally `DEFAULT_RESTAURANT_SLUG`)
  as environment variables. They are server-only. The `/api/*` rewrite in
  `next.config.mjs` proxies browser requests to the backend, so no CORS
  configuration is needed and no backend URL or key reaches the client.
- The proxy forwards `X-Forwarded-For`. Enable `TRUST_PROXY_HEADERS` on the
  backend only if the backend is not publicly reachable except through
  trusted proxies.

## Secrets

- Never commit `.env` files. `.gitignore` excludes them and only
  `*.env.example` placeholders are tracked.
- `ANTHROPIC_API_KEY` and `ADMIN_API_KEY` belong in your platform's secret
  manager.
