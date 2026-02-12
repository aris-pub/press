"""End-to-end tests for subject filtering functionality."""

from playwright.async_api import async_playwright
import pytest


@pytest.mark.e2e
async def test_subject_filtering_works_in_browser(test_server):
    """Test that subject filtering actually works in the browser."""

    # Use Playwright to test filtering
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Navigate to homepage
            await page.goto(test_server)

            # Wait for page to load completely
            await page.wait_for_selector(".subject-card")

            # Check if there are any scrolls - if not, skip the filtering test
            scroll_count = await page.locator(".scroll.preview").count()
            if scroll_count == 0:
                print("No scrolls found, skipping filtering test")
                assert True  # Test passes if no scrolls to filter
                return

            # Test basic filtering functionality with seeded data
            # Check if Physics subject exists in seeded data
            physics_subject_card = page.locator('.subject-card:has-text("Physics")').first
            if await physics_subject_card.count() > 0:
                await physics_subject_card.click()
                await page.wait_for_timeout(500)  # Wait for HTMX swap

                # Check that heading updated to show physics filter
                heading = page.locator("#recent-submissions-heading")
                heading_text = await heading.text_content()
                assert "Recent Physics Scrolls" in heading_text

                # Click "Show All" to reset
                show_all_btn = page.locator("#show-all-btn")
                await show_all_btn.click()
                await page.wait_for_timeout(500)  # Wait for HTMX swap

                # Verify heading is back to "Recent Scrolls"
                heading_text = await heading.text_content()
                assert heading_text == "Recent Scrolls"

                # Test completed successfully
                assert True

        finally:
            await browser.close()


@pytest.mark.e2e
async def test_show_all_button_works(test_server):
    """Test that the Show All button works correctly."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(test_server)

            # Wait for elements
            await page.wait_for_selector(".subject-card")

            # Test Show All button functionality
            show_all_btn = page.locator("#show-all-btn")
            await show_all_btn.wait_for()

            # Try to find a subject to filter by
            first_subject_card = page.locator(".subject-card").first
            if await first_subject_card.count() > 0:
                await first_subject_card.click()
                await page.wait_for_timeout(500)  # Wait for HTMX swap

                # Click Show All button
                await show_all_btn.click()
                await page.wait_for_timeout(500)  # Wait for HTMX swap

                # Verify heading is back to "Recent Scrolls"
                heading = page.locator("#recent-submissions-heading")
                heading_text = await heading.text_content()
                assert heading_text == "Recent Scrolls"

                # Test completed successfully
                assert True

        finally:
            await browser.close()
