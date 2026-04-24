# Copyright (c) 2026 John Carter. All rights reserved.
"""
Management UI authentication — Google OAuth login flow for human users.

This is a separate, lighter-weight flow from the MCP OAuth 2.1 flow.
It issues short-lived management JWTs (typ=mgmt) stored in the browser's
localStorage, not in DynamoDB.

Routes:
  GET /auth/login    — redirect to Google (or issue bypass JWT in non-prod)
  GET /auth/callback — handle Google callback, upsert User, issue mgmt JWT
"""

from __future__ import annotations

import html
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from starter.auth.google import (
    exchange_google_code,
    google_authorization_url,
    is_admin_email,
    verify_google_id_token,
)
from starter.auth.tokens import ISSUER, issue_mgmt_jwt
from starter.logging_config import get_logger
from starter.models import User
from starter.storage import HiveStorage

router = APIRouter(tags=["mgmt-auth"])
logger = get_logger("hive.auth.mgmt_auth")

_BYPASS = bool(os.environ.get("HIVE_BYPASS_GOOGLE_AUTH"))

# Redirect target after successful login — the management UI root
_UI_ROOT = "/"


def _mgmt_callback_uri() -> str:
    return f"{ISSUER}/auth/callback"


def _html_redirect(jwt_token: str) -> HTMLResponse:
    """Return a minimal HTML page that writes the JWT to localStorage and redirects."""
    safe_token = html.escape(jwt_token, quote=True)
    body = (
        "<!DOCTYPE html><html><head><title>Logging in…</title></head><body>"
        "<script>"
        f"localStorage.setItem('hive_mgmt_token', '{safe_token}');"
        f"location.replace('{_UI_ROOT}');"
        "</script>"
        "<noscript>JavaScript is required to complete login.</noscript>"
        "</body></html>"
    )
    return HTMLResponse(content=body)


@router.get("/auth/login", include_in_schema=False)
async def mgmt_login(request: Request) -> RedirectResponse:
    """Redirect the management UI user to Google for authentication.

    In HIVE_BYPASS_GOOGLE_AUTH mode (non-prod), issue a synthetic JWT directly
    when a test_email query parameter is provided, so e2e tests can run without
    a real Google account.  Omitting test_email falls through to the real Google
    OAuth flow, allowing developers to log in with their actual identity in dev.
    """
    test_email = request.query_params.get("test_email")
    if _BYPASS and test_email:
        storage = HiveStorage()
        user = _upsert_user(storage, test_email, test_email.split("@")[0], test_email)
        token = issue_mgmt_jwt(user)
        return _html_redirect(token)  # type: ignore[return-value]

    storage = HiveStorage()
    pending = storage.create_mgmt_pending_state()
    url = google_authorization_url(pending.state, _mgmt_callback_uri())
    return RedirectResponse(url, status_code=302)


@router.get(
    "/auth/callback",
    include_in_schema=False,
    responses={400: {"description": "Invalid Google OAuth callback"}},
)
async def mgmt_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """Handle the Google OAuth callback for the management UI.

    Validates the nonce, exchanges the code, verifies the ID token,
    upserts the User record, and returns an HTML page that writes the
    management JWT to localStorage and redirects to the UI root.
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")

    storage = HiveStorage()

    # Validate and consume the nonce
    pending = storage.get_mgmt_pending_state(state)
    if pending is None:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    if datetime.now(timezone.utc) >= pending.expires_at:
        storage.delete_mgmt_pending_state(state)
        raise HTTPException(status_code=400, detail="Login session expired, please try again")
    storage.delete_mgmt_pending_state(state)

    # Exchange code → ID token → claims
    try:
        id_token = await exchange_google_code(code, _mgmt_callback_uri())
        claims = await verify_google_id_token(id_token)
    except Exception as exc:
        logger.warning("Google token exchange failed: %s", exc)
        raise HTTPException(status_code=400, detail="Failed to verify Google identity") from exc

    if not claims.get("email_verified"):
        raise HTTPException(status_code=400, detail="Google email is not verified")

    email: str = claims["email"]
    display_name: str = claims.get("name", email.split("@")[0])

    user = _upsert_user(storage, email, display_name, email)
    token = issue_mgmt_jwt(user)
    logger.info("Management login: %s (role=%s)", email, user.role)
    return _html_redirect(token)


def _upsert_user(storage: HiveStorage, email: str, display_name: str, _email: str) -> User:
    """Create or update the User record for a given email."""
    now = datetime.now(timezone.utc)
    user = storage.get_user_by_email(email)
    if user is None:
        role = "admin" if is_admin_email(email) else "user"
        user = User(email=email, display_name=display_name, role=role, created_at=now)
        logger.info("New user registered: %s (role=%s)", email, role)
    else:
        user.display_name = display_name
        # Re-evaluate admin status in case the allowlist was updated
        user.role = "admin" if is_admin_email(email) else "user"
    user.last_login_at = now
    storage.put_user(user)
    return user
