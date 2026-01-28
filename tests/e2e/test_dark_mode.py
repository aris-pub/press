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
        page.on(
            "console",
            lambda msg: (console_errors.append(msg.text) if msg.type == "error" else None),
        )

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
                err
                for err in console_errors
                if "already been declared" in err or "Identifier" in err
            ]

            # Assert no redeclaration errors occurred
            assert len(redeclaration_errors) == 0, (
                f"Script redeclaration errors detected after HTMX navigation: {redeclaration_errors}"
            )

        finally:
            await browser.close()


async def test_logo_loads_on_homepage(test_server):
    """Regression test: logo should load on homepage.

    This ensures the navbar logo is visible on the homepage on initial page load.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Navigate to homepage
            await page.goto(f"{test_server}/")
            await page.wait_for_load_state("networkidle")

            # Verify logo is visible
            logo = page.locator(".navbar .logo img")
            await expect(logo).to_be_visible(timeout=5000)

            # Verify logo has correct src
            logo_src = await logo.get_attribute("src")
            assert "/brand/logos/press/press-logo-64.svg" in logo_src, (
                f"Logo src incorrect: {logo_src}"
            )

            # Verify only one navbar exists
            navbar_count = await page.locator(".navbar").count()
            assert navbar_count == 1, f"Expected 1 navbar, found {navbar_count}"

        finally:
            await browser.close()


async def test_logo_loads_after_login_and_homepage_navigation(test_server):
    """Regression test: logo should load when navigating to homepage after login.

    This tests the scenario where a user logs in, then navigates back to homepage.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Collect network requests
        requests = []
        page.on(
            "request",
            lambda req: requests.append(
                {"url": req.url, "method": req.method, "headers": dict(req.headers)}
            ),
        )

        try:
            # Login
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')

            # Wait for login to complete
            await expect(page.locator(".success-message")).to_be_visible(timeout=5000)
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            # Clear requests log
            requests.clear()

            # Click logo to navigate to homepage
            await page.click(".navbar .logo a")
            await page.wait_for_url(f"{test_server}/", timeout=5000)
            await page.wait_for_timeout(500)

            # Check if logo was requested
            logo_requests = [r for r in requests if "press-logo-64.svg" in r["url"]]
            print(f"\n=== Logo requests after navigation: {len(logo_requests)} ===")
            for req in logo_requests:
                print(f"  {req['method']} {req['url']}")

            # Check homepage request details
            homepage_requests = [
                r
                for r in requests
                if r["url"].endswith(test_server + "/") or r["url"] == test_server + "/"
            ]
            print(f"\n=== Homepage requests: {len(homepage_requests)} ===")
            for req in homepage_requests:
                hx_request = req["headers"].get("hx-request", "not present")
                print(f"  {req['method']} {req['url']} | HX-Request: {hx_request}")

            # Verify logo is still visible
            logo = page.locator(".navbar .logo img")
            await expect(logo).to_be_visible(timeout=5000)

            # Verify only one navbar exists
            navbar_count = await page.locator(".navbar").count()
            assert navbar_count == 1, f"Expected 1 navbar after navigation, found {navbar_count}"

            # Verify logo src is correct
            logo_src = await logo.get_attribute("src")
            assert "/brand/logos/press/press-logo-64.svg" in logo_src, (
                f"Logo src incorrect after navigation: {logo_src}"
            )

        finally:
            await browser.close()


async def test_no_duplicate_navbar_after_htmx_navigation(test_server):
    """Regression test: navbar should only appear once after HTMX navigation.

    This test ensures that HTMX content swapping doesn't duplicate the navbar.
    Previously, swapping into #main-content would sometimes include a duplicate
    navbar if the swapped content incorrectly included navbar elements.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login to trigger HTMX navigation
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')

            # Wait for HTMX to complete navigation
            await expect(page.locator(".success-message")).to_be_visible(timeout=5000)
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)
            await page.wait_for_timeout(500)

            # Count navbar elements
            navbar_count = await page.locator(".navbar").count()

            # Assert exactly one navbar exists
            assert navbar_count == 1, (
                f"Expected 1 navbar after HTMX navigation, found {navbar_count}. "
                "Multiple navbars indicate content swapping is including navbar elements."
            )

            # Also verify logo appears exactly once
            logo_count = await page.locator(".navbar .logo").count()
            assert logo_count == 1, (
                f"Expected 1 logo, found {logo_count}. "
                "Multiple logos indicate duplicate navbar rendering."
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


async def test_homepage_identical_for_all_user_states(test_server):
    """Regression test: homepage must be identical for all users regardless of auth state.

    This ensures that authentication/verification status doesn't affect homepage rendering,
    particularly after middleware changes that could inadvertently block assets or alter content.

    Tests two critical cases:
    1. Unauthenticated user - no session cookies
    2. Authenticated verified user - with valid session

    Both should see identical homepage structure and assets (logo, navbar, etc).
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        try:
            # Helper to get homepage content and check structure
            async def check_homepage_structure(page, label):
                await page.goto(f"{test_server}/")
                await page.wait_for_load_state("networkidle")

                # Check that all key structural elements are present
                logo_visible = await page.locator(".navbar .logo img").is_visible()
                has_navbar = await page.locator(".navbar").count() > 0
                has_hero = await page.locator(".hero").count() > 0
                has_subjects = await page.locator(".subjects").count() > 0
                has_recent = await page.locator(".recent").count() > 0

                assert logo_visible, f"Logo not visible for {label}"
                assert has_navbar, f"Navbar missing for {label}"
                assert has_hero, f"Hero section missing for {label}"
                assert has_subjects, f"Subjects section missing for {label}"
                assert has_recent, f"Recent scrolls section missing for {label}"

                return {
                    "logo_visible": logo_visible,
                    "has_navbar": has_navbar,
                    "has_hero": has_hero,
                    "has_subjects": has_subjects,
                    "has_recent": has_recent,
                }

            # 1. Get content as unauthenticated user (no cookies)
            unauth_page = await browser.new_page()
            unauth_structure = await check_homepage_structure(unauth_page, "unauthenticated user")
            await unauth_page.close()

            # 2. Get content as authenticated verified user
            auth_page = await browser.new_page()
            await auth_page.goto(f"{test_server}/login")
            await auth_page.fill('input[name="email"]', "testuser@example.com")
            await auth_page.fill('input[name="password"]', "testpass")
            await auth_page.click('button[type="submit"]')
            await expect(auth_page.locator(".success-message")).to_be_visible(timeout=5000)
            await auth_page.wait_for_timeout(1500)  # Wait for HTMX redirect

            auth_structure = await check_homepage_structure(
                auth_page, "authenticated verified user"
            )
            await auth_page.close()

            # Both states should have identical structure
            assert unauth_structure == auth_structure, (
                f"Homepage structure differs between authentication states:\n"
                f"Unauthenticated: {unauth_structure}\n"
                f"Authenticated: {auth_structure}"
            )

        finally:
            await browser.close()
