"""Discovery and navigation e2e tests.

Tests for search functionality, subject browsing, and content discovery workflows.

Run against development server:
    just dev
    uv run pytest tests/e2e/test_discovery_flows.py -v
"""

from playwright.async_api import async_playwright, expect
import pytest

# Configuration
DEV_SERVER_URL = "http://localhost:8000"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_search_and_discovery_workflow():
    """Test search functionality and content discovery.

    Verifies:
    1. Homepage search box functionality
    2. Search results display
    3. Navigation from search to scroll view
    4. Back navigation preservation
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Step 1: Visit homepage
            await page.goto(DEV_SERVER_URL)
            await page.wait_for_load_state("networkidle")

            # Verify search box is present
            search_form = page.locator(".search-box form")
            await expect(search_form).to_be_visible()

            search_input = page.locator('input[name="q"]')
            await expect(search_input).to_be_visible()

            # Step 2: Perform search
            search_term = "test"  # Should match seeded data or uploaded content
            await search_input.fill(search_term)

            # Submit search
            search_button = page.locator('button[type="submit"]', has_text="Search")
            await search_button.click()

            await page.wait_for_load_state("networkidle")

            # Step 3: Verify search results page
            assert "/search" in page.url

            # Should see search results heading
            results_heading = page.locator('h1:has-text("Search Results")')
            await expect(results_heading).to_be_visible()

            # Should show search term
            search_term_display = page.locator(f'text="{search_term}"')
            await expect(search_term_display).to_be_visible()

            # Check if we have results (depends on seeded data)
            results_container = page.locator(".scrolls-grid, .search-results")
            await expect(results_container).to_be_visible()

            # If we have scroll cards, test clicking on one
            scroll_cards = page.locator(".scroll-card")
            card_count = await scroll_cards.count()

            if card_count > 0:
                # Step 4: Click on first result
                first_card = scroll_cards.first()
                await first_card.click()

                await page.wait_for_load_state("networkidle")

                # Should navigate to scroll view
                assert "/scroll/" in page.url

                # Should see scroll content
                scroll_content = page.locator(".scroll-content, .scroll-container")
                await expect(scroll_content).to_be_visible()

                # Step 5: Test back navigation
                await page.go_back()
                await page.wait_for_load_state("networkidle")

                # Should be back on search results
                assert "/search" in page.url
                await expect(results_heading).to_be_visible()

        finally:
            await browser.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_subject_browsing_and_filtering():
    """Test subject-based content browsing and filtering.

    Verifies:
    1. Subject cards on homepage
    2. Subject filtering functionality
    3. Filtered results display
    4. Navigation to individual scrolls
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Step 1: Visit homepage
            await page.goto(DEV_SERVER_URL)
            await page.wait_for_load_state("networkidle")

            # Step 2: Verify subjects section
            subjects_section = page.locator(".subjects")
            await expect(subjects_section).to_be_visible()

            subjects_heading = page.locator('h2:has-text("Browse by Subject")')
            await expect(subjects_heading).to_be_visible()

            # Should see subject cards
            subject_cards = page.locator(".subject-card")
            card_count = await subject_cards.count()
            assert card_count > 0, "Should have at least one subject card"

            # Step 3: Click on a subject (Computer Science if available)
            # Try to find Computer Science first, otherwise use first available
            cs_card = page.locator('.subject-card:has-text("Computer Science")')
            first_card = subject_cards.first()

            if await cs_card.count() > 0:
                target_card = cs_card
                subject_name = "Computer Science"
            else:
                target_card = first_card
                subject_name = await first_card.locator(".subject-name, h3").text_content()
                subject_name = subject_name.strip() if subject_name else "Subject"

            await target_card.click()
            await page.wait_for_load_state("networkidle")

            # Step 4: Verify filtered results page
            # Should show filtered results for the subject
            page_heading = page.locator("h1, h2")
            await expect(page_heading).to_contain_text(subject_name)

            # Should see filtered scrolls or "no results" message
            content_area = page.locator(".scrolls-grid, .content, main")
            await expect(content_area).to_be_visible()

            # Check for scroll cards or no results message
            scroll_cards = page.locator(".scroll-card")
            no_results = page.locator(':has-text("No scrolls found"), :has-text("No results")')

            # Either should have results or a no results message
            results_exist = await scroll_cards.count() > 0
            no_results_exist = await no_results.count() > 0

            assert results_exist or no_results_exist, (
                "Should show either results or no results message"
            )

            # Step 5: If we have results, test clicking on one
            if results_exist:
                first_result = scroll_cards.first()
                await first_result.click()

                await page.wait_for_load_state("networkidle")

                # Should navigate to scroll view
                assert "/scroll/" in page.url

                # Should see scroll content
                scroll_content = page.locator(".scroll-content, .scroll-container")
                await expect(scroll_content).to_be_visible()

                # Verify subject metadata is preserved
                await page.click(".fab")  # Open info modal
                await page.wait_for_selector(".modal.show", state="visible")

                # Modal should contain subject information
                modal_content = page.locator(".modal")
                await expect(modal_content).to_contain_text(subject_name)

                await page.click(".modal-close")

        finally:
            await browser.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_homepage_show_all_subjects():
    """Test 'Show All' functionality for subjects section.

    Verifies:
    1. Show All button functionality
    2. Subject visibility toggling
    3. Responsive subject grid
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Visit homepage
            await page.goto(DEV_SERVER_URL)
            await page.wait_for_load_state("networkidle")

            # Check if Show All button exists
            show_all_btn = page.locator("#show-all-btn, .show-all-btn")

            if await show_all_btn.count() > 0:
                # Get initial subject count
                subject_cards = page.locator(".subject-card")
                initial_count = await subject_cards.count()

                # Click Show All
                await show_all_btn.click()
                await page.wait_for_timeout(500)  # Wait for animation

                # Should show more subjects or change button text
                new_count = await subject_cards.count()
                button_text = await show_all_btn.text_content()

                # Either more subjects visible or button text changed
                assert new_count >= initial_count, "Should show at least same number of subjects"

                # If button text changed, it might now say "Show Less"
                if "Show Less" in button_text:
                    # Test Show Less functionality
                    await show_all_btn.click()
                    await page.wait_for_timeout(500)

                    final_count = await subject_cards.count()
                    assert final_count <= new_count, "Should show fewer subjects after Show Less"

        finally:
            await browser.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_homepage_recent_scrolls_section():
    """Test recent scrolls section on homepage.

    Verifies:
    1. Recent scrolls section display
    2. Scroll card functionality
    3. Navigation to scroll view
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Visit homepage
            await page.goto(DEV_SERVER_URL)
            await page.wait_for_load_state("networkidle")

            # Check recent scrolls section
            recent_section = page.locator(".recent, #recent")
            await expect(recent_section).to_be_visible()

            recent_heading = page.locator('h2:has-text("Recent")')
            await expect(recent_heading).to_be_visible()

            # Check for scroll cards in recent section
            recent_scrolls = recent_section.locator(".scroll-card")
            scroll_count = await recent_scrolls.count()

            if scroll_count > 0:
                # Test clicking on a recent scroll
                first_scroll = recent_scrolls.first()

                # Get scroll title for verification
                scroll_title_elem = first_scroll.locator(".scroll-title, h3")
                scroll_title = await scroll_title_elem.text_content()

                await first_scroll.click()
                await page.wait_for_load_state("networkidle")

                # Should navigate to scroll view
                assert "/scroll/" in page.url

                # Should see the scroll content
                scroll_content = page.locator(".scroll-content, .scroll-container")
                await expect(scroll_content).to_be_visible()

                # Verify it's the correct scroll by checking info modal
                await page.click(".fab")
                await page.wait_for_selector(".modal.show", state="visible")

                modal = page.locator(".modal")
                if scroll_title:
                    await expect(modal).to_contain_text(scroll_title.strip())

                await page.click(".modal-close")
            else:
                # If no recent scrolls, empty state is acceptable for fresh installations
                print("No recent scrolls found - this is expected for fresh installations")

        finally:
            await browser.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_navigation_breadcrumbs_and_links():
    """Test navigation consistency and link functionality.

    Verifies:
    1. Header navigation links
    2. Logo link functionality
    3. Footer links
    4. Consistent navigation across pages
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Start at homepage
            await page.goto(DEV_SERVER_URL)
            await page.wait_for_load_state("networkidle")

            # Test logo link (should always return to home)
            logo_link = page.locator('a:has(img[alt*="Scroll Press"]), .hero-title a')
            if await logo_link.count() > 0:
                await logo_link.click()
                await page.wait_for_load_state("networkidle")
                assert page.url in [DEV_SERVER_URL, f"{DEV_SERVER_URL}/"]

            # Test footer links if present
            footer_links = page.locator("footer a")
            footer_count = await footer_links.count()

            for i in range(min(footer_count, 3)):  # Test first 3 footer links
                link = footer_links.nth(i)
                href = await link.get_attribute("href")

                if href and not href.startswith("mailto:") and not href.startswith("http"):
                    # Internal link - test it
                    await link.click()
                    await page.wait_for_load_state("networkidle")

                    # Should navigate successfully (not 404)
                    page_content = page.locator("body")
                    await expect(page_content).not_to_contain_text("404")
                    await expect(page_content).not_to_contain_text("Not Found")

                    # Return to home for next test
                    await page.goto(DEV_SERVER_URL)
                    await page.wait_for_load_state("networkidle")

            # Test registration/login links
            auth_links = page.locator('a:has-text("Register"), a:has-text("Login")')
            auth_count = await auth_links.count()

            if auth_count > 0:
                # Test register link
                register_link = page.locator('a:has-text("Register")')
                if await register_link.count() > 0:
                    await register_link.click()
                    await page.wait_for_load_state("networkidle")

                    assert "/register" in page.url

                    # Should see registration form
                    form = page.locator("form")
                    await expect(form).to_be_visible()

                    # Return to home
                    await page.goto(DEV_SERVER_URL)
                    await page.wait_for_load_state("networkidle")

                # Test login link
                login_link = page.locator('a:has-text("Login")')
                if await login_link.count() > 0:
                    await login_link.click()
                    await page.wait_for_load_state("networkidle")

                    assert "/login" in page.url

                    # Should see login form
                    form = page.locator("form")
                    await expect(form).to_be_visible()

        finally:
            await browser.close()
