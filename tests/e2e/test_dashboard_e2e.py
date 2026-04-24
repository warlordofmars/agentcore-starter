# Copyright (c) 2026 John Carter. All rights reserved.
"""
Playwright E2E tests for the Hive Dashboard UI (admin-only).
Must run in its own pytest invocation — mixing with async test files causes
pytest-asyncio to start an event loop that blocks sync_playwright().
Requires:
  HIVE_UI_URL        — deployed UI URL (CloudFront)
  HIVE_ADMIN_EMAIL   — admin email for Google auth bypass
"""

from __future__ import annotations

import os

import pytest

UI_URL = os.environ.get("HIVE_UI_URL", "")
ADMIN_EMAIL = os.environ.get("HIVE_ADMIN_EMAIL", "")

pytestmark = pytest.mark.skipif(
    not UI_URL,
    reason="HIVE_UI_URL not set — skipping dashboard e2e tests",
)


@pytest.fixture(scope="module")
def admin_browser_page():
    """Browser page logged in as an admin user via the Google auth bypass."""
    if not ADMIN_EMAIL:
        pytest.skip("HIVE_ADMIN_EMAIL not set — skipping admin UI e2e tests")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        # #619: pre-dismiss the onboarding tour so its viewport-
        # covering backdrop doesn't intercept tab clicks.
        context.add_init_script("localStorage.setItem('hive_tour_dismissed', '1');")
        page = context.new_page()

        page.goto(
            f"{UI_URL}/auth/login?test_email={ADMIN_EMAIL}",
            timeout=30_000,
            wait_until="networkidle",
        )
        page.goto(f"{UI_URL}/app", timeout=30_000, wait_until="networkidle")

        yield page
        context.close()
        browser.close()


class TestDashboardE2E:
    def test_dashboard_tab_visible_for_admin(self, admin_browser_page):
        page = admin_browser_page
        page.goto(f"{UI_URL}/app", timeout=30_000, wait_until="networkidle")
        assert page.locator("nav button:has-text('Dashboard')").is_visible()

    def test_dashboard_renders_without_error(self, admin_browser_page):
        page = admin_browser_page
        page.locator("nav button:has-text('Dashboard')").click()
        page.wait_for_load_state("networkidle")
        # No error banner should be present after metrics load
        assert not page.locator("text=Failed to load metrics").is_visible()
        assert not page.locator("text=Failed to load costs").is_visible()

    def test_dashboard_period_selector(self, admin_browser_page):
        page = admin_browser_page
        page.locator("nav button:has-text('Dashboard')").click()
        page.wait_for_load_state("networkidle")
        # Switch through all period options — none should trigger an error banner
        for period in ("1h", "7d", "30d", "24h"):
            page.locator(f"button:has-text('{period}')").click()
            page.wait_for_load_state("networkidle")
            assert not page.locator("text=Failed to load metrics").is_visible(), (
                f"Error banner appeared after switching to {period}"
            )

    def test_cost_section_renders_without_error(self, admin_browser_page):
        """Cost section must reach a resolved state — data, placeholder, or error banner."""
        page = admin_browser_page
        page.locator("nav button:has-text('Dashboard')").click()
        page.wait_for_load_state("networkidle")
        # networkidle can fire before React's useEffect has started the fetch calls.
        # Wait until all loading skeletons (divs with pulse animation) disappear, which
        # confirms the cost API calls have completed (success or error).
        page.wait_for_function(
            "() => [...document.querySelectorAll('div')]"
            "  .every(d => !d.style.animation || !d.style.animation.includes('pulse'))",
            timeout=15000,
        )
        # Cost section heading is present
        assert page.locator("text=Monthly AWS Spend").is_visible()
        # Section must be in one of three valid resolved states (not a stuck spinner):
        #   1. recharts chart is rendered (costs loaded with data)
        #   2. "no data" placeholder is visible (costs loaded but empty)
        #   3. error banner is visible (costs API failed, but UI handled it gracefully)
        has_data = page.locator(".recharts-responsive-container").count() > 0
        has_placeholder = (
            page.locator("text=No cost data available yet.").is_visible()
            or page.locator("text=No daily cost data available yet.").is_visible()
        )
        # CSS attribute selectors don't reliably match React inline-style CSS custom
        # properties in Chromium, so evaluate via JavaScript instead.
        has_error = page.evaluate(
            "() => [...document.querySelectorAll('div')].some("
            "  d => d.style.color === 'var(--danger)'"
            ")"
        )
        assert has_data or has_placeholder or has_error, (
            "Cost section shows neither a chart, a no-data placeholder, nor an error banner — "
            "the spinner may be stuck or the section failed silently"
        )
