"""
connectionsphere_factory/app.py

FastAPI application factory.

Middleware order — Starlette applies last-registered-first:
  Request:   RequestLogging -> RateLimit -> APIKey -> CORS -> route handler
  Response:  route handler  -> CORS -> APIKey -> RateLimit -> RequestLogging
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from connectionsphere_factory.config import get_settings
from connectionsphere_factory.logging import configure_logging, get_logger
from connectionsphere_factory.middleware.auth import APIKeyMiddleware
from connectionsphere_factory.middleware.rate_limit import RateLimitMiddleware
from connectionsphere_factory.middleware.request_logging import RequestLoggingMiddleware
from connectionsphere_factory.routes import sessions, stages, state, visualize, voice


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(
        log_level   = settings.log_level,
        json_format = settings.json_logs,
    )
    log = get_logger(__name__)
    log.info("factory.startup", model=settings.anthropic_model, debug=settings.debug)
    yield
    log.info("factory.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title       = "ConnectionSphere — System Design Factory",
        version     = "0.1.0",
        description = (
            "FAANG-level system design interview simulator.\n\n"
            "## Quick start\n"
            "1. **Authenticate** — enter your `FACTORY_API_KEY` in the auth panel above\n"
            "2. **Create a session** — `POST /sessions` with a problem statement\n"
            "3. **Read the scene** — note the `session_id` and `stage_url` returned\n"
            "4. **Get stage 1** — `GET /session/{session_id}/stage/1` — read the opening question\n"
            "5. **Submit your answer** — `POST /session/{session_id}/stage/1/submit`\n"
            "6. **Follow `next_url`** — advance through stages until `evaluate`\n\n"
            "---\n"
            "The interviewer sets the scene. You ask clarifying questions. "
            "Claude assesses your answers and probes until concepts are confirmed."
        ),
        lifespan    = lifespan,
        docs_url    = None,
        redoc_url   = None,
        debug       = settings.debug,
    )

    # ── Middleware (registered last → runs first) ─────────────────────────
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(APIKeyMiddleware)

    origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins     = origins,
            allow_credentials = False,
            allow_methods     = ["GET", "POST"],
            allow_headers     = ["X-API-Key", "Content-Type"],
        )

    # ── Routes ────────────────────────────────────────────────────────────
    app.include_router(sessions.router)
    app.include_router(stages.router)
    app.include_router(state.router)
    app.include_router(visualize.router)
    app.include_router(voice.router)

    # ── OpenAPI — declare X-API-Key security scheme ───────────────────────
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title       = app.title,
            version     = app.version,
            description = app.description,
            routes      = app.routes,
        )
        schema["components"]["securitySchemes"] = {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in":   "header",
                "name": "X-API-Key",
            }
        }
        schema["security"] = [{"ApiKeyAuth": []}]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi

    # ── Scalar docs (public) ──────────────────────────────────────────────
    @app.get("/docs", include_in_schema=False)
    def scalar_docs():
        return HTMLResponse(content=_scalar_html(app.title))

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/docs")

    # ── Health (public) ───────────────────────────────────────────────────
    @app.get("/health", tags=["meta"])
    def health():
        checks  = _run_health_checks()
        healthy = all(v for v in checks.values())
        return JSONResponse(
            status_code = 200 if healthy else 503,
            content     = {
                "status": "ok" if healthy else "degraded",
                **({}  if healthy else {"checks": checks}),
            },
        )

    return app


def _run_health_checks() -> dict[str, bool]:
    settings = get_settings()
    checks: dict[str, bool] = {}

    if not settings.anthropic_api_key:
        get_logger(__name__).warning("health.anthropic_key_missing")
    checks["anthropic_key_configured"] = True

    try:
        import connectionsphere_factory.session_store as store
        store.list_all()
        checks["session_store"] = True
    except Exception:
        checks["session_store"] = False

    return checks


def _scalar_html(title: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <title>{title}</title>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body>
  <script
    id="api-reference"
    data-url="/openapi.json"
    data-configuration='{{"theme":"purple","layout":"modern","defaultHttpClient":{{"targetKey":"python","clientKey":"requests"}}}}'
  ></script>
  <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>"""


app = create_app()
