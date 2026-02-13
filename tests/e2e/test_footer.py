"""E2E tests for footer refresh implementation."""

from playwright.async_api import async_playwright
import pytest

pytestmark = pytest.mark.e2e


async def test_footer_structure_light_mode(test_server):
    """Test footer has correct structure with two distinct sections in light mode."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate to a scroll page
        await page.goto(f"{test_server}/")
        await page.wait_for_load_state("networkidle")

        # Click on the first scroll to view it
        first_scroll_link = page.locator('a[href^="/scroll/"]').first
        await first_scroll_link.click()
        await page.wait_for_load_state("networkidle")

        # Check for article metadata section
        article_metadata = page.locator(".scroll-metadata")
        await article_metadata.wait_for()

        # Verify article metadata elements
        assert await article_metadata.locator(".metadata-title").count() == 1
        assert await article_metadata.locator(".metadata-authors").count() == 1
        assert await article_metadata.locator(".metadata-info").count() == 1

        # Verify license info is present
        metadata_info = article_metadata.locator(".metadata-info")
        info_text = await metadata_info.text_content()
        assert "Open Access" in info_text or "All Rights Reserved" in info_text
        assert "CC BY 4.0" in info_text or "All Rights Reserved" in info_text

        # Check for platform attribution section
        platform_attribution = page.locator(".scroll-platform")
        await platform_attribution.wait_for()

        # Verify platform branding
        assert await platform_attribution.locator("text=Published on Scroll Press").count() == 1
        assert await platform_attribution.locator("text=Part of The Aris Program").count() == 1

        # Verify CTAs are present
        cta_container = platform_attribution.locator(".platform-ctas")
        browse_link = cta_container.locator('a[href="/"]')
        upload_link = cta_container.locator('a[href="/upload"]')
        about_link = cta_container.locator('a[href="/about"]')

        assert await browse_link.count() == 1
        assert await upload_link.count() == 1
        assert await about_link.count() == 1

        await browser.close()


async def test_footer_dark_mode(test_server):
    """Test footer displays correctly in dark mode."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate to scroll page
        await page.goto(f"{test_server}/")
        await page.wait_for_load_state("networkidle")

        first_scroll_link = page.locator('a[href^="/scroll/"]').first
        await first_scroll_link.click()
        await page.wait_for_load_state("networkidle")

        # Check that footer sections are still visible
        article_metadata = page.locator(".scroll-metadata")
        platform_attribution = page.locator(".scroll-platform")

        await article_metadata.scroll_into_view_if_needed()

        assert await article_metadata.is_visible()
        assert await platform_attribution.is_visible()

        # Get the metadata title element
        metadata_title = article_metadata.locator(".metadata-title")

        # Enable dark mode by setting data-theme attribute
        await page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")

        # Wait for the color to change from black (indicating dark mode CSS was applied)
        await page.wait_for_function(
            """() => {
                const el = document.querySelector('.metadata-title');
                if (!el) return false;
                const color = window.getComputedStyle(el).color;
                return color !== 'rgb(0, 0, 0)';
            }"""
        )

        # Verify the color is not black
        title_color = await metadata_title.evaluate("el => window.getComputedStyle(el).color")
        assert title_color != "rgb(0, 0, 0)", (
            f"Expected non-black color in dark mode, got {title_color}"
        )

        await browser.close()


async def test_footer_mobile_responsive(test_server):
    """Test footer is responsive on mobile viewport."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Set mobile viewport
        page = await browser.new_page(viewport={"width": 375, "height": 667})

        # Navigate to scroll page
        await page.goto(f"{test_server}/")
        await page.wait_for_load_state("networkidle")

        first_scroll_link = page.locator('a[href^="/scroll/"]').first
        await first_scroll_link.click()
        await page.wait_for_load_state("networkidle")

        # Scroll to footer sections
        article_metadata = page.locator(".scroll-metadata")
        platform_attribution = page.locator(".scroll-platform")

        await article_metadata.scroll_into_view_if_needed()

        # Check footer sections are visible on mobile
        assert await article_metadata.is_visible()
        assert await platform_attribution.is_visible()

        # Check CTAs are stacked vertically on mobile
        cta_container = platform_attribution.locator(".platform-ctas")

        # Get all CTA links
        browse_link = cta_container.locator('a[href="/"]')
        upload_link = cta_container.locator('a[href="/upload"]')

        # Verify they're visible and clickable
        assert await browse_link.is_visible()
        assert await upload_link.is_visible()

        await browser.close()


async def test_footer_cta_links_work(test_server):
    """Test that footer CTA links navigate correctly."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate to scroll page
        await page.goto(f"{test_server}/")
        await page.wait_for_load_state("networkidle")

        first_scroll_link = page.locator('a[href^="/scroll/"]').first
        await first_scroll_link.click()
        await page.wait_for_load_state("networkidle")

        # Test Explore More Scrolls CTA
        browse_link = page.locator('.platform-ctas a[href="/"]')
        await browse_link.click()
        await page.wait_for_load_state("networkidle")
        assert page.url == f"{test_server}/"

        # Navigate back to scroll
        await page.go_back()
        await page.wait_for_load_state("networkidle")

        # Test Learn More CTA
        about_link = page.locator('.platform-ctas a[href="/about"]')
        await about_link.click()
        await page.wait_for_load_state("networkidle")
        assert "/about" in page.url

        # Navigate back
        await page.go_back()
        await page.wait_for_load_state("networkidle")

        # Test Publish Your Research CTA
        upload_link = page.locator('.platform-ctas a[href="/upload"]')
        await upload_link.click()
        await page.wait_for_load_state("networkidle")
        assert "/upload" in page.url or "/login" in page.url  # May redirect to login

        await browser.close()


async def test_footer_aris_link_external(test_server):
    """Test that Aris Program link points to external aris.pub."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate to scroll page
        await page.goto(f"{test_server}/")
        await page.wait_for_load_state("networkidle")

        first_scroll_link = page.locator('a[href^="/scroll/"]').first
        await first_scroll_link.click()
        await page.wait_for_load_state("networkidle")

        # Check Aris Program link
        aris_link = page.locator('.scroll-platform a:has-text("The Aris Program")')
        href = await aris_link.get_attribute("href")

        assert "aris.pub" in href

        # Verify it opens in new tab (has target="_blank")
        target = await aris_link.get_attribute("target")
        assert target == "_blank"

        # Verify security attributes
        rel = await aris_link.get_attribute("rel")
        assert "noopener" in rel
        assert "noreferrer" in rel

        await browser.close()


async def test_footer_license_display_cc_by(test_server):
    """Test footer displays CC BY 4.0 license correctly."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate to a scroll with CC BY license
        await page.goto(f"{test_server}/")
        await page.wait_for_load_state("networkidle")

        # Find a scroll (seed data should have CC BY scrolls)
        first_scroll_link = page.locator('a[href^="/scroll/"]').first
        await first_scroll_link.click()
        await page.wait_for_load_state("networkidle")

        # Check for license info in metadata section
        metadata_info = page.locator(".scroll-metadata .metadata-info")
        info_text = await metadata_info.text_content()

        # Should contain either CC BY 4.0 or All Rights Reserved
        assert "CC BY 4.0" in info_text or "All Rights Reserved" in info_text

        # If CC BY, check for link to Creative Commons
        if "CC BY 4.0" in info_text:
            cc_link = page.locator('.scroll-metadata a[href*="creativecommons.org"]')
            assert await cc_link.count() >= 1

        await browser.close()
