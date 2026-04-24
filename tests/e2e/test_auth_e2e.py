# Copyright (c) 2026 John Carter. All rights reserved.
"""
E2E tests for the deployed OAuth 2.1 authorization server.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets

import pytest

API_URL = os.environ.get("HIVE_API_URL")

pytestmark = pytest.mark.skipif(
    not API_URL,
    reason="HIVE_API_URL not set — skipping e2e tests",
)


def _pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


@pytest.mark.asyncio
class TestOAuthE2E:
    async def test_discovery_document(self):
        import httpx

        async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as http:
            resp = await http.get("/.well-known/oauth-authorization-server")
            assert resp.status_code == 200
            data = resp.json()
            assert "authorization_endpoint" in data
            assert "token_endpoint" in data
            assert "S256" in data["code_challenge_methods_supported"]

    async def test_dcr_and_token_flow(self):
        import httpx

        async with httpx.AsyncClient(
            base_url=API_URL, follow_redirects=False, timeout=30.0
        ) as http:
            # Register
            reg = await http.post(
                "/oauth/register",
                json={"client_name": "E2E Client", "redirect_uris": ["http://localhost/cb"]},
            )
            assert reg.status_code == 201
            client_id = reg.json()["client_id"]

            # Authorize
            verifier, challenge = _pkce_pair()
            auth = await http.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": "http://localhost/cb",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                },
            )
            assert auth.status_code == 302
            location = auth.headers.get("location", "")
            if "accounts.google.com" in location:
                pytest.skip(
                    "Google OAuth required — cannot complete token flow in CI without bypass"
                )
            code = location.split("code=")[1].split("&")[0]

            # Exchange
            token = await http.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": "http://localhost/cb",
                    "client_id": client_id,
                    "code_verifier": verifier,
                },
            )
            assert token.status_code == 200
            assert token.json()["access_token"]
