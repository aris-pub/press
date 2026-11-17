"""TEMPORARY: runs the old and fixed mobile menu checks 20 times each. Delete before merge."""

from playwright.async_api import async_playwright, expect
import pytest

from tests.e2e.conftest import launch_browser
from tests.e2e.test_auth_flows_mobile import MOBILE_VIEWPORT

pytestmark = [pytest.mark.e2e, pytest.mark.mobile]


async def _open_menu_and_click_about(p, test_server):
    browser = await launch_browser(p)
    context = await browser.new_context(has_touch=True, viewport=MOBILE_VIEWPORT)
    page = await context.new_page()
    await page.goto(f"{test_server}/")
    await page.locator(".mobile-menu-toggle").click()
    await page.wait_for_selector(
        '.mobile-nav.open .mobile-nav-links a[href="/#browse"]', state="visible", timeout=5000
    )
    await page.locator('.mobile-nav.open a[href="/about"]').click()
    return browser, page


@pytest.mark.parametrize("attempt", range(20))
async def test_old_networkidle(test_server, attempt):
    async with async_playwright() as p:
        browser, page = await _open_menu_and_click_about(p, test_server)
        try:
            await page.wait_for_load_state("networkidle")
            assert "/about" in page.url
        finally:
            await browser.close()


@pytest.mark.parametrize("attempt", range(20))
async def test_new_to_have_url(test_server, attempt):
    async with async_playwright() as p:
        browser, page = await _open_menu_and_click_about(p, test_server)
        try:
            await expect(page).to_have_url(f"{test_server}/about")
        finally:
            await browser.close()
