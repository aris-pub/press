"""E2E tests against a live development server.

Run these tests against a running development server:
    just dev  # Start the development server
    uv run pytest tests/e2e/test_live_server.py -v
"""

from playwright.async_api import async_playwright
import pytest

# Configuration - adjust this to match your dev server
DEV_SERVER_URL = "http://localhost:8000"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_homepage_loads():
    """Test that the homepage loads correctly."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Visit homepage
            await page.goto(DEV_SERVER_URL)
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


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_navigation_to_register():
    """Test navigation to register page."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(DEV_SERVER_URL)
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


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_user_registration_flow():
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
            await page.goto(f"{DEV_SERVER_URL}/register")
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

            # Wait for any redirects after successful HTMX response
            await page.wait_for_timeout(1000)

            # Verify we're logged in by checking for authenticated user elements
            current_url = page.url
            is_on_homepage = current_url in [DEV_SERVER_URL, f"{DEV_SERVER_URL}/"]
            has_logout_btn = await page.locator('button:has-text("Logout")').count() > 0

            # Registration should result in being logged in and on homepage
            assert is_on_homepage and has_logout_btn, (
                "Registration should redirect to homepage with logout button visible"
            )

        finally:
            await browser.close()
