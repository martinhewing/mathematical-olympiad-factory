"""
competitive_programming_factory/middleware/request_logging.py

One structured log line per HTTP request.
request_id bound to structlog context — all log calls in the request inherit it.
"""

from __future__ import annotations

import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from competitive_programming_factory.logging import (
    bind_request_context,
    clear_request_context,
    get_logger,
)

log = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid.uuid4().hex[:8]
        api_key = request.headers.get("X-API-Key", "")
        api_key_id = api_key[:8] if api_key else "none"

        bind_request_context(
            request_id=request_id,
            api_key_id=api_key_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            log.error("http.request", status_code=500, duration_ms=duration_ms)
            clear_request_context()
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)
        level = "warning" if response.status_code >= 400 else "info"
        log.info(
            "http.request",
            status_code=response.status_code,
            duration_ms=duration_ms,
            _level=level,
        )

        clear_request_context()
        return response
