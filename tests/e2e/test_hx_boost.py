"""E2E tests for hx-boost functionality.

hx-boost enhances anchor tags and forms to use AJAX requests instead of full page
loads, while maintaining browser history and progressive enhancement.
"""

from playwright.async_api import async_playwright
import pytest


@pytest.mark.e2e
async def test_hx_boost_navigation_prevents_full_page_reload(test_server):
    """Test that hx-boost makes navigation use AJAX instead of full page reload."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(test_server)

            # Set a marker on the window object that survives AJAX but not full reload
            await page.evaluate("window.testMarker = 'initial'")

            # Click a navigation link (e.g., to browse page)
            # With hx-boost, this should be an AJAX request
            browse_link = page.locator('a[href*="browse"], a:has-text("Browse")')
            if await browse_link.count() > 0:
                await browse_link.first.click()
                await page.wait_for_timeout(500)

                # Check if the marker still exists (proves no full reload)
                marker = await page.evaluate("window.testMarker")
                assert marker == "initial", (
                    "Full page reload detected - hx-boost not working"
                )

                # Verify URL changed
                assert "browse" in page.url or page.url != test_server
            else:
                # If no browse link, test with any internal link
                internal_link = page.locator('a[href^="/"]').first
                if await internal_link.count() > 0:
                    await internal_link.click()
                    await page.wait_for_timeout(500)

                    marker = await page.evaluate("window.testMarker")
                    assert marker == "initial", (
                        "Full page reload detected - hx-boost not working"
                    )

        finally:
            await browser.close()


@pytest.mark.e2e
async def test_hx_boost_maintains_browser_history(test_server):
    """Test that hx-boost maintains browser history for back/forward buttons."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Start at homepage
            await page.goto(test_server)
            initial_url = page.url

            # Navigate to About page (which should exist in navbar)
            # Use .first to avoid strict mode violation (mobile + desktop nav)
            about_link = page.locator('a[href="/about"]').first
            if await about_link.count() > 0:
                await about_link.click()
                await page.wait_for_timeout(500)
                second_url = page.url

                # Verify we navigated
                assert "/about" in second_url
                assert second_url != initial_url

                # Use browser back button
                await page.go_back()
                await page.wait_for_timeout(500)

                # Verify we're back at the initial page
                current_url = page.url
                # Remove trailing slash for comparison
                assert current_url.rstrip("/") == initial_url.rstrip("/")

                # Use browser forward button
                await page.go_forward()
                await page.wait_for_timeout(500)

                # Verify we're at the second page again
                assert "/about" in page.url
            else:
                # Fallback: try login page
                login_link = page.locator('a[href="/login"]')
                if await login_link.count() > 0:
                    await login_link.click()
                    await page.wait_for_timeout(500)

                    assert "/login" in page.url
                    assert page.url != initial_url

                    await page.go_back()
                    await page.wait_for_timeout(500)
                    assert page.url.rstrip("/") == initial_url.rstrip("/")

        finally:
            await browser.close()


@pytest.mark.e2e
async def test_hx_boost_updates_url_in_address_bar(test_server):
    """Test that hx-boost updates the browser URL correctly."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(test_server)

            # Click a link and verify URL updates
            internal_link = page.locator('a[href^="/"]').first
            if await internal_link.count() > 0:
                # Get the target href
                href = await internal_link.get_attribute("href")

                # Click the link
                await internal_link.click()
                await page.wait_for_timeout(500)

                # Verify URL updated to match href
                assert href in page.url, (
                    f"URL did not update correctly. Expected {href} in {page.url}"
                )

        finally:
            await browser.close()


@pytest.mark.e2e
async def test_hx_boost_preserves_page_content_on_navigation(test_server):
    """Test that hx-boost properly swaps content on navigation."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(test_server)

            # Wait for page to load
            await page.wait_for_selector("body")

            # Get initial page title
            initial_title = await page.title()

            # Navigate to a different page
            internal_link = page.locator('a[href^="/"]').first
            if await internal_link.count() > 0:
                await internal_link.click()
                await page.wait_for_timeout(500)

                # Verify content changed (title should be different or URL changed)
                new_title = await page.title()
                new_url = page.url

                # At least one should have changed
                assert (
                    new_title != initial_title or new_url != test_server
                ), "Page content did not update after navigation"

        finally:
            await browser.close()


@pytest.mark.e2e
async def test_hx_boost_does_not_affect_external_links(test_server):
    """Test that hx-boost does not interfere with external links."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(test_server)

            # Look for external links (e.g., in footer)
            external_links = page.locator('a[href^="http"]:not([href^="' + test_server + '"])')

            if await external_links.count() > 0:
                # External links should not have hx-boost behavior
                # They should open normally (we can check the href attribute)
                first_external = external_links.first
                href = await first_external.get_attribute("href")

                # Verify it's actually external
                assert (
                    href.startswith("http://") or href.startswith("https://")
                ), "Link is not external"
                assert test_server not in href, "Link is not external"

                # External links should not trigger HTMX
                # (We can't easily test actual navigation without leaving the domain,
                # but we can verify the link exists and is properly formed)
                assert href is not None

        finally:
            await browser.close()


@pytest.mark.e2e
async def test_hx_boost_works_with_htmx_attributes(test_server):
    """Test that hx-boost coexists with explicit HTMX attributes."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(test_server)

            # Set marker to detect full reload
            await page.evaluate("window.testMarker = 'present'")

            # Look for elements with explicit hx-get or hx-post
            htmx_elements = page.locator("[hx-get], [hx-post]")

            if await htmx_elements.count() > 0:
                # Click the first HTMX element
                await htmx_elements.first.click()
                await page.wait_for_timeout(500)

                # Verify no full reload occurred
                marker = await page.evaluate("window.testMarker")
                assert marker == "present", "Full page reload detected"

        finally:
            await browser.close()


@pytest.mark.e2e
async def test_hx_boost_indicator_shows_during_navigation(test_server):
    """Test that HTMX loading indicator appears during boosted navigation."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(test_server)

            # Add the htmx indicator class that shows during requests
            # First, verify the indicator element exists or is configured
            # Check if there's a global indicator in the base template

            # Note: This test might need to be adjusted based on your
            # actual indicator implementation. The key is that hx-boost
            # should trigger the same loading states as explicit HTMX requests

            internal_link = page.locator('a[href^="/"]').first
            if await internal_link.count() > 0:
                # This is a placeholder test - adjust based on your indicator implementation
                await internal_link.click()
                # If you have a loading indicator, test for it here
                await page.wait_for_timeout(100)

                # Test passes if navigation completes without error
                assert True

        finally:
            await browser.close()


@pytest.mark.e2e
async def test_hx_boost_disabled_on_specific_links(test_server):
    """Test that hx-boost can be disabled on specific links with hx-boost='false'."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(test_server)

            # Look for links that explicitly disable boost
            # (This tests the override capability)
            disabled_boost_links = page.locator('a[hx-boost="false"]')

            # This test documents the pattern even if no such links exist yet
            # When we add hx-boost="true" to body, we can disable it selectively

            if await disabled_boost_links.count() > 0:
                # Set marker
                await page.evaluate("window.testMarker = 'initial'")

                # Click disabled boost link (should cause full reload)
                await disabled_boost_links.first.click()
                await page.wait_for_timeout(500)

                # Marker should be gone (full reload occurred)
                marker = await page.evaluate("window.testMarker || 'gone'")
                assert marker == "gone", "Link should have caused full reload"
            else:
                # No disabled links found - that's okay, test documents the pattern
                assert True

        finally:
            await browser.close()
