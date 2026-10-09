"""E2E tests for the scroll Details modal.

Option C app shell: the scroll page is full-screen with one scrollbar, and the
metadata, platform links, and Aris attribution that used to sit in an on-page
footer now live in the Details modal behind the Press-logo floating button.
"""

from playwright.async_api import async_playwright
import pytest

pytestmark = pytest.mark.e2e


async def _goto_first_scroll(page, test_server):
    """Open the first scroll from the homepage."""
    await page.goto(f"{test_server}/")
    await page.wait_for_load_state("networkidle")
    await page.locator("a.scroll-card-link").first.click()
    await page.wait_for_load_state("networkidle")


async def _open_details(page, test_server):
    """Open the first scroll and then its Details modal."""
    await _goto_first_scroll(page, test_server)
    await page.locator("#info-fab").click()
    await page.locator("#info-modal.show").wait_for()


async def test_details_modal_structure(test_server):
    """The Details modal holds the scroll metadata, platform links, and Aris line."""
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

        # Platform branding and Aris attribution
        assert await modal.locator("text=Published on Scroll Press").count() == 1
        assert await modal.locator("text=The Aris Program").count() == 1

        # The three platform links
        ctas = modal.locator(".platform-ctas")
        assert await ctas.locator('a[href="/"]').count() == 1
        assert await ctas.locator('a[href="/about"]').count() == 1
        assert await ctas.locator('a[href="/upload"]').count() == 1

        await browser.close()


async def test_details_modal_dark_mode(test_server):
    """The Details modal content displays correctly in dark mode."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await _open_details(page, test_server)

        # Enable dark mode
        await page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")

        # Wait for a modal text element to take on a non-black color (dark CSS applied)
        await page.wait_for_function(
            """() => {
                const el = document.querySelector('#info-modal .platform-link');
                if (!el) return false;
                const color = window.getComputedStyle(el).color;
                return color !== 'rgb(0, 0, 0)';
            }"""
        )

        assert await page.locator("#info-modal").is_visible()

        await browser.close()


async def test_details_modal_mobile_responsive(test_server):
    """The Details modal and its links are usable on a mobile viewport."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 375, "height": 667})

        await _open_details(page, test_server)

        modal = page.locator("#info-modal")
        assert await modal.is_visible()

        ctas = modal.locator(".platform-ctas")
        assert await ctas.locator('a[href="/"]').is_visible()
        assert await ctas.locator('a[href="/upload"]').is_visible()

        await browser.close()


async def test_details_modal_cta_links_work(test_server):
    """The platform links in the Details modal navigate correctly."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Explore More Scrolls -> /
        await _open_details(page, test_server)
        await page.locator('#info-modal .platform-ctas a[href="/"]').click()
        await page.wait_for_load_state("networkidle")
        assert page.url == f"{test_server}/"

        # Learn More -> /about
        await _open_details(page, test_server)
        await page.locator('#info-modal .platform-ctas a[href="/about"]').click()
        await page.wait_for_load_state("networkidle")
        assert "/about" in page.url

        # Publish Your Research -> /upload (may redirect to login)
        await _open_details(page, test_server)
        await page.locator('#info-modal .platform-ctas a[href="/upload"]').click()
        await page.wait_for_load_state("networkidle")
        assert "/upload" in page.url or "/login" in page.url

        await browser.close()


async def test_details_modal_aris_link_external(test_server):
    """The Aris Program link in the Details modal points to external aris.pub safely."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await _open_details(page, test_server)

        aris_link = page.locator("#info-modal a.aris-link")
        href = await aris_link.get_attribute("href")
        assert "aris.pub" in href

        target = await aris_link.get_attribute("target")
        assert target == "_blank"

        rel = await aris_link.get_attribute("rel")
        assert "noopener" in rel
        assert "noreferrer" in rel

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
