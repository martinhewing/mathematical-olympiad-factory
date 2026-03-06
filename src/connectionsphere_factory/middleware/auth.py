"""
connectionsphere_factory/middleware/auth.py
API key authentication. Uses hmac.compare_digest — constant-time comparison
prevents timing attacks. Public routes are explicitly allowlisted.

Session UI routes (/session/*/stage/*, /session/*/state, etc.) are public —
they are browser-rendered interview pages that cannot send custom headers.
API management routes (/sessions) remain protected.
"""
from __future__ import annotations
import hmac
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from connectionsphere_factory.config import get_settings

_PUBLIC_PATHS = frozenset({
    "/health",
    "/favicon.ico",
    "/docs",
    "/openapi.json",
    "/",
})

# Browser-rendered interview UI — cannot send X-API-Key headers
_PUBLIC_PREFIXES = (
    "/session/",   # /session/{id}/stage/{n}, /session/{id}/state, etc.
)


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path in _PUBLIC_PATHS:
            return await call_next(request)

        if any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
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
