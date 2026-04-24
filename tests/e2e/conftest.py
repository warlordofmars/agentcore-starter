# Copyright (c) 2026 John Carter. All rights reserved.
"""
Shared e2e fixtures.
"""

from __future__ import annotations

import base64
import hashlib
import html as html_lib
import os
import re
import secrets

import httpx
import pytest

API_URL = os.environ.get("HIVE_API_URL", "")
ADMIN_EMAIL = os.environ.get("HIVE_ADMIN_EMAIL", "")
E2E_EMAIL = os.environ.get("HIVE_E2E_EMAIL", "")

# The deployed API runs on AWS Lambda, and the first request after a quiet
# period pays a cold-start cost that can run 5–10s on a fresh container. The
# httpx default 5s read timeout occasionally flakes the very first DCR call
# in a test run; bumping to 30s comfortably absorbs that without masking real
# backend slowness.
_E2E_TIMEOUT = 30.0


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


async def _issue_token(client_name: str) -> str:
    """Issue a fresh access token via DCR + PKCE.

    Raises pytest.fail (not skip) if the server redirects to Google, since
    HIVE_BYPASS_GOOGLE_AUTH must be active in any environment where MCP e2e
    tests are expected to run.
    """
    if not API_URL:
        pytest.skip("HIVE_API_URL not set")

    verifier, challenge = _pkce_pair()

    async with httpx.AsyncClient(
        base_url=API_URL, follow_redirects=False, timeout=_E2E_TIMEOUT
    ) as http:
        reg = await http.post(
            "/oauth/register",
            json={"client_name": client_name, "redirect_uris": ["http://localhost/cb"]},
        )
        reg.raise_for_status()
        client_id = reg.json()["client_id"]

        authorize_params: dict[str, str] = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": "http://localhost/cb",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if E2E_EMAIL:
            authorize_params["test_email"] = E2E_EMAIL
        auth = await http.get("/oauth/authorize", params=authorize_params)
        location = auth.headers.get("location", "")
        if "accounts.google.com" in location:
            pytest.fail(
                "Google OAuth redirect — HIVE_BYPASS_GOOGLE_AUTH must be enabled "
                "in any environment where MCP e2e tests are expected to run."
            )
        code = location.split("code=")[1].split("&")[0]

        token_resp = await http.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "http://localhost/cb",
                "client_id": client_id,
                "code_verifier": verifier,
            },
        )
        token_resp.raise_for_status()
        return token_resp.json()["access_token"]


@pytest.fixture(scope="function")
async def live_token() -> str:
    """Issue a fresh access token via DCR + PKCE against the deployed API."""
    return await _issue_token("E2E Session Client")


@pytest.fixture(scope="function")
async def live_token_b() -> str:
    """Issue a second fresh access token from a distinct OAuth client registration.

    Used by isolation tests to verify that two separate clients cannot access
    each other's memories.
    """
    return await _issue_token("E2E Session Client B")


def issue_token_sync() -> str:
    """Synchronous version for use in non-async fixtures (e.g. Playwright browser_page)."""
    if not API_URL:
        pytest.skip("HIVE_API_URL not set")

    verifier, challenge = _pkce_pair()

    with httpx.Client(base_url=API_URL, follow_redirects=False, timeout=_E2E_TIMEOUT) as http:
        reg = http.post(
            "/oauth/register",
            json={"client_name": "E2E UI Client", "redirect_uris": ["http://localhost/cb"]},
        )
        reg.raise_for_status()
        client_id = reg.json()["client_id"]

        auth = http.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": "http://localhost/cb",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
        location = auth.headers.get("location", "")
        if "accounts.google.com" in location:
            pytest.skip("Google OAuth required — cannot complete token flow in CI without bypass")
        code = location.split("code=")[1].split("&")[0]

        token_resp = http.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "http://localhost/cb",
                "client_id": client_id,
                "code_verifier": verifier,
            },
        )
        token_resp.raise_for_status()
        return token_resp.json()["access_token"]


@pytest.fixture(scope="function")
async def live_admin_token() -> str:
    """Issue a management JWT with admin role via the Google auth bypass.

    Hits /auth/login?test_email=<HIVE_ADMIN_EMAIL> and parses the JWT from
    the HTML response.  Skips if the env var is not set or if the server
    redirects to Google (bypass not enabled).
    """
    if not API_URL:
        pytest.skip("HIVE_API_URL not set")
    if not ADMIN_EMAIL:
        pytest.skip("HIVE_ADMIN_EMAIL not set")

    async with httpx.AsyncClient(
        base_url=API_URL, follow_redirects=False, timeout=_E2E_TIMEOUT
    ) as http:
        resp = await http.get("/auth/login", params={"test_email": ADMIN_EMAIL})
        if resp.status_code in (301, 302, 307, 308):
            pytest.skip("Google OAuth redirect — HIVE_BYPASS_GOOGLE_AUTH not enabled")
        resp.raise_for_status()
        m = re.search(r"localStorage\.setItem\('hive_mgmt_token',\s*'([^']+)'\)", resp.text)
        if not m:
            pytest.fail("Could not extract mgmt token from bypass login response")
        return html_lib.unescape(m.group(1))
