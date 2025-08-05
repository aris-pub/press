"""Simple app e2e test."""

from playwright.async_api import async_playwright
import pytest

pytestmark = pytest.mark.e2e


async def test_app_setup(test_server, seeded_database):
    """Test that our test app setup works."""
    # Just verify fixtures are working
    assert test_server is not None
    assert seeded_database is not None
    assert len(seeded_database["subjects"]) == 4
    assert len(seeded_database["users"]) == 2

    # Test basic page functionality using direct playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(test_server)
        title = await page.title()
        assert "Scroll Press" in title

        await browser.close()
