# Copyright (c) 2026 John Carter. All rights reserved.
"""
Shared e2e test fixtures.

E2e tests run against a deployed (or local dev) stack.
Required env vars:
  STARTER_API_URL  — base URL of the management API
  STARTER_UI_URL   — base URL of the React UI (for Playwright tests)
  STARTER_ADMIN_EMAIL — email address that receives admin role in the test env
"""

from __future__ import annotations

import os
import re
import html as html_lib

import httpx
import pytest

API_URL = os.environ.get("STARTER_API_URL", "")
UI_URL = os.environ.get("STARTER_UI_URL", "")
ADMIN_EMAIL = os.environ.get("STARTER_ADMIN_EMAIL", "")

_E2E_TIMEOUT = 30.0


@pytest.fixture(scope="function")
async def live_admin_token() -> str:
    """Issue a management JWT with admin role via the Google auth bypass.

    Hits /auth/login?test_email=<STARTER_ADMIN_EMAIL> and parses the JWT
    from the HTML response.  Skips if the bypass is not enabled on the server.
    """
    if not API_URL:
        pytest.skip("STARTER_API_URL not set")
    if not ADMIN_EMAIL:
        pytest.skip("STARTER_ADMIN_EMAIL not set")

    async with httpx.AsyncClient(
        base_url=API_URL, follow_redirects=False, timeout=_E2E_TIMEOUT
    ) as http:
        resp = await http.get("/auth/login", params={"test_email": ADMIN_EMAIL})
        if resp.status_code in (301, 302, 307, 308):
            pytest.skip("Google OAuth redirect — STARTER_BYPASS_GOOGLE_AUTH not enabled")
        resp.raise_for_status()
        m = re.search(r"localStorage\.setItem\('starter_mgmt_token',\s*'([^']+)'\)", resp.text)
        if not m:
            pytest.fail("Could not extract mgmt token from bypass login response")
        return html_lib.unescape(m.group(1))
