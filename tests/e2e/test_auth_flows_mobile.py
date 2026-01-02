"""Mobile-specific e2e tests for authentication flows."""

import time

from playwright.async_api import async_playwright, expect
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.mobile]

# Mobile device viewport
MOBILE_VIEWPORT = {"width": 375, "height": 667}  # iPhone SE


@pytest.mark.mobile
async def test_complete_login_flow_mobile(test_server):
    """Test complete user login flow using mobile navigation UI."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(has_touch=True, viewport=MOBILE_VIEWPORT)
        page = await context.new_page()

        try:
            # First register a user to login with
            await page.goto(f"{test_server}/register")

            timestamp = int(time.time())
            test_email = f"mobile-logintest-{timestamp}@example.com"
            await page.fill('input[name="email"]', test_email)
            await page.fill('input[name="display_name"]', "Login Test User")
            await page.fill('input[name="password"]', "loginpassword")
            await page.fill('input[name="confirm_password"]', "loginpassword")
            await page.check('input[name="agree_terms"]')
            await page.click('button[type="submit"]')

            # Wait for HTMX form submission to complete
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1000)

            # Registration should succeed - user is now logged in but unverified
            # Check that we're logged in by checking for session (cookies should be set)
            cookies = await page.context.cookies()
            has_session = any(cookie["name"] == "session_id" for cookie in cookies)
            assert has_session, "Registration should set session cookie"

            # For E2E testing, manually verify user by making HTTP request to a test endpoint
            # In production, user would click link in verification email
            import httpx

            async with httpx.AsyncClient() as http_client:
                # Use httpx to update user verification status
                # This is a workaround for E2E tests - in production users verify via email link
                await http_client.post(
                    f"{test_server}/test-verify-user", json={"email": test_email}
                )

            # Navigate to homepage to get logged in experience
            await page.goto(f"{test_server}/")
            await page.wait_for_timeout(500)

            # Now test logout using mobile navigation
            # Open mobile menu first
            mobile_menu_toggle = page.locator(".mobile-menu-toggle")
            await mobile_menu_toggle.click()
            await page.wait_for_timeout(200)  # Wait for menu to open

            # Verify mobile menu is open
            mobile_nav = page.locator(".mobile-nav")
            is_open = await mobile_nav.evaluate("el => el.classList.contains('open')")
            assert is_open, "Mobile menu should be open after clicking toggle"

            # Click mobile logout button
            mobile_logout = page.locator('.mobile-nav form[action="/logout"] button')
            await expect(mobile_logout).to_be_visible()
            await mobile_logout.click()

            await page.wait_for_load_state("networkidle")

            # Navigate to login page
            await page.goto(f"{test_server}/login")

            # Should have login form elements
            await expect(page.locator('input[name="email"]')).to_be_visible()
            await expect(page.locator('input[name="password"]')).to_be_visible()

            # Fill and submit login form
            await page.fill('input[name="email"]', test_email)
            await page.fill('input[name="password"]', "loginpassword")
            await page.click('button[type="submit"]')

            # Wait for login response
            await page.wait_for_timeout(1500)

            # Check for login success
            page_content = (await page.content()).lower()
            current_url = page.url

            login_success = (
                current_url == f"{test_server}/"
                or current_url == f"{test_server}/dashboard"
                or "logout" in page_content
                or "dashboard" in page_content
            )

            assert login_success, f"Login did not succeed. URL: {current_url}"

        finally:
            await browser.close()


@pytest.mark.mobile
async def test_registration_duplicate_email_mobile(test_server):
    """Test registration with already registered email using mobile logout."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(has_touch=True, viewport=MOBILE_VIEWPORT)
        page = await context.new_page()

        try:
            # Register first user
            await page.goto(f"{test_server}/register")

            timestamp = int(time.time())
            test_email = f"mobile-duplicate-{timestamp}@example.com"
            await page.fill('input[name="email"]', test_email)
            await page.fill('input[name="display_name"]', "First User")
            await page.fill('input[name="password"]', "password123")
            await page.fill('input[name="confirm_password"]', "password123")
            await page.check('input[name="agree_terms"]')
            await page.click('button[type="submit"]')

            await page.wait_for_load_state("networkidle")

            # User should see success message
            await expect(page.locator("text=Welcome to Scroll Press")).to_be_visible()

            # For E2E testing, manually verify user via test endpoint
            import httpx

            async with httpx.AsyncClient() as http_client:
                await http_client.post(
                    f"{test_server}/test-verify-user", json={"email": test_email}
                )

            # Navigate to homepage to get logged in experience
            await page.goto(f"{test_server}/")
            await page.wait_for_timeout(500)

            # Logout the first user using mobile navigation
            # Open mobile menu
            mobile_menu_toggle = page.locator(".mobile-menu-toggle")
            await mobile_menu_toggle.click()
            await page.wait_for_timeout(200)

            # Click mobile logout button
            mobile_logout = page.locator('.mobile-nav form[action="/logout"] button')
            await expect(mobile_logout).to_be_visible()
            await mobile_logout.click()

            # Wait for logout to complete
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(500)

            # Try to register second user with same email
            await page.goto(f"{test_server}/register")

            await page.fill('input[name="email"]', test_email)
            await page.fill('input[name="display_name"]', "Second User")
            await page.fill('input[name="password"]', "password456")
            await page.fill('input[name="confirm_password"]', "password456")
            await page.check('input[name="agree_terms"]')
            await page.click('button[type="submit"]')

            # Should show duplicate email error
            await expect(page.locator('li:has-text("Email already registered")')).to_be_visible()

        finally:
            await browser.close()


@pytest.mark.mobile
async def test_mobile_menu_navigation(test_server):
    """Test mobile navigation menu functionality."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(has_touch=True, viewport=MOBILE_VIEWPORT)
        page = await context.new_page()

        try:
            await page.goto(f"{test_server}/")

            # Mobile menu toggle should be visible
            mobile_menu_toggle = page.locator(".mobile-menu-toggle")
            await expect(mobile_menu_toggle).to_be_visible()

            # Mobile nav should initially be closed
            mobile_nav = page.locator(".mobile-nav")

            # Click toggle to open menu
            await mobile_menu_toggle.click()
            await page.wait_for_timeout(200)

            # Menu should now be open
            is_open = await mobile_nav.evaluate("el => el.classList.contains('open')")
            assert is_open, "Mobile menu should be open"

            # Navigation links should be visible
            await expect(page.locator('.mobile-nav a[href="/#browse"]')).to_be_visible()
            await expect(page.locator('.mobile-nav a[href="/#recent"]')).to_be_visible()
            await expect(page.locator('.mobile-nav a[href="/about"]')).to_be_visible()

            # Click a navigation link
            await page.locator('.mobile-nav a[href="/about"]').click()
            await page.wait_for_load_state("networkidle")

            # Should navigate to about page and menu should close
            assert "/about" in page.url

        finally:
            await browser.close()


@pytest.mark.mobile
async def test_mobile_dark_mode_toggle_visibility(test_server):
    """Test that dark mode toggle is accessible in mobile view."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(has_touch=True, viewport=MOBILE_VIEWPORT)
        page = await context.new_page()

        try:
            await page.goto(f"{test_server}/")

            # Mobile dark mode toggle should be visible
            mobile_dark_toggle = page.locator(".mobile-dark-mode-toggle .dark-mode-toggle")
            await expect(mobile_dark_toggle).to_be_visible()

            # Test toggle functionality
            await mobile_dark_toggle.click()
            await page.wait_for_timeout(100)

            # Verify theme was set
            theme_after_toggle = await page.evaluate("""
                () => {
                    return {
                        currentTheme: document.documentElement.getAttribute('data-theme'),
                        storedTheme: localStorage.getItem('theme')
                    };
                }
            """)

            assert theme_after_toggle["currentTheme"] in ["dark", "light"]
            assert theme_after_toggle["storedTheme"] == theme_after_toggle["currentTheme"]

        finally:
            await browser.close()
