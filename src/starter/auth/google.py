# Copyright (c) 2026 John Carter. All rights reserved.
"""
Google OAuth 2.0 integration for Hive.

Hive uses Google as an identity provider for human-facing login while keeping
its own OAuth 2.1 stack intact for MCP clients.  The flow is:

  1. /oauth/authorize → redirect to Google
  2. Google → /oauth/google/callback (this module handles the callback)
  3. Hive verifies the Google ID token + checks email allowlist
  4. Hive creates its own AuthorizationCode and redirects to the original redirect_uri

Configuration (env vars or SSM parameters):
  GOOGLE_CLIENT_ID / GOOGLE_CLIENT_ID_PARAM
  GOOGLE_CLIENT_SECRET / GOOGLE_CLIENT_SECRET_PARAM
  ALLOWED_EMAILS / ALLOWED_EMAILS_PARAM  (JSON array; empty = allow all)
"""

from __future__ import annotations

import functools
import json
import os
from typing import Any
from urllib.parse import urlencode

import httpx
from jose import jwt as jose_jwt

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUER = "https://accounts.google.com"


def _ssm_param(name: str) -> str:
    import boto3

    ssm = boto3.client("ssm")
    resp = ssm.get_parameter(Name=name, WithDecryption=True)
    return resp["Parameter"]["Value"]


@functools.lru_cache(maxsize=1)
def _google_client_id() -> str:
    if val := os.environ.get("GOOGLE_CLIENT_ID"):
        return val
    return _ssm_param(os.environ.get("GOOGLE_CLIENT_ID_PARAM", "/hive/google-client-id"))


@functools.lru_cache(maxsize=1)
def _google_client_secret() -> str:
    if val := os.environ.get("GOOGLE_CLIENT_SECRET"):
        return val
    return _ssm_param(os.environ.get("GOOGLE_CLIENT_SECRET_PARAM", "/hive/google-client-secret"))


@functools.lru_cache(maxsize=1)
def _allowed_emails() -> frozenset[str]:
    if val := os.environ.get("ALLOWED_EMAILS"):
        return frozenset(json.loads(val))
    try:
        raw = _ssm_param(os.environ.get("ALLOWED_EMAILS_PARAM", "/hive/allowed-emails"))
        return frozenset(json.loads(raw))
    except Exception:
        return frozenset()  # empty = allow all (open)


def google_authorization_url(state: str, callback_uri: str) -> str:
    """Build the Google OAuth authorization URL to redirect the user to."""
    params = {
        "client_id": _google_client_id(),
        "response_type": "code",
        "scope": "openid email",
        "redirect_uri": callback_uri,
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_google_code(code: str, callback_uri: str) -> str:
    """Exchange a Google authorization code for an ID token string."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": _google_client_id(),
                "client_secret": _google_client_secret(),
                "redirect_uri": callback_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return str(resp.json()["id_token"])


async def fetch_google_jwks() -> dict[str, Any]:
    """Fetch Google's current public keys (JWKS)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(GOOGLE_JWKS_URL)
        resp.raise_for_status()
        return dict(resp.json())


async def verify_google_id_token(id_token: str) -> dict[str, Any]:
    """Decode and verify a Google ID token; return its claims.

    Raises jose.JWTError on verification failure.
    """
    jwks = await fetch_google_jwks()
    claims: dict[str, Any] = jose_jwt.decode(
        id_token,
        jwks,
        algorithms=["RS256"],
        audience=_google_client_id(),
        issuer=GOOGLE_ISSUER,
        options={"verify_at_hash": False},
    )
    return claims


def is_email_allowed(email: str) -> bool:
    """Return True if the email is permitted to access Hive.

    An empty allowlist means open access (allow all verified Google accounts).
    """
    allowed = _allowed_emails()
    if not allowed:
        return True
    return email in allowed


def is_admin_email(email: str) -> bool:
    """Return True if this email gets the admin role.

    Only emails explicitly listed in ALLOWED_EMAILS / ALLOWED_EMAILS_PARAM
    receive admin.  An empty allowlist means no admins (not 'everyone is admin').
    """
    return email in _allowed_emails()
