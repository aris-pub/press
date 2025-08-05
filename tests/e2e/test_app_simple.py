"""Simple app e2e test."""

from playwright.async_api import async_playwright
import pytest

pytestmark = pytest.mark.e2e


async def test_app_setup(test_server):
    """Test that the server is running and responding."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(test_server)
        await page.wait_for_load_state("networkidle")

        title = await page.title()
        assert "Scroll Press" in title

        await browser.close()
