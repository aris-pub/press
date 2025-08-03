"""Test server setup."""

from playwright.async_api import async_playwright
import pytest


@pytest.mark.e2e
async def test_server_starts(test_server: str):
    """Test that our test server starts and serves pages."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Visit homepage
        await page.goto(test_server)
        await page.wait_for_load_state("networkidle")

        # Should see the Scroll Press homepage
        title = await page.title()
        assert "Scroll Press" in title

        # Should see hero section
        hero = page.locator(".hero")
        await hero.wait_for()

        hero_text = await hero.text_content()
        assert "Scroll Press" in hero_text

        await browser.close()
