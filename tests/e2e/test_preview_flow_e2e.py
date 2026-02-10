"""E2E test for preview edit flow."""

import os
import tempfile

from playwright.async_api import async_playwright, expect
import pytest

pytestmark = pytest.mark.e2e


async def test_preview_edit_button_prefills_form(test_server):
    """Test that clicking Edit Details on preview prefills the upload form."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login with pre-seeded test user
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')

            # Wait for dashboard redirect
            await expect(page.locator(".success-message")).to_be_visible(timeout=5000)
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            # Go to upload page
            await page.goto(f"{test_server}/upload")
            await expect(page.locator("h1")).to_contain_text("Upload New Scroll")

            # Fill in form
            await page.fill('input[name="title"]', "Test Edit Flow")
            await page.fill('input[name="authors"]', "Test Author")
            await page.select_option('select[name="subject_id"]', label="Computer Science")
            await page.fill('textarea[name="abstract"]', "Testing the edit button functionality")
            await page.fill('input[name="keywords"]', "edit, test, preview")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            # Create and upload HTML file
            html_content = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Test Content</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)
                await expect(page.locator("#uploaded-file-name")).to_contain_text(".html")

                # Submit to create preview
                await page.click('form button[name="action"][value="publish"]')

                # Wait for preview page
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
                await expect(page.locator("body")).to_contain_text("Test Edit Flow")

                # Click Edit Details button
                await page.click('button:has-text("Edit Details")')

                # Should be back on upload form
                await page.wait_for_url(f"{test_server}/upload", timeout=5000)

                # Verify form is prefilled with original data
                title_value = await page.input_value('input[name="title"]')
                assert title_value == "Test Edit Flow", (
                    f"Expected 'Test Edit Flow', got '{title_value}'"
                )

                authors_value = await page.input_value('input[name="authors"]')
                assert authors_value == "Test Author", (
                    f"Expected 'Test Author', got '{authors_value}'"
                )

                abstract_value = await page.input_value('textarea[name="abstract"]')
                assert "Testing the edit button functionality" in abstract_value

                keywords_value = await page.input_value('input[name="keywords"]')
                assert keywords_value == "edit, test, preview", (
                    f"Expected 'edit, test, preview', got '{keywords_value}'"
                )

                # Verify license is still selected
                cc_by_radio = page.locator('input[value="cc-by-4.0"]')
                assert await cc_by_radio.is_checked(), "CC-BY license should still be checked"

            finally:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

        finally:
            await browser.close()


async def test_complete_edit_and_resubmit_cycle(test_server):
    """Test that editing and resubmitting creates a new preview with updated data."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login with pre-seeded test user
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')

            # Wait for dashboard redirect
            await expect(page.locator(".success-message")).to_be_visible(timeout=5000)
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            # Go to upload page
            await page.goto(f"{test_server}/upload")
            await expect(page.locator("h1")).to_contain_text("Upload New Scroll")

            # Fill in form with original data
            await page.fill('input[name="title"]', "Original Title")
            await page.fill('input[name="authors"]', "Original Author")
            await page.select_option('select[name="subject_id"]', label="Computer Science")
            await page.fill('textarea[name="abstract"]', "Original abstract content")
            await page.fill('input[name="keywords"]', "original, keywords")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            # Create and upload HTML file
            html_content = """<!DOCTYPE html>
<html>
<head><title>Original</title></head>
<body><h1>Original Content</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)
                await expect(page.locator("#uploaded-file-name")).to_contain_text(".html")

                # Submit to create preview
                await page.click('form button[name="action"][value="publish"]')

                # Wait for preview page
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
                await expect(page.locator("body")).to_contain_text("Original Title")

                # Click Edit Details button
                await page.click('button:has-text("Edit Details")')

                # Should be back on upload form
                await page.wait_for_url(f"{test_server}/upload", timeout=5000)

                # Modify form data
                await page.fill('input[name="title"]', "Updated Title")
                await page.fill('input[name="authors"]', "Updated Author")
                await page.fill('textarea[name="abstract"]', "Updated abstract content")
                await page.fill('input[name="keywords"]', "updated, keywords")

                # Re-upload file (file input is cleared after edit)
                await page.set_input_files('input[type="file"]', temp_file)
                await expect(page.locator("#uploaded-file-name")).to_contain_text(".html")

                # Re-check confirm_rights (required field, not prefilled)
                await page.check('input[name="confirm_rights"]')

                # Resubmit to create new preview
                await page.click('form button[name="action"][value="publish"]')

                # Wait for new preview page
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
                await expect(page.locator("body")).to_contain_text("Updated Title")
                await expect(page.locator("body")).to_contain_text("Updated Author")

                # Verify old data is not present
                page_content = await page.content()
                assert "Original Title" not in page_content
                assert "Original Author" not in page_content

            finally:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

        finally:
            await browser.close()


async def test_cancel_preview_flow(test_server):
    """Test that canceling a preview deletes scroll and redirects to upload."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login with pre-seeded test user
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')

            # Wait for dashboard redirect
            await expect(page.locator(".success-message")).to_be_visible(timeout=5000)
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            # Go to upload page
            await page.goto(f"{test_server}/upload")
            await expect(page.locator("h1")).to_contain_text("Upload New Scroll")

            # Fill in form
            await page.fill('input[name="title"]', "Test Cancel Flow")
            await page.fill('input[name="authors"]', "Test Author")
            await page.select_option('select[name="subject_id"]', label="Computer Science")
            await page.fill('textarea[name="abstract"]', "Testing cancel functionality")
            await page.fill('input[name="keywords"]', "cancel, test")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            # Create and upload HTML file
            html_content = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Cancel Test</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)
                await expect(page.locator("#uploaded-file-name")).to_contain_text(".html")

                # Submit to create preview
                await page.click('form button[name="action"][value="publish"]')

                # Wait for preview page
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
                await expect(page.locator("body")).to_contain_text("Test Cancel Flow")

                # Capture preview URL for later verification
                preview_url = page.url

                # Click Cancel & Discard button
                await page.click('button:has-text("Cancel & Discard")')

                # Should redirect to upload page
                await page.wait_for_url(f"{test_server}/upload", timeout=5000)
                await expect(page.locator("h1")).to_contain_text("Upload New Scroll")

                # Try to access the preview URL - should get 404
                response = await page.goto(preview_url)
                assert response.status == 404, (
                    f"Expected 404 for deleted preview, got {response.status}"
                )

            finally:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

        finally:
            await browser.close()


async def test_file_upload_keyboard_accessibility(test_server):
    """Test that file upload component is keyboard accessible."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login with pre-seeded test user
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')

            # Wait for dashboard redirect
            await expect(page.locator(".success-message")).to_be_visible(timeout=5000)
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            # Go to upload page
            await page.goto(f"{test_server}/upload")
            await expect(page.locator("h1")).to_contain_text("Upload New Scroll")

            # Verify file upload zone has correct accessibility attributes
            role = await page.locator("#file-upload-zone").get_attribute("role")
            assert role == "button", f"Expected role='button', got {role}"

            tabindex = await page.locator("#file-upload-zone").get_attribute("tabindex")
            assert tabindex == "0", f"Expected tabindex='0', got {tabindex}"

            aria_label = await page.locator("#file-upload-zone").get_attribute("aria-label")
            assert aria_label is not None, "Expected aria-label to be present"

            # Focus the element programmatically and verify it can receive focus
            await page.locator("#file-upload-zone").focus()
            focused_element = await page.evaluate("document.activeElement.id")
            assert focused_element == "file-upload-zone", (
                f"Expected file-upload-zone to be focused, got {focused_element}"
            )

            # Verify the element is keyboard-interactive
            # (Can't test ENTER opening file dialog in headless, but we verify the attribute is set)

        finally:
            await browser.close()


async def test_edit_shows_uploaded_state_with_filename(test_server):
    """Test that editing preview shows uploaded state with existing filename."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login with pre-seeded test user
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')

            # Wait for dashboard redirect
            await expect(page.locator(".success-message")).to_be_visible(timeout=5000)
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            # Go to upload page and create preview
            await page.goto(f"{test_server}/upload")
            await page.fill('input[name="title"]', "Keyboard Test")
            await page.fill('input[name="authors"]', "Test Author")
            await page.select_option('select[name="subject_id"]', label="Computer Science")
            await page.fill('textarea[name="abstract"]', "Testing keyboard accessibility")
            await page.fill('input[name="keywords"]', "keyboard, test")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            # Upload file
            html_content = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Keyboard Test</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)

                # Verify uploaded state is shown
                await expect(page.locator("#file-uploaded-state")).to_be_visible()
                await expect(page.locator("#uploaded-file-name")).to_contain_text(".html")

                # Submit to create preview
                await page.click('form button[name="action"][value="publish"]')

                # Wait for preview page
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)

                # Click Edit Details
                await page.click('button:has-text("Edit Details")')

                # Should be back on upload form
                await page.wait_for_url(f"{test_server}/upload", timeout=5000)

                # Verify uploaded state is shown with filename
                await expect(page.locator("#file-uploaded-state")).to_be_visible()
                await expect(page.locator("#uploaded-file-name")).to_contain_text(".html")

                # Verify empty state is hidden
                is_upload_zone_visible = await page.locator("#file-upload-zone").is_visible()
                assert not is_upload_zone_visible, "File upload zone should be hidden when editing"

                # Verify Replace file button is visible and keyboard accessible
                await expect(page.locator("#btn-replace-file")).to_be_visible()
                tabindex = await page.locator("#btn-replace-file").get_attribute("tabindex")
                assert tabindex == "0", f"Expected replace button tabindex='0', got {tabindex}"

            finally:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

        finally:
            await browser.close()


async def test_publish_preview_flow(test_server):
    """Test that publishing a preview makes it publicly accessible."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login with pre-seeded test user
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')

            # Wait for dashboard redirect
            await expect(page.locator(".success-message")).to_be_visible(timeout=5000)
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            # Go to upload page
            await page.goto(f"{test_server}/upload")
            await expect(page.locator("h1")).to_contain_text("Upload New Scroll")

            # Fill in form
            await page.fill('input[name="title"]', "Test Publish Flow")
            await page.fill('input[name="authors"]', "Test Author")
            await page.select_option('select[name="subject_id"]', label="Computer Science")
            await page.fill('textarea[name="abstract"]', "Testing publish functionality")
            await page.fill('input[name="keywords"]', "publish, test")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            # Create and upload HTML file
            html_content = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Publish Test</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)
                await expect(page.locator("#uploaded-file-name")).to_contain_text(".html")

                # Submit to create preview
                await page.click('form button[name="action"][value="publish"]')

                # Wait for preview page
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
                await expect(page.locator("body")).to_contain_text("Test Publish Flow")

                # Click Publish/Confirm button
                await page.click('button:has-text("Publish")')

                # Should redirect to published scroll page
                await page.wait_for_url(f"{test_server}/scroll/**", timeout=5000)

                # Verify preview banner is gone
                page_content = await page.content()
                assert "PREVIEW MODE" not in page_content
                assert "Preview:" not in page_content

                # Verify scroll content is visible
                await expect(page.locator("body")).to_contain_text("Test Publish Flow")
                await expect(page.locator("body")).to_contain_text("Test Author")

                # Capture published URL
                published_url = page.url

                # Logout to test public access
                await page.goto(f"{test_server}/logout")

                # Access published scroll without authentication
                await page.goto(published_url)
                await expect(page.locator("body")).to_contain_text("Test Publish Flow")

            finally:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

        finally:
            await browser.close()
