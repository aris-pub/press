"""Minimal e2e test."""

from playwright.async_api import async_playwright
import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_minimal():
    """Minimal test to verify everything works."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("https://httpbin.org/get")
        content = await page.content()
        assert "httpbin" in content.lower()

        await browser.close()
