"""
connectionsphere_factory/app.py

FastAPI application factory.

Middleware order — Starlette applies last-registered-first:
  Request:   RequestLogging -> RateLimit -> APIKey -> CORS -> route handler
  Response:  route handler  -> CORS -> APIKey -> RateLimit -> RequestLogging
"""

from __future__ import annotations

import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
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

    # ── Favicon (public) ──────────────────────────────────────────────────
    _favicon = pathlib.Path(__file__).parent / "static" / "favicon.png"

    @app.get("/favicon.ico", include_in_schema=False)
    @app.get("/favicon.png", include_in_schema=False)
    async def favicon():
        return Response(content=_favicon.read_bytes(), media_type="image/png")

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
  <link rel="icon" type="image/png" href="/favicon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,400;0,500;1,400&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; background: #0a0a0a; }}

    /* ── Scalar CSS variable overrides ─────────────────────────── */
    :root,
    .light-mode,
    .dark-mode,
    [data-theme],
    .scalar-app {{
      --scalar-color-1:                        #f0f0f0 !important;
      --scalar-color-2:                        #999999 !important;
      --scalar-color-3:                        #555555 !important;
      --scalar-color-accent:                   #c8ff00 !important;
      --scalar-background-1:                   #0a0a0a !important;
      --scalar-background-2:                   #111111 !important;
      --scalar-background-3:                   #1a1a1a !important;
      --scalar-background-4:                   #222222 !important;
      --scalar-border-color:                   #222222 !important;
      --scalar-button-1:                       #c8ff00 !important;
      --scalar-button-1-color:                 #000000 !important;
      --scalar-button-1-hover:                 #d4ff33 !important;
      --scalar-color-green:                    #00ff88 !important;
      --scalar-color-red:                      #ff4444 !important;
      --scalar-color-orange:                   #ffaa00 !important;
      --scalar-color-yellow:                   #ffaa00 !important;
      --scalar-color-blue:                     #6699ff !important;
      --scalar-color-purple:                   #c8ff00 !important;
      --scalar-sidebar-background-1:           #0a0a0a !important;
      --scalar-sidebar-background-2:           #111111 !important;
      --scalar-sidebar-item-hover-background:  #1a1a1a !important;
      --scalar-sidebar-item-active-background: #1a1a1a !important;
      --scalar-sidebar-color-1:                #f0f0f0 !important;
      --scalar-sidebar-color-2:                #666666 !important;
      --scalar-sidebar-color-active:           #c8ff00 !important;
      --scalar-sidebar-border-color:           #1a1a1a !important;
      --scalar-sidebar-search-background:      #111111 !important;
      --scalar-font:                           'DM Sans', sans-serif !important;
      --scalar-font-code:                      'DM Mono', monospace !important;
    }}

    /* Title */
    h1 {{ color: #c8ff00 !important; }}

    /* Force dark background on scalar root elements */
    .scalar-app,
    .references-layout,
    .references-navigation,
    .scalar-api-reference {{
      background: #0a0a0a !important;
      color: #f0f0f0 !important;
      font-family: 'DM Sans', sans-serif !important;
    }}

    /* Sidebar */
    .sidebar,
    .t-doc__sidebar {{
      background: #0a0a0a !important;
      border-right: 1px solid #222 !important;
    }}

    /* Active nav item accent */
    .sidebar-item--active,
    .sidebar-item.active {{
      color: #c8ff00 !important;
      border-left-color: #c8ff00 !important;
    }}

    /* Code blocks */
    .code-block, pre, code {{
      background: #111111 !important;
      font-family: 'DM Mono', monospace !important;
    }}

    /* Buttons */
    .btn-primary, .scalar-button-primary {{
      background: #c8ff00 !important;
      color: #000 !important;
    }}

    /* Method badges */
    .badge-get    {{ background: rgba(102,153,255,0.15) !important; color: #6699ff !important; }}
    .badge-post   {{ background: rgba(0,255,136,0.12)  !important; color: #00ff88 !important; }}
    .badge-put    {{ background: rgba(255,170,0,0.12)  !important; color: #ffaa00 !important; }}
    .badge-delete {{ background: rgba(255,68,68,0.12)  !important; color: #ff4444 !important; }}
  </style>
</head>
<body>
  <script
    id="api-reference"
    data-url="/openapi.json"
    data-configuration='{{"theme":"none","layout":"modern","darkMode":true,"defaultHttpClient":{{"targetKey":"python","clientKey":"requests"}}}}'
  ></script>
  <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>"""


app = create_app()