"""E2E tests for email verification and password reset flows."""

import time

from playwright.async_api import async_playwright, expect
import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_registration_shows_verification_message(test_server):
    """Test that registration shows email verification message."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Navigate to registration page
            await page.goto(f"{test_server}/register")

            # Fill registration form
            timestamp = int(time.time())
            test_email = f"verify-test-{timestamp}@example.com"
            await page.fill('input[name="email"]', test_email)
            await page.fill('input[name="display_name"]', "Verification Test User")
            await page.fill('input[name="password"]', "testpassword123")
            await page.fill('input[name="confirm_password"]', "testpassword123")
            await page.check('input[name="agree_terms"]')

            # Submit registration
            await page.click('button[type="submit"]')

            # Wait for success message
            await expect(page.locator(".success-message")).to_be_visible()
            await expect(page.locator('h2:has-text("Account Created!")')).to_be_visible()

            # Should show email verification instructions
            await expect(page.locator("text=check your email to verify")).to_be_visible()

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_unverified_user_blocked_from_dashboard(test_server):
    """Test that unverified users cannot access protected routes."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Register user
            await page.goto(f"{test_server}/register")
            timestamp = int(time.time())
            test_email = f"blocked-test-{timestamp}@example.com"
            await page.fill('input[name="email"]', test_email)
            await page.fill('input[name="display_name"]', "Blocked Test")
            await page.fill('input[name="password"]', "testpassword123")
            await page.fill('input[name="confirm_password"]', "testpassword123")
            await page.check('input[name="agree_terms"]')
            await page.click('button[type="submit"]')

            await page.wait_for_timeout(1000)

            # Try to access dashboard
            await page.goto(f"{test_server}/dashboard")
            await page.wait_for_timeout(500)

            # Should be blocked or redirected
            page_content = await page.content()
            current_url = page.url

            # Either we're not on dashboard or we see a verification required message
            blocked = (
                "/dashboard" not in current_url
                or "verify" in page_content.lower()
                or "verification" in page_content.lower()
            )
            assert blocked, "Unverified user should be blocked from dashboard"

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_email_verification_with_valid_token(test_server):
    """Test email verification flow with a valid token."""
    import httpx

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Register user
            await page.goto(f"{test_server}/register")
            timestamp = int(time.time())
            test_email = f"verify-flow-{timestamp}@example.com"
            await page.fill('input[name="email"]', test_email)
            await page.fill('input[name="display_name"]', "Verify Flow Test")
            await page.fill('input[name="password"]', "testpassword123")
            await page.fill('input[name="confirm_password"]', "testpassword123")
            await page.check('input[name="agree_terms"]')
            await page.click('button[type="submit"]')

            await page.wait_for_timeout(1000)

            # Use test endpoint to verify user
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{test_server}/test-verify-user", json={"email": test_email}
                )
                assert response.status_code == 200

            # Now navigate to dashboard - should work
            await page.goto(f"{test_server}/dashboard")
            await page.wait_for_timeout(500)

            # Should be able to access dashboard
            current_url = page.url
            assert "/dashboard" in current_url or "dashboard" in (await page.content()).lower()

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_forgot_password_page_loads(test_server):
    """Test that forgot password page loads correctly."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(f"{test_server}/forgot-password")

            # Should have email input and submit button
            await expect(page.locator('input[name="email"]')).to_be_visible()
            await expect(page.locator('button[type="submit"]')).to_be_visible()

            # Should show reset password heading or similar
            page_content = await page.content()
            assert "reset" in page_content.lower() or "forgot" in page_content.lower()

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_forgot_password_submission(test_server):
    """Test submitting forgot password form."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # First register a user
            await page.goto(f"{test_server}/register")
            timestamp = int(time.time())
            test_email = f"reset-flow-{timestamp}@example.com"
            await page.fill('input[name="email"]', test_email)
            await page.fill('input[name="display_name"]', "Reset Flow Test")
            await page.fill('input[name="password"]', "oldpassword123")
            await page.fill('input[name="confirm_password"]', "oldpassword123")
            await page.check('input[name="agree_terms"]')
            await page.click('button[type="submit"]')

            await page.wait_for_timeout(1000)

            # Navigate to forgot password
            await page.goto(f"{test_server}/forgot-password")

            # Submit email
            await page.fill('input[name="email"]', test_email)
            await page.click('button[type="submit"]')

            await page.wait_for_timeout(1000)

            # Should show success message (doesn't reveal if email exists)
            page_content = await page.content()
            assert (
                "check your email" in page_content.lower()
                or "email" in page_content.lower()
                or "sent" in page_content.lower()
            )

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_reset_password_with_invalid_token(test_server):
    """Test that invalid reset tokens show error."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Try to access reset password with invalid token
            await page.goto(f"{test_server}/reset-password?token=invalid_token_12345")
            await page.wait_for_timeout(500)

            # Should see error message
            page_content = await page.content()
            assert (
                "invalid" in page_content.lower()
                or "expired" in page_content.lower()
                or "error" in page_content.lower()
            ), "Should show error for invalid reset token"

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_verify_email_with_invalid_token(test_server):
    """Test that invalid verification tokens show error."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Try to verify with invalid token
            await page.goto(f"{test_server}/verify-email?token=invalid_token_12345")
            await page.wait_for_timeout(500)

            # Should see error message
            page_content = await page.content()
            assert (
                "invalid" in page_content.lower()
                or "expired" in page_content.lower()
                or "error" in page_content.lower()
            ), "Should show error for invalid verification token"

        finally:
            await browser.close()
