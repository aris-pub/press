"""Test server setup."""

from playwright.async_api import Page
import pytest

# Import from the new conftest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_server_starts(page: Page, test_server: str):
    """Test that our test server starts and serves pages."""
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
