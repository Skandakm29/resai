"""In-process sliding-window rate limiter for public AI endpoints.

Good for a single instance. For multiple replicas, put a shared limiter in
front (API gateway / reverse proxy, or a Redis-backed limiter) - see
docs/DEPLOYMENT.md. The dependency interface stays the same.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import get_settings


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: float = 60.0) -> float | None:
        """Record a hit. Returns None if allowed, else seconds until retry."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] >= window:
                q.popleft()
            if len(q) >= limit:
                return max(0.0, window - (now - q[0]))
            q.append(now)
            if len(self._hits) > 50_000:  # crude memory bound
                for k in [k for k, v in self._hits.items() if not v][:10_000]:
                    del self._hits[k]
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    settings = get_settings()
    if settings.trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str):
    def dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        limit = settings.rate_limit_chat_per_minute if bucket == "chat" else settings.rate_limit_search_per_minute
        retry = limiter.check(f"{bucket}:{client_ip(request)}", limit)
        if retry is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait a moment and try again.",
                headers={"Retry-After": str(int(retry) + 1)},
            )

    return dependency


def hourly_limit(bucket: str, setting: str):
    """Per-IP limit of ``getattr(settings, setting)`` requests per hour."""

    def dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        retry = limiter.check(f"{bucket}:{client_ip(request)}", getattr(settings, setting), window=3600.0)
        if retry is not None:
            minutes = int(retry // 60) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"You've hit the hourly limit. Please try again in about {minutes} minutes.",
                headers={"Retry-After": str(int(retry) + 1)},
            )

    return dependency
