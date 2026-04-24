# Copyright (c) 2026 John Carter. All rights reserved.
"""
Playwright E2E tests for the Hive management UI.
Requires:
  HIVE_UI_URL   — deployed UI URL (CloudFront)
  HIVE_API_URL  — deployed API URL (used to prime the session via bypass login)
"""

from __future__ import annotations

import os

import pytest

UI_URL = os.environ.get("HIVE_UI_URL", "")
API_URL = os.environ.get("HIVE_API_URL", "")

pytestmark = pytest.mark.skipif(
    not UI_URL,
    reason="HIVE_UI_URL not set — skipping UI e2e tests",
)


@pytest.fixture(scope="module")
def browser_page():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()

        # #619 shipped an OnboardingTour that renders a full-viewport
        # backdrop with pointer-events-auto on first visit — its
        # "click outside to dismiss" behaviour intercepts every
        # nav-tab click until it's dismissed. An `add_init_script`
        # pre-sets the dismissed flag on every page that loads in
        # this context so e2e tests never see the overlay.
        context.add_init_script("localStorage.setItem('hive_tour_dismissed', '1');")
        page = context.new_page()

        # Navigate to the bypass login endpoint via CloudFront (same origin as
        # the UI) so the mgmt JWT lands in the correct localStorage origin.
        # test_email is required — HIVE_BYPASS_GOOGLE_AUTH only triggers the
        # synthetic path when test_email is explicitly supplied (#140).
        page.goto(
            f"{UI_URL}/auth/login?test_email=e2e@example.com",
            timeout=30_000,
            wait_until="networkidle",
        )

        # Token is now in localStorage. Navigate directly to /app — the
        # HomeRoute would also redirect there, but client-side redirects can
        # race with wait_for_url so we go straight to the destination.
        page.goto(f"{UI_URL}/app", timeout=30_000, wait_until="networkidle")

        yield page
        context.close()
        browser.close()


class TestMarketingNav:
    def test_signin_btn_border_is_visible(self):
        """Sign in button on marketing navbar has a visible border (not transparent).

        Asserts the computed border-color so CSS regressions can't sneak past a
        class-name check.  The nav variant bakes border-white/60 into the variant
        itself — no className override needed.
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"{UI_URL}/", timeout=30_000, wait_until="networkidle")
            signin_btn = page.locator(".marketing-signin-btn")
            if not signin_btn.is_visible():
                browser.close()
                pytest.skip("Sign in button not visible (may be mobile viewport)")
            border_color = signin_btn.evaluate("el => getComputedStyle(el).borderColor")
            import re

            nums = [float(x) for x in re.findall(r"[\d.]+", border_color)]
            assert len(nums) >= 4 and nums[3] > 0, (
                f"Sign in button border is transparent: {border_color!r}. "
                "Check that the nav variant in button.jsx applies border-white/60."
            )
            browser.close()


class TestUIE2E:
    def test_memories_tab_visible(self, browser_page):
        page = browser_page
        page.goto(UI_URL)
        assert page.locator("nav button:has-text('Memories')").is_visible()

    def test_create_and_see_memory(self, browser_page):
        import time

        page = browser_page
        # Use a unique key AND a unique tag per run.  The key avoids ownership
        # conflicts; the tag is used to filter the list immediately after create
        # so we never depend on the new memory appearing on page 1 of an
        # unfiltered list (accumulated test data from past runs can push it off).
        ts = int(time.time())
        memory_key = f"ui-e2e-{ts}"
        unique_tag = f"e2e-{ts}"

        page.goto(UI_URL)
        page.wait_for_load_state("networkidle")  # wait for initial memories load
        # Ensure we're on Memories tab regardless of first-run redirect
        page.locator("nav button:has-text('Memories')").click()
        page.wait_for_load_state("networkidle")

        page.locator("button:has-text('+ New')").first.click()
        page.locator("input[placeholder='unique-key']").fill(memory_key)
        page.locator("textarea").fill("UI e2e test value")
        page.locator("input[placeholder='tag1, tag2']").fill(unique_tag)

        with page.expect_response(
            lambda r: "/api/memories" in r.url and r.request.method == "POST",
            timeout=30_000,
        ) as resp_info:
            page.locator("button:has-text('Save')").click()
        assert resp_info.value.ok, f"POST /api/memories failed: {resp_info.value.status}"

        # Wait for the list to reload after save.
        page.wait_for_load_state("networkidle")

        # Apply tag filter and retry to handle DynamoDB GSI eventual consistency.
        # The TagIndex GSI may not immediately reflect a new write; if the filtered
        # list comes back empty, clear the chip and reapply the filter until the
        # memory appears (or we exhaust retries). 24 × 5s = 120s total — GSI has
        # been observed taking north of 60s under load in the dev pipeline.
        _RETRIES = 24
        for attempt in range(_RETRIES):
            # If a chip is already showing, clear it first so we can re-type.
            if page.locator("[aria-label='Clear tag filter']").count() > 0:
                page.locator("[aria-label='Clear tag filter']").click()
                page.wait_for_selector("input[placeholder='Filter by tag']")
            tag_input = page.locator("input[placeholder='Filter by tag']")
            tag_input.fill(unique_tag)
            tag_input.press("Enter")
            page.wait_for_load_state("networkidle")
            if page.locator(f"text={memory_key}").count() > 0:
                break
            if attempt < _RETRIES - 1:
                time.sleep(5)  # wait for GSI propagation before retrying
        assert page.locator(f"text={memory_key}").first.is_visible(), (
            f"Memory '{memory_key}' not visible after filtering by tag '{unique_tag}'"
        )

    def test_clients_tab(self, browser_page):
        page = browser_page
        page.locator("nav button:has-text('OAuth Clients')").click()
        assert page.locator("text=Register Client").first.is_visible()

    def test_activity_tab(self, browser_page):
        page = browser_page
        page.locator("nav button:has-text('Activity Log')").click()
        assert page.locator("nav button:has-text('Activity Log')").is_visible()
