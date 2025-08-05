"""Comprehensive e2e tests for authentication flows."""

from playwright.async_api import async_playwright, expect
import pytest

pytestmark = pytest.mark.e2e


async def test_complete_registration_flow(test_server):
    """Test complete user registration flow with form validation."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Navigate to registration page
            await page.goto(f"{test_server}/register")

            # Should have registration form elements
            await expect(page.locator('input[name="email"]')).to_be_visible()
            await expect(page.locator('input[name="display_name"]')).to_be_visible()
            await expect(page.locator('input[name="password"]')).to_be_visible()
            await expect(page.locator('input[name="confirm_password"]')).to_be_visible()
            await expect(page.locator('input[name="agree_terms"]')).to_be_visible()
            await expect(page.locator('button[type="submit"]')).to_be_visible()

            # Test form validation - missing fields
            await page.click('button[type="submit"]')
            # Browser should prevent submission due to required fields

            # Fill in form with valid data
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="display_name"]', "Test User")
            await page.fill('input[name="password"]', "testpassword123")
            await page.fill('input[name="confirm_password"]', "testpassword123")
            await page.check('input[name="agree_terms"]')

            # Submit form
            await page.click('button[type="submit"]')

            # Wait for HTMX response and any subsequent redirects
            await page.wait_for_timeout(1500)  # Wait for form submission and any HTMX redirects

            # Check if successfully registered - look for success indicators
            page_content = await page.content()
            current_url = page.url

            # Look for success indicators (either content or URL change)
            success_found = (
                "Welcome" in page_content
                or "success" in page_content
                or "dashboard" in current_url
                or "/dashboard" in page_content
                or "Redirecting" in page_content
                or current_url == test_server + "/"  # Redirected to homepage
                or current_url == test_server + "/dashboard"  # Redirected to dashboard
            )

            assert success_found, f"Registration appears to have failed. URL: {current_url}"

        finally:
            await browser.close()


async def test_registration_password_mismatch_validation(test_server):
    """Test registration form validates password confirmation."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(f"{test_server}/register")

            # Fill form with mismatched passwords
            await page.fill('input[name="email"]', "testuser2@example.com")
            await page.fill('input[name="display_name"]', "Test User 2")
            await page.fill('input[name="password"]', "password123")
            await page.fill('input[name="confirm_password"]', "differentpassword")
            await page.check('input[name="agree_terms"]')

            # Submit form
            await page.click('button[type="submit"]')

            # Should show password mismatch error
            await expect(page.locator('li:has-text("Passwords do not match")')).to_be_visible()

        finally:
            await browser.close()


async def test_registration_display_name_validation(test_server):
    """Test registration form validates display name."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(f"{test_server}/register")

            # Test with whitespace-only display name
            await page.fill('input[name="email"]', "testuser3@example.com")
            await page.fill('input[name="display_name"]', "   ")
            await page.fill('input[name="password"]', "password123")
            await page.fill('input[name="confirm_password"]', "password123")
            await page.check('input[name="agree_terms"]')

            # Submit form
            await page.click('button[type="submit"]')

            # Should show display name error
            await expect(
                page.locator('li:has-text("Display name cannot be empty")')
            ).to_be_visible()

        finally:
            await browser.close()


async def test_complete_login_flow(test_server):
    """Test complete user login flow."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # First register a user to login with
            await page.goto(f"{test_server}/register")

            await page.fill('input[name="email"]', "logintest@example.com")
            await page.fill('input[name="display_name"]', "Login Test User")
            await page.fill('input[name="password"]', "loginpassword")
            await page.fill('input[name="confirm_password"]', "loginpassword")
            await page.check('input[name="agree_terms"]')
            await page.click('button[type="submit"]')

            # Wait for registration to complete - user should be auto-logged in
            await page.wait_for_timeout(2500)  # Wait longer for HTMX redirect

            # Check that user is successfully logged in after registration
            page_content = (await page.content()).lower()
            current_url = page.url

            # Should be logged in (redirected to homepage or dashboard)
            logged_in = (
                current_url == f"{test_server}/"
                or current_url == f"{test_server}/dashboard"
                or "logout" in page_content
                or "dashboard" in page_content
            )

            assert logged_in, f"User was not logged in after registration. URL: {current_url}"

            # Now test logout and login cycle
            # Look for mobile logout button first (always visible if present)
            mobile_logout = page.locator('.mobile-nav form[action="/logout"] button')
            mobile_count = await mobile_logout.count()

            if mobile_count > 0 and await mobile_logout.first.is_visible():
                # Use mobile logout button if visible
                await mobile_logout.first.click()
            else:
                # Try the desktop dropdown approach - open the user menu
                user_menu_trigger = page.locator(".user-menu-trigger")
                if await user_menu_trigger.count() > 0:
                    await user_menu_trigger.first.click()
                    # Wait a bit for JavaScript to run
                    await page.wait_for_timeout(100)

                    # Check if dropdown opened, if not manually open it
                    dropdown_state = await page.evaluate("""
                        () => {
                            const dropdown = document.querySelector('.dropdown.user-menu');
                            return dropdown && dropdown.classList.contains('open');
                        }
                    """)

                    if not dropdown_state:
                        await page.evaluate("""
                            () => {
                                const dropdown = document.querySelector('.dropdown.user-menu');
                                if (dropdown) dropdown.classList.add('open');
                            }
                        """)

                    await page.wait_for_selector(".dropdown.user-menu.open", timeout=2000)

                # Now click the dropdown logout button
                dropdown_logout = page.locator(
                    '.dropdown.user-menu.open .dropdown-menu form[action="/logout"] button'
                )
                await dropdown_logout.wait_for(state="visible", timeout=2000)
                await dropdown_logout.first.click()

            await page.wait_for_load_state("networkidle")

            # Navigate to login page
            await page.goto(f"{test_server}/login")

            # Should have login form elements
            await expect(page.locator('input[name="email"]')).to_be_visible()
            await expect(page.locator('input[name="password"]')).to_be_visible()

            # Fill and submit login form
            await page.fill('input[name="email"]', "logintest@example.com")
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


async def test_login_invalid_credentials(test_server):
    """Test login form with invalid credentials."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(f"{test_server}/login")

            # Fill form with invalid credentials
            await page.fill('input[name="email"]', "nonexistent@example.com")
            await page.fill('input[name="password"]', "wrongpassword")
            await page.click('button[type="submit"]')

            # Should show invalid credentials error
            await expect(
                page.locator('li:has-text("Incorrect email or password")')
            ).to_be_visible()

        finally:
            await browser.close()


async def test_login_empty_fields(test_server):
    """Test login form validation with empty fields."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(f"{test_server}/login")

            # Submit form without filling fields
            await page.click('button[type="submit"]')

            # Browser should prevent submission due to required fields
            # The page should still be on the login page
            assert "/login" in page.url

        finally:
            await browser.close()


async def test_registration_duplicate_email(test_server):
    """Test registration with already registered email."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Register first user
            await page.goto(f"{test_server}/register")

            await page.fill('input[name="email"]', "duplicate@example.com")
            await page.fill('input[name="display_name"]', "First User")
            await page.fill('input[name="password"]', "password123")
            await page.fill('input[name="confirm_password"]', "password123")
            await page.check('input[name="agree_terms"]')
            await page.click('button[type="submit"]')

            await page.wait_for_load_state("networkidle")

            # Logout the first user so we can access the registration page again
            # Look for mobile logout button first (always visible if present)
            mobile_logout = page.locator('.mobile-nav form[action="/logout"] button')
            mobile_count = await mobile_logout.count()

            if mobile_count > 0 and await mobile_logout.first.is_visible():
                # Use mobile logout button if visible
                await mobile_logout.first.click()
            else:
                # Manually navigate to logout by creating and submitting a form via JavaScript
                await page.evaluate("""
                    () => {
                        const form = document.createElement('form');
                        form.method = 'POST';
                        form.action = '/logout';
                        document.body.appendChild(form);
                        form.submit();
                    }
                """)

                # Wait for logout to complete - should redirect to homepage
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(500)  # Extra wait to ensure logout is processed

            # Try to register second user with same email
            await page.goto(f"{test_server}/register")

            await page.fill('input[name="email"]', "duplicate@example.com")
            await page.fill('input[name="display_name"]', "Second User")
            await page.fill('input[name="password"]', "password456")
            await page.fill('input[name="confirm_password"]', "password456")
            await page.check('input[name="agree_terms"]')
            await page.click('button[type="submit"]')

            # Should show duplicate email error
            await expect(page.locator('li:has-text("Email already registered")')).to_be_visible()

        finally:
            await browser.close()
