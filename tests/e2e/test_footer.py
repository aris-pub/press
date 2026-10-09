"""E2E tests for the scroll Details modal.

Option C app shell: the scroll page is full-screen with one scrollbar, and the
scroll's metadata lives in the Details modal behind the Press-logo floating button.
The modal holds the scroll's own information and actions, not page chrome.
"""

from playwright.async_api import async_playwright
import pytest

pytestmark = pytest.mark.e2e


async def _open_details(page, test_server):
    """Open the first scroll and then its Details modal."""
    await page.goto(f"{test_server}/")
    await page.wait_for_load_state("networkidle")
    await page.locator("a.scroll-card-link").first.click()
    await page.wait_for_load_state("networkidle")
    await page.locator("#info-fab").click()
    await page.locator("#info-modal.show").wait_for()


async def test_details_modal_structure(test_server):
    """The Details modal holds the scroll metadata, license, and a Download action."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await _open_details(page, test_server)

        modal = page.locator("#info-modal")

        # Scroll metadata (from the scroll card)
        assert await modal.locator(".scroll-title").count() >= 1
        assert await modal.locator(".scroll-authors").count() >= 1

        # License info is present
        license_text = await modal.locator(".license-info").text_content()
        assert "CC BY 4.0" in license_text or "All Rights Reserved" in license_text

        # The scroll's own action is present
        assert await modal.locator("#download-btn").is_visible()

        # No page-footer content leaked into the modal
        assert await modal.locator(".platform-ctas").count() == 0
        assert await modal.locator("text=Explore More Scrolls").count() == 0

        await browser.close()


async def test_details_modal_dark_mode(test_server):
    """The Details modal displays correctly in dark mode."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await _open_details(page, test_server)

        # Enable dark mode and wait for the page background to leave white
        await page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
        await page.wait_for_function(
            """() => {
                const bg = window.getComputedStyle(document.body).backgroundColor;
                return bg !== 'rgb(255, 255, 255)' && bg !== 'rgba(0, 0, 0, 0)';
            }"""
        )

        assert await page.locator("#info-modal").is_visible()

        await browser.close()


async def test_details_modal_mobile_responsive(test_server):
    """The Details modal and its Download action are usable on a mobile viewport."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 375, "height": 667})

        await _open_details(page, test_server)

        modal = page.locator("#info-modal")
        assert await modal.is_visible()
        assert await modal.locator("#download-btn").is_visible()

        await browser.close()


async def test_details_modal_license_display(test_server):
    """The Details modal shows the license, with a Creative Commons link for CC BY."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await _open_details(page, test_server)

        license_info = page.locator("#info-modal .license-info")
        info_text = await license_info.text_content()
        assert "CC BY 4.0" in info_text or "All Rights Reserved" in info_text

        if "CC BY 4.0" in info_text:
            cc_link = page.locator('#info-modal a[href*="creativecommons.org"]')
            assert await cc_link.count() >= 1

        await browser.close()
