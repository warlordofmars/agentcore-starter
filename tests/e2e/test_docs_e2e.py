# Copyright (c) 2026 John Carter. All rights reserved.
"""
Playwright E2E tests for the Hive VitePress docs site.
Requires:
  HIVE_UI_URL — deployed UI URL (CloudFront), e.g. https://hive.warlordofmars.net
"""

from __future__ import annotations

import os

import pytest

UI_URL = os.environ.get("HIVE_UI_URL", "")

pytestmark = pytest.mark.skipif(
    not UI_URL,
    reason="HIVE_UI_URL not set — skipping docs e2e tests",
)

# Expected navbar background — #1a1a2e in RGB
_NAVBAR_BG = "rgb(26, 26, 46)"
# Minimum luminance ratio considered "light enough" for white-on-dark text
# rgb(255,255,255) on rgb(26,26,46) is ~12:1, well above 4.5:1 WCAG AA
_MIN_ALPHA = 0.6  # channel value 0–1 for rgba text colours


@pytest.fixture(scope="module")
def _browser():
    """Single Playwright browser instance shared across all docs e2e tests.

    Two separate sync_playwright() calls in the same process conflict because
    each one tries to start its own asyncio event loop and the second raises
    "Sync API inside asyncio loop" when the first is still active (yielded).
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def docs_page(_browser):
    page = _browser.new_page()
    yield page
    page.close()


@pytest.fixture(scope="module")
def docs_page_mobile(_browser):
    """Page at 375×812 (iPhone viewport) for mobile tests."""
    page = _browser.new_page(viewport={"width": 375, "height": 812})
    yield page
    page.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bg(page, selector: str) -> str:
    return page.evaluate(
        f"() => window.getComputedStyle(document.querySelector('{selector}')).backgroundColor"
    )


def _color(page, selector: str) -> str:
    return page.evaluate(
        f"() => window.getComputedStyle(document.querySelector('{selector}')).color"
    )


def _parse_rgb(css: str) -> tuple[int, int, int, float]:
    """Parse rgb(...) or rgba(...) → (r, g, b, a)."""
    import re

    nums = [float(x) for x in re.findall(r"[\d.]+", css)]
    r, g, b = int(nums[0]), int(nums[1]), int(nums[2])
    a = float(nums[3]) if len(nums) > 3 else 1.0
    return r, g, b, a


# ---------------------------------------------------------------------------
# General docs routing tests
# ---------------------------------------------------------------------------


class TestDocsRouting:
    def test_docs_home_redirects(self, docs_page):
        """/docs and /docs/ both redirect to What is Hive? (no separate landing page)."""
        page = docs_page
        # Test /docs/ (the href VitePress emits for the Docs nav link)
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        assert page.url.rstrip("/").endswith("/docs/getting-started/what-is-hive"), (
            f"/docs/ should redirect to what-is-hive, got {page.url!r}"
        )
        assert page.locator("h1").first.is_visible()
        assert not page.locator("button:has-text('Sign in')").is_visible()

    def test_docs_home_title(self, docs_page):
        """Page title contains 'Hive' after redirect."""
        page = docs_page
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        assert "Hive" in page.title()

    def test_docs_subpage_loads(self, docs_page):
        """A nested doc page loads without redirecting to the React app."""
        page = docs_page
        page.goto(
            f"{UI_URL}/docs/getting-started/quick-start",
            timeout=30_000,
            wait_until="networkidle",
        )
        assert page.locator("h1").first.is_visible()
        assert not page.locator("button:has-text('Sign in')").is_visible()

    def test_docs_trailing_slash_page_loads(self, docs_page):
        """Trailing slash on a content page resolves correctly (CloudFront Function)."""
        page = docs_page
        page.goto(
            f"{UI_URL}/docs/getting-started/quick-start/",
            timeout=30_000,
            wait_until="networkidle",
        )
        assert page.locator("h1").first.is_visible()
        assert not page.locator("button:has-text('Sign in')").is_visible()

    def test_docs_logo_not_broken(self, docs_page):
        """Logo image loads successfully (not a broken image)."""
        page = docs_page
        page.goto(
            f"{UI_URL}/docs/getting-started/quick-start",
            timeout=30_000,
            wait_until="networkidle",
        )
        logo = page.locator("img[alt='Hive']")
        assert logo.is_visible()
        natural_width = page.evaluate("el => el.naturalWidth", logo.element_handle())
        assert natural_width > 0, "Logo image failed to load (naturalWidth == 0)"

    def test_docs_sidebar_navigation(self, docs_page):
        """Sidebar section headings are visible on a doc page."""
        page = docs_page
        page.goto(
            f"{UI_URL}/docs/getting-started/quick-start",
            timeout=30_000,
            wait_until="networkidle",
        )
        assert page.locator(".VPSidebar").is_visible()

    def test_docs_search_present(self, docs_page):
        """Local search button is present."""
        page = docs_page
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        assert (
            page.locator("button.DocSearch").is_visible()
            or page.locator("[aria-label='Search']").is_visible()
        )


# ---------------------------------------------------------------------------
# Navbar appearance and behaviour tests
# ---------------------------------------------------------------------------


class TestDocsNavbar:
    def test_navbar_dark_on_doc_page(self, docs_page):
        """Navbar background is dark navy on a doc page (sidebar layout)."""
        page = docs_page
        page.goto(
            f"{UI_URL}/docs/getting-started/quick-start",
            timeout=30_000,
            wait_until="networkidle",
        )
        bg = _bg(page, ".VPNavBar")
        assert bg == _NAVBAR_BG, (
            f"Expected navbar bg {_NAVBAR_BG!r} on doc page, got {bg!r}. "
            "Check .VPNavBar and .content-body CSS overrides."
        )

    def test_navbar_dark_on_home_page(self, docs_page):
        """Navbar background is dark navy when navigating via /docs/ (redirects to sidebar page)."""
        page = docs_page
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        bg = _bg(page, ".VPNavBar")
        assert bg == _NAVBAR_BG, (
            f"Expected navbar bg {_NAVBAR_BG!r}, got {bg!r}. "
            "Check .VPNavBar and .VPNavBar.has-sidebar CSS overrides."
        )

    def test_navbar_dark_after_scroll(self, docs_page):
        """Navbar stays dark navy after scrolling down on a doc page."""
        page = docs_page
        page.goto(
            f"{UI_URL}/docs/getting-started/quick-start",
            timeout=30_000,
            wait_until="networkidle",
        )
        page.evaluate("window.scrollBy(0, 300)")
        page.wait_for_timeout(400)  # allow transition
        bg = _bg(page, ".VPNavBar")
        assert bg == _NAVBAR_BG, (
            f"Navbar bg changed after scroll: {bg!r}. "
            "Check .VPNavBar:not(.home) desktop media-query override."
        )

    def test_logo_wordmark_matches_marketing(self, docs_page):
        """Logo wordmark font matches the marketing site header: 700 weight, 20px, 1px spacing."""
        page = docs_page
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        title = page.locator(".VPNavBarTitle .title")
        el = title.element_handle()

        font_weight = page.evaluate("el => window.getComputedStyle(el).fontWeight", el)
        assert font_weight == "700", (
            f"Logo wordmark font-weight {font_weight!r} — expected '700' to match marketing site."
        )

        font_size = page.evaluate("el => window.getComputedStyle(el).fontSize", el)
        assert font_size == "20px", (
            f"Logo wordmark font-size {font_size!r} — expected '20px' to match marketing site."
        )

        letter_spacing = page.evaluate("el => window.getComputedStyle(el).letterSpacing", el)
        assert letter_spacing == "1px", (
            f"Logo wordmark letter-spacing {letter_spacing!r} — expected '1px'."
        )

        logo_img = page.locator(".VPNavBarTitle .logo")
        if logo_img.is_visible():
            el2 = logo_img.element_handle()
            logo_height = page.evaluate("el => window.getComputedStyle(el).height", el2)
            assert logo_height == "28px", (
                f"Logo image height {logo_height!r} — expected '28px' to match marketing site."
            )

    def test_navbar_title_is_light(self, docs_page):
        """Site title text is light (readable on dark navbar)."""
        page = docs_page
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        color = _color(page, ".VPNavBarTitle .title")
        r, g, b, _ = _parse_rgb(color)
        # All channels should be high (near white)
        assert r > 200 and g > 200 and b > 200, (
            f"Navbar title text {color!r} is too dark for dark background. "
            "Check .VPNavBarTitle .title color override."
        )

    def test_nav_links_are_light(self, docs_page):
        """Docs nav link is light-coloured (readable on dark navbar)."""
        page = docs_page
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        link = page.locator(".docs-nav-link").first
        if not link.is_visible():
            pytest.skip("Docs nav link not visible (may be mobile viewport)")
        color = page.evaluate(
            "el => window.getComputedStyle(el).color",
            link.element_handle(),
        )
        r, g, b, a = _parse_rgb(color)
        assert r > 150 and g > 150 and b > 150, (
            f"Docs nav link color {color!r} is too dark for dark navbar. "
            "Check .docs-nav-link color."
        )

    def test_content_body_dark_on_sidebar_page(self, docs_page):
        """The content-body (right navbar section) is dark on a sidebar page."""
        page = docs_page
        page.goto(
            f"{UI_URL}/docs/getting-started/quick-start",
            timeout=30_000,
            wait_until="networkidle",
        )
        content_body = page.locator(".VPNavBar .content-body")
        if not content_body.is_visible():
            pytest.skip(".content-body not visible (may be mobile viewport)")
        bg = page.evaluate(
            "el => window.getComputedStyle(el).backgroundColor",
            content_body.element_handle(),
        )
        assert bg == _NAVBAR_BG, (
            f"Expected .content-body bg {_NAVBAR_BG!r} on sidebar page, got {bg!r}. "
            "Check .VPNavBar .content-body CSS override."
        )

    def test_docs_nav_link_href(self, docs_page):
        """Docs nav link href points to what-is-hive, rendered via layout slot."""
        page = docs_page
        page.goto(
            f"{UI_URL}/docs/getting-started/what-is-hive",
            timeout=30_000,
            wait_until="networkidle",
        )
        docs_link = page.locator(".docs-nav-link", has_text="Docs")
        if not docs_link.is_visible():
            pytest.skip("Docs nav link not visible")
        href = docs_link.get_attribute("href")
        assert href == "/docs/getting-started/what-is-hive", (
            f"Docs nav link href {href!r} — expected '/docs/getting-started/what-is-hive'."
        )

    def test_docs_nav_link_click(self, docs_page):
        """Clicking Docs nav link navigates to what-is-hive.

        Start from quick-start so the click triggers a real navigation.
        """
        page = docs_page
        page.goto(
            f"{UI_URL}/docs/getting-started/quick-start",
            timeout=30_000,
            wait_until="networkidle",
        )
        docs_link = page.locator(".docs-nav-link", has_text="Docs")
        if not docs_link.is_visible():
            pytest.skip("Docs nav link not visible")
        with page.expect_navigation(timeout=15_000):
            docs_link.click()
        page.wait_for_load_state("networkidle", timeout=15_000)
        assert "getting-started/what-is-hive" in page.url, (
            f"Docs link navigated to {page.url!r} — expected what-is-hive page."
        )
        assert page.locator("h1").first.is_visible()

    def test_logo_click_navigates_to_marketing(self, docs_page):
        """Clicking the Hive logo performs a full page navigation to the marketing root.

        VitePress's Vue Router would intercept href='/' as a client-side SPA
        navigation, keeping the user on /docs/. The theme's enhanceApp override
        intercepts the click in the capture phase and calls window.location.href='/'
        to force a real page load of the marketing site instead.
        """
        page = docs_page
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        logo = page.locator(".VPNavBarTitle .title")
        with page.expect_navigation(timeout=30_000):
            logo.click()
        page.wait_for_url(f"{UI_URL}/", timeout=30_000)
        assert page.url.rstrip("/") == UI_URL.rstrip("/"), (
            f"Logo click navigated to {page.url!r} — expected marketing page '{UI_URL}'."
        )

    def test_signin_nav_link_click(self, docs_page):
        """Clicking the Sign in button loads the React login page at /app.

        Sign in is injected as a plain <a href="/app"> via a VitePress layout
        slot (nav-bar-content-after) so Vue Router never handles it.  This
        avoids Vue Router pushing /docs/app onto the browser history stack.
        """
        page = docs_page
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        signin_btn = page.locator(".docs-signin-btn")
        if not signin_btn.is_visible():
            pytest.skip("Sign in button not visible")
        with page.expect_navigation(timeout=30_000):
            signin_btn.click()
        page.wait_for_url(f"{UI_URL}/app", timeout=30_000)
        assert page.url.rstrip("/").endswith("/app"), (
            f"Sign in button navigated to {page.url!r} — expected URL ending in '/app'."
        )

    def test_signin_back_button_returns_to_docs(self, _browser):
        """Pressing Back after Sign in returns to the docs page — not a /docs/app 404.

        The old approach used a RouterLink (href=/docs/app) with a JS click
        interceptor.  Vue Router pushed /docs/app onto the history stack before
        the interceptor fired, so Back landed on /docs/app (404).  The fix is
        a plain <a href="/app"> that Vue Router never sees.

        Uses a fresh page (not the module-scoped docs_page) so that accumulated
        history from prior tests doesn't affect the go_back() destination.
        """
        page = _browser.new_page()
        origin_url = f"{UI_URL}/docs/getting-started/what-is-hive"
        page.goto(origin_url, timeout=30_000, wait_until="networkidle")
        signin_btn = page.locator(".docs-signin-btn")
        if not signin_btn.is_visible():
            pytest.skip("Sign in button not visible")
        with page.expect_navigation(timeout=30_000):
            signin_btn.click()
        page.wait_for_url(f"{UI_URL}/app", timeout=30_000)
        # Go back
        with page.expect_navigation(timeout=15_000):
            page.go_back()
        page.wait_for_load_state("networkidle", timeout=15_000)
        assert "/docs/app" not in page.url, (
            f"Back button landed on {page.url!r} — /docs/app 404 regression detected."
        )
        assert page.locator(".VPNavBar").is_visible(), (
            f"Back button left the docs site entirely ({page.url!r})."
        )
        page.close()

    def test_signin_link_has_button_style(self, docs_page):
        """Sign in button styling matches the marketing site header button exactly.

        Rendered as .docs-signin-btn via a layout slot — a plain <a> with no
        VitePress/Vue Router involvement.  Padding, border, and radius must
        match the marketing site: padding 6px 16px, border solid rgba(255,255,255,.3),
        border-radius 6px.
        """
        page = docs_page
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        signin_btn = page.locator(".docs-signin-btn")
        if not signin_btn.is_visible():
            pytest.skip("Sign in button not visible (may be mobile viewport)")

        el = signin_btn.element_handle()

        # href must be /app — never /docs/app (which would cause Back → 404)
        href = signin_btn.get_attribute("href")
        assert href == "/app", (
            f"Sign in button href {href!r} — expected '/app'. "
            "A /docs/app href means Vue Router is still involved and Back will 404."
        )

        border_style = page.evaluate("el => window.getComputedStyle(el).borderTopStyle", el)
        assert border_style == "solid", (
            f"Sign in button borderTopStyle {border_style!r} — expected 'solid'."
        )

        border_radius = page.evaluate("el => window.getComputedStyle(el).borderTopLeftRadius", el)
        assert border_radius == "6px", (
            f"Sign in button border-radius {border_radius!r} — expected '6px'."
        )

        border_color = page.evaluate("el => window.getComputedStyle(el).borderTopColor", el)
        _, _, _, alpha = _parse_rgb(border_color)
        assert alpha >= 0.5, (
            f"Sign in button border alpha {alpha:.2f} ({border_color!r}) — "
            "expected >= 0.5 to match marketing site (rgba(255,255,255,0.6))."
        )

        padding = page.evaluate("el => window.getComputedStyle(el).padding", el)
        assert padding == "6px 16px", (
            f"Sign in button padding {padding!r} — expected '6px 16px' to match "
            "the marketing site header button."
        )

    def test_docs_link_style_matches_marketing(self, docs_page):
        """Docs nav link color and font-size match the marketing site header."""
        page = docs_page
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        docs_link = page.locator(".docs-nav-link").first
        if not docs_link.is_visible():
            pytest.skip("Docs nav link not visible (may be mobile viewport)")

        el = docs_link.element_handle()

        color = page.evaluate("el => window.getComputedStyle(el).color", el)
        r, g, b, _ = _parse_rgb(color)
        assert r > 150 and g > 150 and b > 150, (
            f"Docs link color {color!r} is too dark — expected ~rgba(255,255,255,0.75)."
        )

        font_size = page.evaluate("el => window.getComputedStyle(el).fontSize", el)
        assert font_size == "14px", f"Docs link font-size {font_size!r} — expected '14px'."

    def test_docs_link_active_indicator(self, docs_page):
        """Docs nav link has orange bottom border (active indicator) on the docs site.

        The Docs link is always 'active' on the docs site — the .docs-nav-link--active
        class is baked into the element and the orange border is always shown.
        """
        page = docs_page
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        docs_link = page.locator(".docs-nav-link", has_text="Docs")
        if not docs_link.is_visible():
            pytest.skip("Docs nav link not visible (may be mobile viewport)")

        el = docs_link.element_handle()
        border_color = page.evaluate("el => window.getComputedStyle(el).borderBottomColor", el)
        r, g, b, _ = _parse_rgb(border_color)
        # #e8a020 == rgb(232, 160, 32) — orange active indicator
        assert r > 200 and g > 100 and b < 100, (
            f"Docs link border-bottom-color {border_color!r} — expected orange (#e8a020 / rgb(232,160,32))."
        )

    def test_navbar_hamburger_visible_mobile(self, docs_page_mobile):
        """Hamburger menu button is visible on mobile viewport."""
        page = docs_page_mobile
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        hamburger = page.locator(".VPNavBarHamburger")
        assert hamburger.is_visible(), "Hamburger button not visible on mobile viewport"

    def test_navbar_mobile_menu_toggle(self, docs_page_mobile):
        """Clicking the hamburger opens the mobile nav screen."""
        page = docs_page_mobile
        page.goto(f"{UI_URL}/docs/", timeout=30_000, wait_until="networkidle")
        hamburger = page.locator(".VPNavBarHamburger")
        hamburger.click()
        screen = page.locator(".VPNavScreen")
        screen.wait_for(state="visible", timeout=5_000)
        assert screen.is_visible(), "Mobile nav screen did not open after hamburger click"

    def test_docs_page_fits_mobile_viewport(self, docs_page_mobile):
        """Docs pages should render without horizontal overflow at 375px (#528).

        VitePress plus the custom theme occasionally lets a wide code block
        or table overflow the page — this guards against regressions.
        """
        page = docs_page_mobile
        page.goto(
            f"{UI_URL}/docs/getting-started/what-is-hive",
            timeout=30_000,
            wait_until="networkidle",
        )
        doc_width, body_width = page.evaluate(
            "() => [document.querySelector('.vp-doc').scrollWidth, document.body.clientWidth]"
        )
        # Allow a small fudge for sub-pixel rounding / scrollbar — but the
        # content must not exceed the viewport by more than a few px.
        assert doc_width <= body_width + 4, (
            f"Docs content scrollWidth {doc_width} exceeds body clientWidth {body_width}"
        )

    def test_mobile_sidebar_opens_on_menu(self, docs_page_mobile):
        """The doc-pages sidebar is collapsed on mobile and opens via the menu button."""
        page = docs_page_mobile
        page.goto(
            f"{UI_URL}/docs/getting-started/what-is-hive",
            timeout=30_000,
            wait_until="networkidle",
        )
        menu_btn = page.locator(".VPLocalNav button, .VPLocalNav .menu")
        if not menu_btn.first.is_visible():
            pytest.skip("Local nav menu not visible (layout may have changed)")
        menu_btn.first.click()
        sidebar = page.locator(".VPSidebar")
        sidebar.wait_for(state="visible", timeout=5_000)
        assert sidebar.is_visible(), "Sidebar did not open after menu click"
