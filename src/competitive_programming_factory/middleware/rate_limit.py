"""
competitive_programming_factory/middleware/rate_limit.py

Per-key sliding window rate limiter on Claude-calling endpoints.
In-memory for the skeleton — swap _windows for Redis before adding workers.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from competitive_programming_factory.config import get_settings

_WINDOW_SECONDS = 3600
_windows: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _group(path: str) -> str | None:
    if path.endswith("/sessions"):
        return "sessions"
    if path.endswith("/submit"):
        return "submits"
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method != "POST":
            return await call_next(request)

        group = _group(request.url.path)
        if group is None:
            return await call_next(request)

        s = get_settings()
        limit = s.rate_limit_sessions_per_hour if group == "sessions" else s.rate_limit_submits_per_hour
        api_key = request.headers.get("X-API-Key", "anon")
        key = (api_key, group)
        now = time.monotonic()
        window = _windows[key]

        while window and window[0] < now - _WINDOW_SECONDS:
            window.popleft()

        if len(window) >= limit:
            retry_after = int(_WINDOW_SECONDS - (now - window[0]))
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit: {limit} requests/hour on {group}",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)
        return await call_next(request)
