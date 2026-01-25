"""Mobile-specific e2e tests for dark mode functionality."""

from playwright.async_api import async_playwright, expect
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.mobile]

# Mobile device viewport
MOBILE_VIEWPORT = {"width": 375, "height": 667}  # iPhone SE


@pytest.mark.mobile
async def test_mobile_dark_mode_toggle_functionality(test_server):
    """Test mobile dark mode toggle works with touch interactions."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(has_touch=True, viewport=MOBILE_VIEWPORT)
        page = await context.new_page()

        try:
            await page.goto(f"{test_server}/")
            await page.wait_for_load_state("networkidle")

            # Mobile dark mode toggle should be visible in mobile controls
            mobile_dark_toggle = page.locator(".mobile-dark-mode-toggle .dark-mode-toggle")
            await expect(mobile_dark_toggle).to_be_visible()

            # Get initial theme state
            initial_state = await page.evaluate("""
                () => {
                    return {
                        theme: document.documentElement.getAttribute('data-theme'),
                        stored: localStorage.getItem('theme'),
                        systemPrefersDark: window.matchMedia('(prefers-color-scheme: dark)').matches
                    };
                }
            """)

            # Click mobile toggle using touch tap
            await mobile_dark_toggle.tap()
            await page.wait_for_timeout(200)

            # Verify theme changed
            after_toggle = await page.evaluate("""
                () => {
                    return {
                        theme: document.documentElement.getAttribute('data-theme'),
                        stored: localStorage.getItem('theme')
                    };
                }
            """)

            # Theme should be explicitly set and different from initial
            assert after_toggle["theme"] in ["dark", "light"]
            assert after_toggle["stored"] == after_toggle["theme"]
            assert after_toggle["theme"] != initial_state["theme"]

        finally:
            await browser.close()


@pytest.mark.mobile
async def test_mobile_theme_persistence_across_navigation(test_server):
    """Test that theme setting persists across mobile navigation."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(has_touch=True, viewport=MOBILE_VIEWPORT)
        page = await context.new_page()

        try:
            # Start on homepage and set theme using mobile toggle
            await page.goto(f"{test_server}/")
            mobile_dark_toggle = page.locator(".mobile-dark-mode-toggle .dark-mode-toggle")
            await mobile_dark_toggle.tap()
            await page.wait_for_timeout(100)

            # Get the theme that was set
            set_theme_info = await page.evaluate("""
                () => {
                    return {
                        theme: document.documentElement.getAttribute('data-theme'),
                        stored: localStorage.getItem('theme')
                    };
                }
            """)

            set_theme = set_theme_info["theme"]
            assert set_theme in ["dark", "light"]

            # Navigate using mobile menu
            mobile_menu_toggle = page.locator(".mobile-menu-toggle")
            await mobile_menu_toggle.tap()

            # Wait for menu to open and About link to become visible
            await page.wait_for_selector(
                '.mobile-nav.open a[href="/about"]', state="visible", timeout=5000
            )

            # Click About link in mobile menu
            await page.locator('.mobile-nav.open a[href="/about"]').tap()
            await page.wait_for_load_state("networkidle")

            # Verify theme persisted
            about_theme = await page.evaluate("""
                () => {
                    return {
                        theme: document.documentElement.getAttribute('data-theme'),
                        stored: localStorage.getItem('theme')
                    };
                }
            """)

            assert about_theme["theme"] == set_theme
            assert about_theme["stored"] == set_theme

            # Test another page through mobile navigation
            mobile_menu_toggle = page.locator(".mobile-menu-toggle")
            await mobile_menu_toggle.tap()
            await page.wait_for_timeout(200)

            await page.locator('.mobile-nav a[href="/login"]').tap()
            await page.wait_for_load_state("networkidle")

            # Wait for page to fully load then verify theme still persisted
            await page.wait_for_timeout(500)  # Extra wait for navigation
            login_theme = await page.evaluate("""
                () => {
                    return {
                        theme: document.documentElement.getAttribute('data-theme'),
                        stored: localStorage.getItem('theme')
                    };
                }
            """)

            assert login_theme["theme"] == set_theme
            assert login_theme["stored"] == set_theme

        finally:
            await browser.close()


@pytest.mark.mobile
async def test_mobile_viewport_responsive_behavior(test_server):
    """Test dark mode behavior at different mobile viewport sizes."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Test different mobile viewport sizes
        mobile_viewports = [
            {"width": 375, "height": 667},  # iPhone SE
            {"width": 390, "height": 844},  # iPhone 12/13
            {"width": 414, "height": 896},  # iPhone 11 Pro Max
        ]

        for viewport in mobile_viewports:
            context = await browser.new_context(has_touch=True, viewport=viewport)
            page = await context.new_page()

            try:
                await page.goto(f"{test_server}/")
                await page.wait_for_load_state("networkidle")

                # Mobile controls should be visible at all mobile sizes
                mobile_controls = page.locator(".mobile-controls")
                await expect(mobile_controls).to_be_visible()

                # Desktop auth buttons should be hidden
                desktop_auth = page.locator(".auth-buttons")
                await expect(desktop_auth).to_be_hidden()

                # Mobile dark mode toggle should work
                mobile_dark_toggle = page.locator(".mobile-dark-mode-toggle .dark-mode-toggle")
                await expect(mobile_dark_toggle).to_be_visible()

                await mobile_dark_toggle.tap()
                await page.wait_for_timeout(100)

                # Theme should be set
                theme_info = await page.evaluate("""
                    () => {
                        return {
                            theme: document.documentElement.getAttribute('data-theme'),
                            stored: localStorage.getItem('theme')
                        };
                    }
                """)

                assert theme_info["theme"] in ["dark", "light"]
                assert theme_info["stored"] == theme_info["theme"]

            finally:
                await context.close()

        await browser.close()


@pytest.mark.mobile
async def test_mobile_scroll_page_dark_mode_sync(test_server):
    """Test scroll page dark mode toggle syncs with mobile theme."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(has_touch=True, viewport=MOBILE_VIEWPORT)
        page = await context.new_page()

        try:
            # Set theme on main site using mobile toggle
            await page.goto(f"{test_server}/")
            mobile_dark_toggle = page.locator(".mobile-dark-mode-toggle .dark-mode-toggle")
            await mobile_dark_toggle.tap()
            await page.wait_for_timeout(100)

            # Get the theme that was set
            main_site_theme = await page.evaluate("""
                () => {
                    return {
                        currentTheme: document.documentElement.getAttribute('data-theme'),
                        storedTheme: localStorage.getItem('theme')
                    };
                }
            """)

            set_theme = main_site_theme["currentTheme"]
            assert set_theme in ["dark", "light"]

            # Navigate to browse page to find a scroll
            await page.goto(f"{test_server}/browse")
            await page.wait_for_load_state("networkidle")

            # Find and click a scroll link
            scroll_link = page.locator('a[href*="/scroll/"]').first
            if await scroll_link.count() > 0:
                await scroll_link.tap()
                await page.wait_for_load_state("networkidle")

                # Verify scroll page synced theme
                scroll_page_theme = await page.evaluate("""
                    () => {
                        return {
                            currentTheme: document.documentElement.getAttribute('data-theme'),
                            storedTheme: localStorage.getItem('theme'),
                            hasScrollToggle: !!document.querySelector('.scroll-dark-mode-toggle')
                        };
                    }
                """)

                # Theme should have synced from main site
                assert scroll_page_theme["currentTheme"] == set_theme
                assert scroll_page_theme["storedTheme"] == set_theme
                assert scroll_page_theme["hasScrollToggle"]

                # Test scroll page toggle on mobile
                scroll_toggle = page.locator(".scroll-dark-mode-toggle")
                await expect(scroll_toggle).to_be_visible()

                # Toggle theme on scroll page using touch
                await scroll_toggle.tap()
                await page.wait_for_timeout(100)

                # Verify toggle worked
                after_scroll_toggle = await page.evaluate("""
                    () => {
                        return {
                            currentTheme: document.documentElement.getAttribute('data-theme'),
                            storedTheme: localStorage.getItem('theme')
                        };
                    }
                """)

                # Theme should have changed and be stored
                assert after_scroll_toggle["currentTheme"] != set_theme
                assert after_scroll_toggle["storedTheme"] == after_scroll_toggle["currentTheme"]

        finally:
            await browser.close()


@pytest.mark.mobile
async def test_mobile_touch_interactions_with_theme(test_server):
    """Test theme toggle responds properly to mobile touch events."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(has_touch=True, viewport=MOBILE_VIEWPORT)
        page = await context.new_page()

        try:
            await page.goto(f"{test_server}/")
            await page.wait_for_load_state("networkidle")

            mobile_dark_toggle = page.locator(".mobile-dark-mode-toggle .dark-mode-toggle")

            # Test tap (primary mobile interaction)
            await mobile_dark_toggle.tap()
            await page.wait_for_timeout(100)

            first_toggle = await page.evaluate("""
                () => document.documentElement.getAttribute('data-theme')
            """)

            # Test double tap (should toggle twice)
            await mobile_dark_toggle.tap()
            await page.wait_for_timeout(100)
            await mobile_dark_toggle.tap()
            await page.wait_for_timeout(100)

            final_toggle = await page.evaluate("""
                () => document.documentElement.getAttribute('data-theme')
            """)

            # After two taps, should be back to first state
            assert final_toggle == first_toggle

            # Verify theme is properly stored
            stored_theme = await page.evaluate("""
                () => localStorage.getItem('theme')
            """)
            assert stored_theme == final_toggle

        finally:
            await browser.close()
