"""
connectionsphere_factory/middleware/auth.py

API key authentication. Uses hmac.compare_digest — constant-time comparison
prevents timing attacks. Public routes are explicitly allowlisted.
"""

from __future__ import annotations

import hmac

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from connectionsphere_factory.config import get_settings

_PUBLIC_PATHS = frozenset({
    "/health",
    "/docs",
    "/openapi.json",
    "/",
})


class APIKeyMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        key = request.headers.get("X-API-Key", "")

        if not key:
            return JSONResponse(
                status_code = 401,
                content     = {"detail": "X-API-Key header required"},
            )

        if not _verify_key(key):
            return JSONResponse(
                status_code = 403,
                content     = {"detail": "Invalid API key"},
            )

        return await call_next(request)


def _verify_key(provided: str) -> bool:
    expected = get_settings().factory_api_key
    if not expected:
        return False
    return hmac.compare_digest(
        provided.encode("utf-8"),
        expected.encode("utf-8"),
    )
