"""Essential e2e tests for core functionality only.

Minimal tests to verify basic functionality without timeouts.
"""

from playwright.async_api import async_playwright, expect
import pytest

pytestmark = pytest.mark.e2e


async def test_basic_upload_flow(test_server):
    """Test basic upload page redirects to login (auth required)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Upload page should redirect to login when not authenticated
            await page.goto(f"{test_server}/upload")

            # Should be redirected to login page
            await expect(page.locator('input[name="email"]')).to_be_visible()
            await expect(page.locator('input[name="password"]')).to_be_visible()

        finally:
            await browser.close()


async def test_homepage_loads(test_server):
    """Test homepage loads correctly."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(test_server)
            body = page.locator("body")
            await expect(body).to_be_visible()

            # Should have main navigation (first nav element)
            await expect(page.locator("nav").first).to_be_visible()

        finally:
            await browser.close()


async def test_register_page_loads(test_server):
    """Test registration page loads correctly."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(f"{test_server}/register")
            body = page.locator("body")
            await expect(body).to_be_visible()

            # Should have registration form
            await expect(page.locator('input[name="email"]')).to_be_visible()
            await expect(page.locator('input[name="password"]')).to_be_visible()

        finally:
            await browser.close()
