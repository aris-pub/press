"""Basic e2e test to verify Playwright setup."""

from playwright.async_api import async_playwright
import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_basic_playwright():
    """Test basic Playwright functionality without fixtures."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("https://example.com")
        title = await page.title()
        assert "Example Domain" in title

        await browser.close()
