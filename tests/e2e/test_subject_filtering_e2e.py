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
            await page.wait_for_selector(".scroll.preview")

            # Test basic filtering functionality with seeded data
            # Check if Physics subject exists in seeded data
            physics_subject_card = page.locator('.subject-card:has-text("Physics")')
            if await physics_subject_card.count() > 0:
                await physics_subject_card.click()
                await page.wait_for_timeout(200)

                # Check that heading updated to show physics filter
                heading = page.locator("#recent-submissions-heading")
                heading_text = await heading.text_content()
                assert "Recent Physics Scrolls" in heading_text

                # Click again to deselect
                await physics_subject_card.click()
                await page.wait_for_timeout(200)

                # Verify heading is back to "Recent Scrolls"
                heading_text = await heading.text_content()
                assert heading_text == "Recent Scrolls"

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

            # Show All button should start with "active" class (showing all by default)
            btn_classes = await show_all_btn.get_attribute("class")
            assert "active" in btn_classes

            # Try to find a subject to filter by
            first_subject_card = page.locator(".subject-card").first
            if await first_subject_card.count() > 0:
                await first_subject_card.click()
                await page.wait_for_timeout(200)

                # Show All button should no longer have "active" class
                btn_classes = await show_all_btn.get_attribute("class")
                assert "active" not in btn_classes

                # Click Show All button
                await show_all_btn.click()
                await page.wait_for_timeout(200)

                # Verify heading is back to "Recent Scrolls"
                heading = page.locator("#recent-submissions-heading")
                heading_text = await heading.text_content()
                assert heading_text == "Recent Scrolls"

                # Show All button should now have "active" class again
                btn_classes = await show_all_btn.get_attribute("class")
                assert "active" in btn_classes

        finally:
            await browser.close()
