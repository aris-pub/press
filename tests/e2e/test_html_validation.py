"""E2E tests for HTML validation during upload."""

from playwright.async_api import async_playwright, expect
import pytest

pytestmark = pytest.mark.e2e


async def test_upload_page_loads_and_requires_auth(test_server):
    """Test that upload page redirects to login when not authenticated."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Navigate to upload page (should redirect to login)
            await page.goto(f"{test_server}/upload")

            # Should be redirected to login page
            await expect(page.locator('input[name="email"]')).to_be_visible()
            await expect(page.locator('input[name="password"]')).to_be_visible()

            # Should have login form elements
            await expect(page.locator("form")).to_be_visible()

        finally:
            await browser.close()


async def test_register_page_has_form_elements(test_server):
    """Test that register page loads and has required form elements."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Navigate to register page
            await page.goto(f"{test_server}/register")

            # Should have registration form elements
            await expect(page.locator('input[name="email"]')).to_be_visible()
            await expect(page.locator('input[name="password"]')).to_be_visible()
            await expect(page.locator("form")).to_be_visible()

        finally:
            await browser.close()
