"""Request hardening for the API (Task 32): rate limits and security headers.

Rate limits are per client address, in three buckets with sliding one-minute or one-hour
windows: uploads (lecture and deck uploads, the expensive ones), other writes (review, cancel,
retry) and reads (including the video and audio the player streams). Health checks are never
limited. The limiter keeps its counts in memory: correct for the single API process this app
deploys with; several processes would each count separately. Behind the Caddy proxy, set
`trust_proxy_headers` so the client address comes from `X-Forwarded-For` (Caddy overwrites it).

Every response carries headers that stop browsers from sniffing types, framing the API,
leaking referrers or loading its files from other sites.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from seehere.core.config import Settings

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-site",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
DOCS_PATHS = ("/api/docs", "/api/openapi.json")  # Swagger UI needs its own scripts


@dataclass(frozen=True)
class Limit:
    bucket: str
    requests: int
    window_s: float


class RateLimiter:
    """Sliding-window counter per (client, bucket). Thread-safe."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()
        self._clock = clock

    def check(self, client: str, limit: Limit) -> float:
        """Record a request. Returns 0 if allowed, else seconds until one is allowed."""
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault((client, limit.bucket), deque())
            while hits and hits[0] <= now - limit.window_s:
                hits.popleft()
            if len(hits) >= limit.requests:
                return max(0.001, hits[0] + limit.window_s - now)
            hits.append(now)
            if len(self._hits) > 10_000:  # forget idle clients so memory stays bounded
                for key in [k for k, v in self._hits.items() if not v]:
                    del self._hits[key]
            return 0.0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def _is_upload(method: str, path: str) -> bool:
    """POST /api/projects (a lecture) or POST /api/projects/{id}/deck (a slide deck)."""
    parts = path.rstrip("/").split("/")
    return method == "POST" and (
        parts == ["", "api", "projects"]
        or (len(parts) == 5 and parts[1:3] == ["api", "projects"] and parts[4] == "deck")
    )


def limit_for(settings: Settings, method: str, path: str) -> Limit | None:
    if not settings.rate_limit_enabled or path.startswith("/api/health"):
        return None
    if _is_upload(method, path):
        return Limit("upload", settings.rate_limit_uploads_per_hour, 3600.0)
    if method in ("POST", "PATCH", "PUT", "DELETE"):
        return Limit("write", settings.rate_limit_writes_per_minute, 60.0)
    return Limit("read", settings.rate_limit_reads_per_minute, 60.0)


def client_address(request: Request, settings: Settings) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def install_security(app: FastAPI, settings_of: Callable[[], Settings]) -> RateLimiter:
    """Add the middleware. `settings_of` is called per request, so tests and dependency
    overrides can change the limits without rebuilding the app."""
    limiter = RateLimiter()

    @app.middleware("http")
    async def harden(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = settings_of()
        limit = (
            None
            if request.method == "OPTIONS"
            else limit_for(settings, request.method, request.url.path)
        )
        if limit is not None:
            wait = limiter.check(client_address(request, settings), limit)
            if wait:
                response: Response = JSONResponse(
                    {
                        "error": {
                            "code": "rate_limited",
                            "message": "Too many requests. Please wait and try again.",
                        }
                    },
                    status_code=429,
                    headers={"Retry-After": str(math.ceil(wait))},
                )
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            if name == "Content-Security-Policy" and request.url.path.startswith(DOCS_PATHS):
                continue
            response.headers.setdefault(name, value)
        return response

    return limiter
