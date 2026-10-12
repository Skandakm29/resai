# Deployment

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
