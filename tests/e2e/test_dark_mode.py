"""Minimal high-quality e2e tests for dark mode functionality."""

from playwright.async_api import async_playwright, expect
import pytest

pytestmark = pytest.mark.e2e


async def test_system_preference_and_manual_override(test_server):
    """Test system preference detection and manual override functionality."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Test with dark system preference
        dark_context = await browser.new_context(color_scheme="dark")
        dark_page = await dark_context.new_page()

        # Test with light system preference
        light_context = await browser.new_context(color_scheme="light")
        light_page = await light_context.new_page()

        try:
            # === Test 1: Dark system preference should be respected ===
            await dark_page.goto(f"{test_server}/")
            await dark_page.wait_for_load_state("networkidle")

            # Should start with no explicit data-theme (following system)
            initial_dark_theme = await dark_page.evaluate("""
                () => {
                    const hasExplicitTheme = document.documentElement.hasAttribute('data-theme');
                    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                    const storedTheme = localStorage.getItem('theme');
                    return { hasExplicitTheme, systemPrefersDark, storedTheme };
                }
            """)

            assert initial_dark_theme["systemPrefersDark"]
            assert initial_dark_theme["storedTheme"] is None  # No manual override yet

            # === Test 2: Manual override should work (dark → light) ===
            await dark_page.locator(".dark-mode-toggle").first.click()
            await dark_page.wait_for_timeout(100)

            after_toggle = await dark_page.evaluate("""
                () => {
                    const currentTheme = document.documentElement.getAttribute('data-theme');
                    const storedTheme = localStorage.getItem('theme');
                    return { currentTheme, storedTheme };
                }
            """)

            # Should have switched to light and persisted choice
            assert after_toggle["currentTheme"] == "light"
            assert after_toggle["storedTheme"] == "light"

            # === Test 3: Light system preference should be respected ===
            await light_page.goto(f"{test_server}/")
            await light_page.wait_for_load_state("networkidle")

            initial_light_theme = await light_page.evaluate("""
                () => {
                    const hasExplicitTheme = document.documentElement.hasAttribute('data-theme');
                    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                    const storedTheme = localStorage.getItem('theme');
                    return { hasExplicitTheme, systemPrefersDark, storedTheme };
                }
            """)

            assert not initial_light_theme["systemPrefersDark"]
            assert initial_light_theme["storedTheme"] is None  # No manual override yet

            # === Test 4: Manual override should work (light → dark) ===
            await light_page.locator(".dark-mode-toggle").first.click()
            await light_page.wait_for_timeout(100)

            after_light_toggle = await light_page.evaluate("""
                () => {
                    const currentTheme = document.documentElement.getAttribute('data-theme');
                    const storedTheme = localStorage.getItem('theme');
                    return { currentTheme, storedTheme };
                }
            """)

            # Should have switched to dark and persisted choice
            assert after_light_toggle["currentTheme"] == "dark"
            assert after_light_toggle["storedTheme"] == "dark"

        finally:
            await dark_context.close()
            await light_context.close()
            await browser.close()


async def test_theme_persistence_across_navigation(test_server):
    """Test that theme setting persists across page navigation."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Start on homepage and set dark mode
            await page.goto(f"{test_server}/")
            await page.locator(".dark-mode-toggle").first.click()
            await page.wait_for_timeout(100)

            # Verify dark mode is active
            theme_after_toggle = await page.evaluate("""
                () => {
                    const currentTheme = document.documentElement.getAttribute('data-theme');
                    const storedTheme = localStorage.getItem('theme');
                    return { currentTheme, storedTheme };
                }
            """)

            set_theme = theme_after_toggle["currentTheme"]
            assert set_theme in ["dark", "light"]  # Should be explicitly set
            assert theme_after_toggle["storedTheme"] == set_theme

            # Test persistence across key page types
            pages_to_test = ["/about", "/login", "/terms"]

            for page_url in pages_to_test:
                await page.goto(f"{test_server}{page_url}")
                await page.wait_for_load_state("networkidle")

                # Verify theme persisted
                persisted_theme = await page.evaluate("""
                    () => {
                        const currentTheme = document.documentElement.getAttribute('data-theme');
                        const storedTheme = localStorage.getItem('theme');
                        return { currentTheme, storedTheme };
                    }
                """)

                assert persisted_theme["currentTheme"] == set_theme, (
                    f"Theme not persisted on {page_url}"
                )
                assert persisted_theme["storedTheme"] == set_theme, (
                    f"localStorage not persisted on {page_url}"
                )

        finally:
            await browser.close()


async def test_theme_toggle_after_htmx_navigation(test_server):
    """Regression test: theme toggle should work after HTMX navigation (e.g., login).

    This test ensures that event listeners are properly attached to dynamically
    loaded content via HTMX. Previously, theme toggles didn't work after HTMX
    swapped content because DOMContentLoaded had already fired.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login to trigger HTMX navigation to dashboard
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')

            # Wait for HTMX to process login and redirect to dashboard
            await expect(page.locator(".success-message")).to_be_visible(timeout=5000)
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            # Dashboard should be loaded via HTMX
            await expect(page.locator("h2").first).to_contain_text("Your Scrolls")

            # Verify theme toggle button exists in the dynamically loaded content
            dark_mode_toggle = page.locator(".dark-mode-toggle").first
            await expect(dark_mode_toggle).to_be_visible()

            # Get initial theme state
            initial_theme = await page.evaluate("""
                () => document.documentElement.getAttribute('data-theme')
            """)

            # Click theme toggle
            await dark_mode_toggle.click()
            await page.wait_for_timeout(200)

            # Get theme state after toggle
            toggled_theme = await page.evaluate("""
                () => document.documentElement.getAttribute('data-theme')
            """)

            # Verify theme actually changed (this is the regression test)
            assert initial_theme != toggled_theme, (
                "Theme didn't change after clicking toggle on HTMX-loaded content"
            )

            # Verify the new theme is valid
            assert toggled_theme in ["dark", "light"], f"Invalid theme: {toggled_theme}"

            # Verify localStorage was updated
            stored_theme = await page.evaluate("""
                () => localStorage.getItem('theme')
            """)
            assert stored_theme == toggled_theme, "Theme not persisted to localStorage"

        finally:
            await browser.close()


async def test_no_script_redeclaration_errors_after_htmx_navigation(test_server):
    """Regression test: no JavaScript redeclaration errors after HTMX navigation.

    This test ensures that scripts don't redeclare variables when HTMX re-executes
    them. Previously, module-level `let`/`const` declarations would throw
    "identifier already declared" errors when HTMX swapped content.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Collect console errors
        console_errors = []
        page.on("console", lambda msg: (
            console_errors.append(msg.text) if msg.type == "error" else None
        ))

        try:
            # Login to trigger HTMX navigation
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')

            # Wait for HTMX to complete
            await expect(page.locator(".success-message")).to_be_visible(timeout=5000)
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)
            await page.wait_for_timeout(500)  # Give time for any errors to appear

            # Filter for redeclaration errors
            redeclaration_errors = [
                err for err in console_errors
                if "already been declared" in err or "Identifier" in err
            ]

            # Assert no redeclaration errors occurred
            assert len(redeclaration_errors) == 0, (
                f"Script redeclaration errors detected after HTMX navigation: {redeclaration_errors}"
            )

            # Navigate to another page to trigger more HTMX
            await page.click('a[href="/upload"]')
            await page.wait_for_timeout(500)

            # Check again for errors after second navigation
            redeclaration_errors = [
                err for err in console_errors
                if "already been declared" in err or "Identifier" in err
            ]

            assert len(redeclaration_errors) == 0, (
                f"Script redeclaration errors after multiple navigations: {redeclaration_errors}"
            )

        finally:
            await browser.close()


@pytest.mark.desktop
async def test_toggle_functionality_and_css_changes(test_server):
    """Test that dark mode toggle works and CSS variables actually change on desktop."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Test on representative pages (covers different template types)
            pages_to_test = [
                "/",  # Main homepage
                "/login",  # Auth page
                "/about",  # Static content page
            ]

            for page_url in pages_to_test:
                await page.goto(f"{test_server}{page_url}")
                await page.wait_for_load_state("networkidle")

                # Verify dark mode toggle exists
                dark_mode_toggle = page.locator(".dark-mode-toggle").first
                await expect(dark_mode_toggle).to_be_visible()

                # Get initial CSS variable values
                initial_vars = await page.evaluate("""
                    () => {
                        const styles = getComputedStyle(document.documentElement);
                        return {
                            white: styles.getPropertyValue('--white').trim(),
                            black: styles.getPropertyValue('--black').trim(),
                            grayDark: styles.getPropertyValue('--gray-dark').trim(),
                            theme: document.documentElement.getAttribute('data-theme')
                        };
                    }
                """)

                # Toggle theme
                await dark_mode_toggle.click()
                await page.wait_for_timeout(200)  # Wait for CSS to apply

                # Get CSS variable values after toggle
                toggled_vars = await page.evaluate("""
                    () => {
                        const styles = getComputedStyle(document.documentElement);
                        return {
                            white: styles.getPropertyValue('--white').trim(),
                            black: styles.getPropertyValue('--black').trim(),
                            grayDark: styles.getPropertyValue('--gray-dark').trim(),
                            theme: document.documentElement.getAttribute('data-theme')
                        };
                    }
                """)

                # Verify theme and CSS variables changed
                assert initial_vars["theme"] != toggled_vars["theme"], (
                    f"Theme didn't change on {page_url}"
                )
                assert toggled_vars["theme"] in ["dark", "light"], f"Invalid theme on {page_url}"

                # At least one CSS variable should have changed
                css_changed = (
                    initial_vars["white"] != toggled_vars["white"]
                    or initial_vars["black"] != toggled_vars["black"]
                    or initial_vars["grayDark"] != toggled_vars["grayDark"]
                )
                assert css_changed, f"CSS variables didn't change on {page_url}"

        finally:
            await browser.close()
