"""E2E test: Show All button should be enabled when filter is active."""

from playwright.async_api import async_playwright
import pytest

pytestmark = pytest.mark.e2e


async def test_show_all_button_disabled_when_no_filter(test_server):
    """Show All button should be disabled when showing all scrolls."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"{test_server}/")
        await page.wait_for_load_state("networkidle")

        # Button should have 'active' class when no filter is active
        button = page.locator("#show-all-btn")
        classes = await button.get_attribute("class")

        assert "active" in classes, (
            "Show All button should be disabled (have 'active' class) when no filter is active"
        )

        await browser.close()


async def test_show_all_button_enabled_when_filter_active(test_server):
    """REGRESSION: Show All button should be enabled when subject filter is active."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"{test_server}/")
        await page.wait_for_load_state("networkidle")

        # Click a subject button to activate filter
        await page.locator("button.subject-card").first.click()
        await page.wait_for_timeout(1000)

        # Button should NOT have 'active' class when filter is active
        button = page.locator("#show-all-btn")
        classes = await button.get_attribute("class")

        assert "active" not in classes, (
            "REGRESSION: Show All button should be enabled (no 'active' class) "
            "when subject filter is active. This allows users to clear the filter."
        )

        await browser.close()


async def test_show_all_button_becomes_disabled_after_clicking(test_server):
    """Show All button should become disabled after clicking it."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"{test_server}/")
        await page.wait_for_load_state("networkidle")

        # Click subject to enable Show All button
        await page.locator("button.subject-card").first.click()
        await page.wait_for_timeout(1000)

        # Click Show All button
        await page.locator("#show-all-btn").click()
        await page.wait_for_timeout(1000)

        # Button should be disabled again
        button = page.locator("#show-all-btn")
        classes = await button.get_attribute("class")

        assert "active" in classes, (
            "Show All button should be disabled after clicking it (filter is cleared)"
        )

        await browser.close()
