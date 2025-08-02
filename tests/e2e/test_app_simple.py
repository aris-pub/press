"""Simple app e2e test."""

from playwright.async_api import Page
import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_app_setup(page: Page, test_app, seeded_database):
    """Test that our test app setup works."""
    # Just verify fixtures are working
    assert test_app is not None
    assert seeded_database is not None
    assert len(seeded_database["subjects"]) == 4
    assert len(seeded_database["users"]) == 2

    # Test basic page functionality
    await page.goto("https://example.com")
    title = await page.title()
    assert "Example Domain" in title
