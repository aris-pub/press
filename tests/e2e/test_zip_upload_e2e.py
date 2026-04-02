"""E2E tests for zip archive upload with entry point picker and asset serving."""

import os
import tempfile
import zipfile

from playwright.async_api import async_playwright, expect
import pytest

pytestmark = pytest.mark.e2e

VALID_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Zip Upload E2E Test</title>
    <link rel="stylesheet" href="styles/main.css">
</head>
<body>
    <h1>Research Paper: Zip Upload Test</h1>
    <p>This is a comprehensive test document designed to pass the content validator
    minimum word count requirement of one hundred words. The document contains
    structured content with headings and paragraphs as required by the validation
    pipeline. Academic research papers typically contain many more words than this
    minimum threshold but for testing purposes we need to ensure that the validator
    accepts our test content without raising errors about insufficient word count
    or missing document structure elements that are expected in scholarly work.</p>
    <p>Additional paragraph providing more content to ensure we comfortably exceed
    the minimum word count threshold required by the content quality validator.</p>
</body>
</html>"""


def _make_test_zip(files: dict[str, str]) -> str:
    """Create a zip file with given files, return the temp path."""
    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return path


async def test_zip_upload_shows_entry_point_picker(test_server):
    """Uploading a zip file should show the entry point picker before creating the scroll."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')
            await expect(page.locator(".success-message")).to_be_visible(timeout=5000)
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            # Go to upload page
            await page.goto(f"{test_server}/upload")
            await expect(page.locator("h1")).to_contain_text("Upload New Scroll")

            # Fill in form
            await page.fill('input[name="title"]', "Zip Upload E2E Test")
            await page.fill('input[name="authors"]', "E2E Author")
            await page.select_option('select[name="subject_id"]', label="Computer Science")
            await page.fill('textarea[name="abstract"]', "Test abstract for zip upload e2e test")
            await page.fill('input[name="keywords"]', "zip, e2e, test")

            # Create test zip
            zip_path = _make_test_zip(
                {
                    "index.html": VALID_HTML,
                    "styles/main.css": "h1 { color: navy; font-size: 2rem; }",
                }
            )

            try:
                await page.set_input_files('input[type="file"]', zip_path)
                await expect(page.locator("#uploaded-file-name")).to_contain_text(".zip")

                # Select license and confirm rights
                await page.check('input[value="cc-by-4.0"]')
                await page.check('input[name="confirm_rights"]')

                # Submit form
                await page.click('form button[name="action"][value="publish"]')

                # Should show entry point picker
                await expect(page.locator("body")).to_contain_text(
                    "Select Entry Point", timeout=10000
                )
                await expect(page.locator("body")).to_contain_text("index.html")

                # Confirm entry point
                await page.click('#entry-point-form button[type="submit"]')

                # Should redirect to preview
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)

            finally:
                if os.path.exists(zip_path):
                    os.unlink(zip_path)

        finally:
            await browser.close()


async def test_zip_upload_assets_load_in_iframe(test_server):
    """After zip upload, assets referenced in the HTML should load within the iframe."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')
            await expect(page.locator(".success-message")).to_be_visible(timeout=5000)
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            # Upload a zip with CSS assets
            await page.goto(f"{test_server}/upload")
            await page.fill('input[name="title"]', "Asset Loading Test")
            await page.fill('input[name="authors"]', "E2E Author")
            await page.select_option('select[name="subject_id"]', label="Computer Science")
            await page.fill('textarea[name="abstract"]', "Testing asset loading from zip archives")
            await page.fill('input[name="keywords"]', "assets, css")

            zip_path = _make_test_zip(
                {
                    "index.html": VALID_HTML,
                    "styles/main.css": "h1 { color: navy; font-size: 2rem; }",
                }
            )

            try:
                await page.set_input_files('input[type="file"]', zip_path)
                await page.check('input[value="cc-by-4.0"]')
                await page.check('input[name="confirm_rights"]')
                await page.click('form button[name="action"][value="publish"]')

                # Confirm entry point on picker page
                await expect(page.locator("body")).to_contain_text(
                    "Select Entry Point", timeout=10000
                )
                await page.click('#entry-point-form button[type="submit"]')

                # Wait for preview page
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)

                # Verify entry point HTML loaded in iframe
                iframe = page.frame_locator("#paper-frame")
                await expect(iframe.locator("h1")).to_contain_text(
                    "Research Paper: Zip Upload Test", timeout=10000
                )

                # Verify CSS loaded by checking computed style (use to_have_css
                # which polls/retries, unlike evaluate which is a one-shot check
                # that can race with stylesheet loading)
                await expect(iframe.locator("h1")).to_have_css(
                    "color", "rgb(0, 0, 128)", timeout=10000
                )

            finally:
                if os.path.exists(zip_path):
                    os.unlink(zip_path)

        finally:
            await browser.close()
