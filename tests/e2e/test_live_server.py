"""E2E tests against a live development server.

Run these tests against a running development server:
    just dev  # Start the development server
    uv run pytest tests/e2e/test_live_server.py -v
"""

from playwright.async_api import async_playwright
import pytest

pytestmark = pytest.mark.e2e

# Configuration will be provided by test_server fixture


async def test_homepage_loads(test_server):
    """Test that the homepage loads correctly."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Visit homepage
            await page.goto(test_server)
            await page.wait_for_load_state("networkidle")

            # Check title
            title = await page.title()
            assert "Scroll Press" in title

            # Check hero section
            hero = page.locator(".hero")
            await hero.wait_for()

            # Check search box exists
            search_box = page.locator(".search-box")
            await search_box.wait_for()

            # Check subjects section
            subjects = page.locator(".subjects")
            await subjects.wait_for()

        finally:
            await browser.close()


async def test_navigation_to_register(test_server):
    """Test navigation to register page."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(test_server)
            await page.wait_for_load_state("networkidle")

            # Click register link (shows as "New Scroll") - use first one
            register_link = page.locator('a[href="/register"]').first
            await register_link.click()

            await page.wait_for_load_state("networkidle")

            # Should be on register page
            assert "/register" in page.url

            # Should see registration form
            form = page.locator("form")
            await form.wait_for()

            # Should see required fields
            await page.locator('input[name="email"]').wait_for()
            await page.locator('input[name="password"]').wait_for()
            await page.locator('input[name="display_name"]').wait_for()

        finally:
            await browser.close()


async def test_user_registration_flow(test_server):
    """Test complete user registration flow.

    This tests registration → auto-login → redirect to homepage.
    """
    import uuid

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Generate unique test user
            test_id = uuid.uuid4().hex[:8]
            email = f"e2etest_{test_id}@example.com"
            password = "testpass123"
            display_name = f"E2E Test User {test_id}"

            # Go to register page
            await page.goto(f"{test_server}/register")
            await page.wait_for_load_state("networkidle")

            # Fill registration form
            await page.fill('input[name="email"]', email)
            await page.fill('input[name="display_name"]', display_name)
            await page.fill('input[name="password"]', password)

            # Accept terms
            await page.check('input[name="agree_terms"]')

            # Submit form (HTMX form, so no page redirect expected)
            await page.click('button[type="submit"]')

            # Wait for HTMX response - either success (content changes) or error (form stays)
            await page.wait_for_timeout(2000)  # Give HTMX time to process

            # Check if we still have the registration form (indicates failure)
            register_form = page.locator("#register-form-container")
            if await register_form.count() > 0:
                # Look for error messages in the form area
                error_msgs = page.locator(".form-error, .error-message, .alert-danger")
                if await error_msgs.count() > 0:
                    error_text = await error_msgs.first.text_content()
                    raise AssertionError(f"Registration failed with error: {error_text}")
                else:
                    raise AssertionError(
                        "Registration form submission failed - no redirect occurred"
                    )

            # Look for success message which auto-redirects after 1 second
            success_msg = page.locator("text=Account Created!")

            # If we see the success message, wait for automatic HTMX redirect
            if await success_msg.count() > 0:
                # Wait for HTMX auto-redirect (delay:1s in template)
                await page.wait_for_timeout(2000)
                await page.wait_for_load_state("networkidle")

            # Wait for any additional redirects
            await page.wait_for_timeout(500)

            # Verify we're logged in by checking for user menu trigger (logout is inside dropdown)
            current_url = page.url
            is_on_homepage = current_url in [
                test_server,
                f"{test_server}/",
                f"{test_server}/dashboard",
            ]
            has_user_menu = await page.locator(".user-menu-trigger").count() > 0

            if not (is_on_homepage and has_user_menu):
                raise AssertionError(
                    f"Registration should redirect to homepage with user menu visible. "
                    f"URL: {current_url}, has_user_menu: {has_user_menu}"
                )

        finally:
            await browser.close()
