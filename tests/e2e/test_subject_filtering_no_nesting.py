"""E2E regression test: Subject filtering must not cause page nesting.

This test prevents the nightmare scenario where clicking a subject button
causes the entire page to nest inside itself.
"""

from playwright.async_api import async_playwright
import pytest

pytestmark = pytest.mark.e2e


async def test_subject_filtering_does_not_duplicate_page(test_server):
    """CRITICAL: Subject filtering must not duplicate navbar/page content.

    This regression test ensures that clicking a subject button:
    1. Makes an XHR request (not full page load)
    2. Returns partial HTML (not full page)
    3. Does not duplicate navbar, hero, or other page elements
    4. Only updates the scrolls section

    If this fails, check:
    - EmailVerificationMiddleware ALLOWED_PATHS includes /partials
    - /partials/scrolls returns 200, not 302 redirect
    - Partial template doesn't extend base.html
    - HTMX swap configuration is correct
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Track network requests
        requests = []
        responses = {}

        def log_request(req):
            requests.append(req.url)

        async def log_response(resp):
            if "/partials/scrolls" in resp.url:
                text = await resp.text()
                responses[resp.url] = {
                    "status": resp.status,
                    "text": text,
                    "length": len(text),
                }

        page.on("request", log_request)
        page.on("response", log_response)

        # Navigate to homepage
        await page.goto(f"{test_server}/")
        await page.wait_for_load_state("networkidle")

        # Count elements BEFORE clicking
        navbars_before = await page.locator("header.navbar").count()
        heroes_before = await page.locator(".hero").count()
        body_length_before = len(await page.content())

        assert navbars_before == 1, f"Should have 1 navbar initially, found {navbars_before}"
        assert heroes_before == 1, f"Should have 1 hero initially, found {heroes_before}"

        # Clear tracking
        requests.clear()
        responses.clear()

        # Click first subject button
        await page.locator("button.subject-card").first.click()
        await page.wait_for_timeout(2000)

        # CRITICAL CHECKS

        # 1. Must make XHR request to /partials/scrolls
        partial_requests = [url for url in requests if "/partials/scrolls" in url]
        assert len(partial_requests) > 0, (
            "REGRESSION: No request to /partials/scrolls! "
            "HTMX is not making the expected request."
        )

        # 2. Response must be 200, not redirect
        for url, resp in responses.items():
            assert resp["status"] == 200, (
                f"REGRESSION: /partials/scrolls returned {resp['status']}! "
                f"Middleware is blocking/redirecting the endpoint. "
                f"Check EmailVerificationMiddleware ALLOWED_PATHS."
            )

            # 3. Response must be partial, not full page
            assert "<!DOCTYPE" not in resp["text"], (
                "REGRESSION: Partial response contains DOCTYPE! "
                "Server is returning full page instead of partial."
            )
            assert "<html" not in resp["text"].lower(), (
                "REGRESSION: Partial response contains <html> tag! "
                "This will cause page nesting."
            )
            assert 'class="navbar"' not in resp["text"], (
                "REGRESSION: Partial response contains navbar! "
                "Full page is being returned."
            )

            # 4. Response should be small
            assert resp["length"] < 10_000, (
                f"REGRESSION: Partial response is {resp['length']} bytes! "
                f"This is too large - likely the full page (~30KB) instead of partial (~2KB)."
            )

        # 5. Count elements AFTER clicking
        navbars_after = await page.locator("header.navbar").count()
        heroes_after = await page.locator(".hero").count()
        body_length_after = len(await page.content())

        assert navbars_after == 1, (
            f"REGRESSION: Found {navbars_after} navbars after click! "
            f"The page is nesting inside itself. "
            f"This means the partial endpoint returned full page HTML."
        )
        assert heroes_after == 1, (
            f"REGRESSION: Found {heroes_after} hero sections after click! "
            f"The page is duplicating."
        )

        # Body should not double in size (would indicate full page nesting)
        growth_ratio = body_length_after / body_length_before
        assert growth_ratio < 1.5, (
            f"REGRESSION: Body HTML grew {growth_ratio:.1f}x after click! "
            f"Before: {body_length_before} bytes, After: {body_length_after} bytes. "
            f"This indicates the entire page is being inserted into the DOM."
        )

        # 6. Verify heading actually changed (filtering works)
        heading = await page.locator("#recent-submissions-heading").text_content()
        assert "Scrolls" in heading, "Heading should contain 'Scrolls'"

        await browser.close()


async def test_show_all_button_does_not_duplicate_page(test_server):
    """Ensure Show All button also doesn't cause nesting."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"{test_server}/")
        await page.wait_for_load_state("networkidle")

        # Click subject first
        await page.locator("button.subject-card").first.click()
        await page.wait_for_timeout(1000)

        # Click Show All
        await page.locator("#show-all-btn").click()
        await page.wait_for_timeout(1000)

        # Count after
        navbars_after = await page.locator("header.navbar").count()

        assert navbars_after == 1, (
            f"REGRESSION: Found {navbars_after} navbars after Show All! "
            f"Page nesting occurred."
        )

        await browser.close()
