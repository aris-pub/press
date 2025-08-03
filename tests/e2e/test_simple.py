"""Simple e2e test to verify setup works."""

from playwright.async_api import async_playwright
import pytest


@pytest.mark.e2e
async def test_playwright_works():
    """Test that Playwright basic functionality works."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("https://example.com")
        await page.wait_for_load_state("networkidle")

        title = await page.title()
        assert "Example Domain" in title

        # Test that we can interact with elements
        heading = page.locator("h1")
        await heading.wait_for()
        heading_text = await heading.text_content()
        assert "Example Domain" in heading_text

        await browser.close()
