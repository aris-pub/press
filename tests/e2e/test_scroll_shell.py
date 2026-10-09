"""E2E test for the scroll app shell (Option C).

The behavioral guard for the layout: the outer page must stay locked (one scrollbar)
and a position:fixed element inside the paper iframe must stay pinned to the viewport
while the paper scrolls. The server-side contract is checked in
tests/test_previews.py::test_scroll_view_iframe_pins_fixed_elements; this verifies the
real rendered behavior.
"""

from playwright.async_api import async_playwright
import pytest

pytestmark = pytest.mark.e2e


async def test_app_shell_locks_outer_page_and_pins_fixed(test_server):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1200, "height": 800})

        # Open the first scroll from the homepage
        await page.goto(f"{test_server}/")
        await page.wait_for_load_state("networkidle")
        await page.locator("a.scroll-card-link").first.click()
        await page.wait_for_load_state("networkidle")
        await page.locator("#paper-frame").wait_for()

        # Wait until the same-origin paper document is ready
        await page.wait_for_function(
            """() => {
                const ifr = document.getElementById('paper-frame');
                return ifr && ifr.contentDocument && ifr.contentDocument.body;
            }"""
        )

        # Inject a tall spacer and a position:fixed probe into the paper
        await page.evaluate(
            """() => {
                const doc = document.getElementById('paper-frame').contentDocument;
                const spacer = doc.createElement('div');
                spacer.style.height = '3000px';
                doc.body.appendChild(spacer);
                const pin = doc.createElement('div');
                pin.id = 'pinned-probe';
                pin.textContent = 'PINNED';
                pin.style.position = 'fixed';
                pin.style.bottom = '0';
                pin.style.left = '0';
                doc.body.appendChild(pin);
            }"""
        )

        def _state():
            return """() => {
                const ifr = document.getElementById('paper-frame');
                const doc = ifr.contentDocument, win = ifr.contentWindow;
                const r = doc.getElementById('pinned-probe').getBoundingClientRect();
                const outer = document.scrollingElement || document.documentElement;
                return { pinTop: r.top, iframeScroll: win.scrollY, outerScroll: outer.scrollTop };
            }"""

        before = await page.evaluate(_state())

        # Scroll the paper iframe down
        await page.evaluate(
            "() => document.getElementById('paper-frame').contentWindow.scrollTo(0, 1500)"
        )
        await page.wait_for_timeout(200)

        after = await page.evaluate(_state())

        # The iframe actually scrolled
        assert after["iframeScroll"] > before["iframeScroll"] + 100, (
            f"iframe did not scroll: {before['iframeScroll']} -> {after['iframeScroll']}"
        )
        # The fixed probe stayed put relative to the viewport (pinned)
        assert abs(after["pinTop"] - before["pinTop"]) < 2, (
            f"fixed element moved: {before['pinTop']} -> {after['pinTop']}"
        )
        # The outer page never scrolled (one scrollbar, the iframe's)
        assert after["outerScroll"] == 0, (
            f"outer page scrolled to {after['outerScroll']}, should stay locked at 0"
        )

        await browser.close()
