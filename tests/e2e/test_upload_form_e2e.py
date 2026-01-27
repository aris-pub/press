"""E2E tests for file upload form with CSRF and multipart handling."""

import os
import tempfile

from playwright.async_api import async_playwright, expect
import pytest

pytestmark = pytest.mark.e2e


async def test_upload_form_submission_with_file(test_server):
    """Test complete upload form submission with file upload and CSRF token.

    This is a regression test for:
    - Missing enctype="multipart/form-data" attribute
    - CSRF token not sent in X-CSRF-Token header for multipart requests
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login with pre-seeded test user
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')

            # Wait for login to complete (redirects to dashboard)
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            # Go to upload page
            await page.goto(f"{test_server}/upload")
            await expect(page.locator("h1")).to_contain_text("Upload New Scroll")

            # Fill in form fields
            await page.fill('input[name="title"]', "E2E Upload Test")
            await page.fill('input[name="authors"]', "Test Author")
            await page.select_option('select[name="subject_id"]', label="Computer Science")
            await page.fill('textarea[name="abstract"]', "This is a test abstract for E2E testing")
            await page.fill('input[name="keywords"]', "e2e, test, upload")

            # Create a temporary HTML file
            valid_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>E2E Test Document</title>
    <style>body { margin: 2rem; font-family: Arial; }</style>
</head>
<body>
    <h1>E2E Test Content</h1>
    <p>This is valid HTML content for E2E testing.</p>
</body>
</html>"""

            # Write to temp file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(valid_html)
                temp_file_path = f.name

            try:
                # Upload the file
                await page.set_input_files('input[type="file"]', temp_file_path)

                # Wait for file info to appear
                await expect(page.locator("#file-name")).to_contain_text(".html")

                # Select license
                await page.check('input[value="cc-by-4.0"]')

                # Confirm rights
                await page.check('input[name="confirm_rights"]')

                # Submit form (use specific selector to avoid logout button)
                await page.click('form button[name="action"][value="publish"]')

                # Wait for preview mode to appear (indicates successful upload)
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)

                # Verify the content is displayed in iframe
                iframe = page.frame_locator("#paper-frame")
                await expect(iframe.locator("body")).to_contain_text(
                    "E2E Test Content", timeout=5000
                )

            finally:
                # Clean up temp file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        finally:
            await browser.close()


async def test_upload_form_validation_without_file(test_server):
    """Test upload form shows validation error when no file is selected."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login with pre-seeded test user
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            # Go to upload page
            await page.goto(f"{test_server}/upload")

            # Fill in form fields but don't upload file
            await page.fill('input[name="title"]', "No File Test")
            await page.fill('input[name="authors"]', "Test Author")
            await page.select_option('select[name="subject_id"]', label="Computer Science")
            await page.fill('textarea[name="abstract"]', "Testing validation without file")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            # Try to submit without file (use specific selector to avoid logout button)
            # Note: Client-side validation will prevent form submission
            await page.click('form button[name="action"][value="publish"]')

            # Validation should prevent submission - we should stay on upload page
            await page.wait_for_timeout(1000)
            # Verify we're still on the upload page (not redirected to preview)
            assert "/upload" in page.url
            await expect(page.locator("h1")).to_contain_text("Upload New Scroll")

        finally:
            await browser.close()


async def test_upload_form_file_size_validation(test_server):
    """Test upload form rejects files larger than 50MB."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login with pre-seeded test user
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            # Go to upload page
            await page.goto(f"{test_server}/upload")

            # Create a large HTML file (51MB - over the limit)
            large_html = (
                "<!DOCTYPE html><html><body>" + ("x" * (51 * 1024 * 1024)) + "</body></html>"
            )

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(large_html)
                temp_file_path = f.name

            try:
                # Try to upload the large file
                await page.set_input_files('input[type="file"]', temp_file_path)

                # Should show size validation error
                await expect(page.locator("#file-error")).to_be_visible(timeout=2000)
                await expect(page.locator("#file-error")).to_contain_text("50MB")

            finally:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        finally:
            await browser.close()
