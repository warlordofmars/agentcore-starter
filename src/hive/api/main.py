# Copyright (c) 2026 John Carter. All rights reserved.
"""
Hive management FastAPI application.

Runs on port 8001 in development.
All /api/* routes require a valid OAuth 2.1 Bearer token.
OAuth endpoints (/oauth/*, /.well-known/*) are public.
"""

from __future__ import annotations

import importlib.metadata
import os
import time
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse

from hive.api._auth import require_admin
from hive.api.account import router as account_router
from hive.api.admin import router as admin_router
from hive.api.clients import router as clients_router
from hive.api.csp import router as csp_router
from hive.api.keys import router as keys_router
from hive.api.logs import router as logs_router
from hive.api.memories import router as memories_router
from hive.api.stats import router as stats_router
from hive.api.users import router as users_router
from hive.api.versions import router as versions_router
from hive.auth.mgmt_auth import router as mgmt_auth_router
from hive.auth.oauth import router as oauth_router
from hive.logging_config import configure_logging, get_logger, new_request_id, set_request_context

configure_logging("api")
logger = get_logger("hive.api")


# APP_VERSION is injected at deploy time via Lambda env var.
# Falls back to the installed package version, then "dev" for local runs.
def _app_version() -> str:
    if v := os.environ.get("APP_VERSION"):
        return v
    try:
        return importlib.metadata.version("hive")
    except importlib.metadata.PackageNotFoundError:
        return "dev"


APP_VERSION = _app_version()

app = FastAPI(
    title="Hive Management API",
    version=APP_VERSION,
    description="REST API for managing Hive memories, OAuth clients, and viewing activity stats.",
    docs_url=None,
    redoc_url=None,
)

# Allow the React dev server (port 5173) and any configured UI origin
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _log_requests(request: Request, call_next):
    """Log every request with method, path, status code, and duration."""
    request_id = (
        request.headers.get("x-amzn-requestid")
        or request.headers.get("x-request-id")
        or new_request_id()
    )
    set_request_context(request_id)

    t0 = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - t0) * 1000)

    level = "warning" if response.status_code >= 400 else "info"
    getattr(logger, level)(
        "%s %s %d",
        request.method,
        request.url.path,
        response.status_code,
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.middleware("http")
async def _verify_origin_secret(request: Request, call_next):
    """Reject requests missing the CloudFront X-Origin-Verify secret.

    Disabled when HIVE_ORIGIN_VERIFY_PARAM is not set (local dev / non-prod).
    The placeholder value also disables the check so a fresh deploy without
    a rotated secret does not lock out traffic.
    """
    from hive.auth.tokens import _origin_verify_secret

    expected = _origin_verify_secret()
    if (
        expected
        and expected != "CHANGE_ME_ON_FIRST_DEPLOY"
        and request.headers.get("x-origin-verify") != expected
    ):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=403, content={"detail": "Forbidden"})
    return await call_next(request)


# OAuth 2.1 endpoints (unauthenticated)
app.include_router(oauth_router)

# Management UI auth endpoints (unauthenticated — issues mgmt JWTs)
app.include_router(mgmt_auth_router)

# Management API endpoints (Bearer token required)
app.include_router(memories_router, prefix="/api")
app.include_router(versions_router, prefix="/api")
app.include_router(clients_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(keys_router, prefix="/api")
app.include_router(account_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(logs_router, prefix="/api")

# Browser CSP report receiver — unauthenticated by design
# (browsers don't send credentials with CSP POSTs). Per-IP rate-limited.
app.include_router(csp_router, prefix="/api")


@app.get("/docs", include_in_schema=False)
async def swagger_ui(_claims: dict = Depends(require_admin)) -> HTMLResponse:
    """Swagger UI — admin only."""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Hive Management API")


@app.get("/redoc", include_in_schema=False)
async def redoc_ui(_claims: dict = Depends(require_admin)) -> HTMLResponse:
    """ReDoc UI — admin only."""
    return get_redoc_html(openapi_url="/openapi.json", title="Hive Management API")


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:  # pragma: no cover
    """AWS Lambda + Function URL handler for the management API."""
    try:
        from mangum import Mangum
    except ImportError as exc:
        raise RuntimeError("mangum is required for Lambda deployment") from exc

    handler = Mangum(app, lifespan="off")
    return handler(event, context)  # type: ignore[arg-type]
