"""E2E tests for infinite draft persistence."""

import tempfile
import time

from playwright.async_api import async_playwright, expect
import pytest

pytestmark = pytest.mark.e2e


async def test_drafts_persist_indefinitely(test_server):
    """Test that drafts persist without time-based deletion."""
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

            # Create a draft
            await page.goto(f"{test_server}/upload")
            await page.fill('input[name="title"]', "Persistent Draft")
            await page.fill('input[name="authors"]', "Test Author")
            await page.select_option('select[name="subject_id"]', label="Computer Science")
            await page.fill('textarea[name="abstract"]', "This draft should persist indefinitely")
            await page.fill('input[name="keywords"]', "persistence")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            html_content = """<!DOCTYPE html>
<html>
<head><title>Persistent Draft</title></head>
<body><h1>Test Content</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)
                await page.click('form button[name="action"][value="publish"]')
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
            finally:
                import os

                os.unlink(temp_file)

            # Wait 2 seconds to simulate time passing (in real scenario this would be hours)
            time.sleep(2)

            # Go to dashboard - draft should still exist
            await page.goto(f"{test_server}/dashboard")
            await expect(page.locator(".drafts-section")).to_be_visible(timeout=5000)
            await expect(page.get_by_role("heading", name="Persistent Draft")).to_be_visible()

        finally:
            await browser.close()


async def test_drafts_show_in_dashboard(test_server):
    """Test that drafts appear in My Drafts section of dashboard."""
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

            # Create a draft
            await page.goto(f"{test_server}/upload")
            await page.fill('input[name="title"]', "Dashboard Draft")
            await page.fill('input[name="authors"]', "Dashboard Author")
            await page.select_option('select[name="subject_id"]', label="Mathematics")
            await page.fill('textarea[name="abstract"]', "Testing dashboard display")
            await page.fill('input[name="keywords"]', "dashboard")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            html_content = """<!DOCTYPE html>
<html>
<head><title>Dashboard Draft</title></head>
<body><h1>Dashboard Test</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)
                await page.click('form button[name="action"][value="publish"]')
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
            finally:
                import os

                os.unlink(temp_file)

            # Go to dashboard
            await page.goto(f"{test_server}/dashboard")

            # Verify My Drafts section exists
            await expect(page.locator(".drafts-section")).to_be_visible(timeout=5000)
            await expect(page.locator(".drafts-section h2")).to_contain_text("My Drafts")

            # Verify draft card is displayed for "Dashboard Draft"
            draft_card = page.locator(".draft-card").filter(has_text="Dashboard Draft")
            await expect(draft_card).to_be_visible()
            await expect(draft_card.locator(".draft-title")).to_contain_text("Dashboard Draft")
            await expect(draft_card.locator(".draft-authors")).to_contain_text("Dashboard Author")
            await expect(draft_card.locator(".draft-authors")).to_contain_text("Mathematics")

            # Verify action buttons for this specific draft
            await expect(draft_card.locator('button:has-text("Continue Editing")')).to_be_visible()
            await expect(draft_card.locator('a:has-text("View Preview")')).to_be_visible()
            await expect(draft_card.locator('button:has-text("Delete")')).to_be_visible()

        finally:
            await browser.close()


async def test_continue_editing_from_dashboard(test_server):
    """Test that Continue Editing button from dashboard loads the form."""
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

            # Create a draft
            await page.goto(f"{test_server}/upload")
            await page.fill('input[name="title"]', "Continue Draft")
            await page.fill('input[name="authors"]', "Continue Author")
            await page.select_option('select[name="subject_id"]', label="Physics")
            await page.fill('textarea[name="abstract"]', "Testing continue button")
            await page.fill('input[name="keywords"]', "continue")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            html_content = """<!DOCTYPE html>
<html>
<head><title>Continue Draft</title></head>
<body><h1>Continue Test</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)
                await page.click('form button[name="action"][value="publish"]')
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
            finally:
                import os

                os.unlink(temp_file)

            # Go to dashboard and click Continue Editing
            await page.goto(f"{test_server}/dashboard")
            await expect(page.locator(".drafts-section")).to_be_visible(timeout=5000)
            await page.click('button:has-text("Continue Editing")')

            # Should be on upload page with form pre-filled
            await page.wait_for_url(f"{test_server}/upload", timeout=5000)
            title_value = await page.input_value('input[name="title"]')
            assert title_value == "Continue Draft"
            authors_value = await page.input_value('input[name="authors"]')
            assert authors_value == "Continue Author"

        finally:
            await browser.close()


async def test_delete_draft_from_dashboard(test_server):
    """Test that Delete button removes draft from dashboard."""
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

            # Create a draft
            await page.goto(f"{test_server}/upload")
            await page.fill('input[name="title"]', "Draft to Delete")
            await page.fill('input[name="authors"]', "Delete Author")
            await page.select_option('select[name="subject_id"]', label="Biology")
            await page.fill('textarea[name="abstract"]', "Testing delete button")
            await page.fill('input[name="keywords"]', "delete")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            html_content = """<!DOCTYPE html>
<html>
<head><title>Delete Draft</title></head>
<body><h1>Delete Test</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)
                await page.click('form button[name="action"][value="publish"]')
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
            finally:
                import os

                os.unlink(temp_file)

            # Go to dashboard
            await page.goto(f"{test_server}/dashboard")
            await expect(page.locator(".drafts-section")).to_be_visible(timeout=5000)
            await expect(page.get_by_role("heading", name="Draft to Delete")).to_be_visible()

            # Click Delete button with dialog handler
            page.on("dialog", lambda dialog: dialog.accept())
            await page.click('button:has-text("Delete")')

            # Wait for redirect to upload page
            await page.wait_for_url(f"{test_server}/upload", timeout=5000)

            # Go back to dashboard and verify this specific draft is gone
            await page.goto(f"{test_server}/dashboard")
            # The "Draft to Delete" heading should not be visible (other drafts may still exist)
            await expect(page.get_by_role("heading", name="Draft to Delete")).not_to_be_visible()

        finally:
            await browser.close()


async def test_banner_appears_on_upload_with_drafts(test_server):
    """Test that banner appears on upload page when drafts exist."""
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

            # Create a draft
            await page.goto(f"{test_server}/upload")
            await page.fill('input[name="title"]', "Banner Test Draft")
            await page.fill('input[name="authors"]', "Banner Author")
            await page.select_option('select[name="subject_id"]', label="Chemistry")
            await page.fill('textarea[name="abstract"]', "Testing banner display")
            await page.fill('input[name="keywords"]', "banner")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            html_content = """<!DOCTYPE html>
<html>
<head><title>Banner Test</title></head>
<body><h1>Banner Test</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)
                await page.click('form button[name="action"][value="publish"]')
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
            finally:
                import os

                os.unlink(temp_file)

            # Visit upload page (without clicking Edit Details)
            await page.goto(f"{test_server}/upload")

            # Banner should be visible
            banner = page.locator(".drafts-banner")
            await expect(banner).to_be_visible(timeout=5000)
            await expect(banner).to_contain_text("draft")  # Matches "1 draft" or "X drafts"
            await expect(banner.locator('button:has-text("Continue")')).to_be_visible()
            await expect(banner.locator('button:has-text("Start Fresh")')).to_be_visible()

            # Form should NOT be pre-filled (only banner should appear)
            title_value = await page.input_value('input[name="title"]')
            assert title_value == "", "Form should not be pre-filled without explicit action"

        finally:
            await browser.close()


async def test_continue_button_loads_draft(test_server):
    """Test that Continue button from banner loads the draft."""
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

            # Create a draft
            await page.goto(f"{test_server}/upload")
            await page.fill('input[name="title"]', "Banner Continue Draft")
            await page.fill('input[name="authors"]', "Banner Continue Author")
            await page.select_option('select[name="subject_id"]', label="Economics")
            await page.fill('textarea[name="abstract"]', "Testing banner continue")
            await page.fill('input[name="keywords"]', "banner,continue")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            html_content = """<!DOCTYPE html>
<html>
<head><title>Banner Continue</title></head>
<body><h1>Banner Continue Test</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)
                await page.click('form button[name="action"][value="publish"]')
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
            finally:
                import os

                os.unlink(temp_file)

            # Visit upload page and click Continue from banner
            await page.goto(f"{test_server}/upload")
            await expect(page.locator(".drafts-banner")).to_be_visible(timeout=5000)
            await page.click('.drafts-banner button:has-text("Continue")')

            # Should reload page with form pre-filled
            await page.wait_for_url(f"{test_server}/upload", timeout=5000)
            title_value = await page.input_value('input[name="title"]')
            assert title_value == "Banner Continue Draft"
            authors_value = await page.input_value('input[name="authors"]')
            assert authors_value == "Banner Continue Author"

            # Banner should NOT be visible when editing
            await expect(page.locator(".drafts-banner")).not_to_be_visible()

        finally:
            await browser.close()


async def test_start_fresh_shows_empty_form(test_server):
    """Test that Start Fresh button shows empty form."""
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

            # Create a draft
            await page.goto(f"{test_server}/upload")
            await page.fill('input[name="title"]', "Start Fresh Draft")
            await page.fill('input[name="authors"]', "Fresh Author")
            await page.select_option('select[name="subject_id"]', label="Biology")
            await page.fill('textarea[name="abstract"]', "Testing start fresh")
            await page.fill('input[name="keywords"]', "fresh")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            html_content = """<!DOCTYPE html>
<html>
<head><title>Start Fresh</title></head>
<body><h1>Start Fresh Test</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)
                await page.click('form button[name="action"][value="publish"]')
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
            finally:
                import os

                os.unlink(temp_file)

            # Visit upload page and click Start Fresh from banner
            await page.goto(f"{test_server}/upload")
            await expect(page.locator(".drafts-banner")).to_be_visible(timeout=5000)
            await page.click('.drafts-banner button:has-text("Start Fresh")')

            # Should reload page with empty form
            await page.wait_for_url(f"{test_server}/upload", timeout=5000)
            title_value = await page.input_value('input[name="title"]')
            assert title_value == "", "Form should be empty after Start Fresh"

            # Banner should be DISMISSED (not visible) after Start Fresh
            await expect(page.locator(".drafts-banner")).not_to_be_visible()

            # Draft should still exist in dashboard
            await page.goto(f"{test_server}/dashboard")
            await expect(page.get_by_role("heading", name="Start Fresh Draft")).to_be_visible()

        finally:
            await browser.close()


async def test_start_fresh_dismisses_banner_for_session(test_server):
    """Test that Start Fresh dismisses banner for the current session."""
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

            # Create a draft
            await page.goto(f"{test_server}/upload")
            await page.fill('input[name="title"]', "Session Test Draft")
            await page.fill('input[name="authors"]', "Session Author")
            await page.select_option('select[name="subject_id"]', label="Physics")
            await page.fill('textarea[name="abstract"]', "Testing session dismissal")
            await page.fill('input[name="keywords"]', "session")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            html_content = """<!DOCTYPE html>
<html>
<head><title>Session Test</title></head>
<body><h1>Session Test</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)
                await page.click('form button[name="action"][value="publish"]')
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
            finally:
                import os

                os.unlink(temp_file)

            # Visit upload page and verify banner appears
            await page.goto(f"{test_server}/upload")
            await expect(page.locator(".drafts-banner")).to_be_visible(timeout=5000)

            # Click Start Fresh
            await page.click('.drafts-banner button:has-text("Start Fresh")')
            await page.wait_for_url(f"{test_server}/upload", timeout=5000)

            # Banner should be dismissed
            await expect(page.locator(".drafts-banner")).not_to_be_visible()

            # Navigate to dashboard and back - banner should STILL be dismissed (same session)
            await page.goto(f"{test_server}/dashboard")
            await page.goto(f"{test_server}/upload")

            # Banner should STILL not appear (dismissed for this session)
            await expect(page.locator(".drafts-banner")).not_to_be_visible()

        finally:
            await browser.close()


async def test_banner_reappears_on_new_session(test_server):
    """Test that banner reappears after logout/login (new session)."""
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

            # Create a draft
            await page.goto(f"{test_server}/upload")
            await page.fill('input[name="title"]', "New Session Test")
            await page.fill('input[name="authors"]', "New Session Author")
            await page.select_option('select[name="subject_id"]', label="Chemistry")
            await page.fill('textarea[name="abstract"]', "Testing new session")
            await page.fill('input[name="keywords"]', "newsession")
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')

            html_content = """<!DOCTYPE html>
<html>
<head><title>New Session Test</title></head>
<body><h1>New Session Test</h1></body>
</html>"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(html_content)
                temp_file = f.name

            try:
                await page.set_input_files('input[type="file"]', temp_file)
                await page.click('form button[name="action"][value="publish"]')
                await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)
            finally:
                import os

                os.unlink(temp_file)

            # Visit upload and dismiss banner
            await page.goto(f"{test_server}/upload")
            await expect(page.locator(".drafts-banner")).to_be_visible(timeout=5000)
            await page.click('.drafts-banner button:has-text("Start Fresh")')
            await page.wait_for_url(f"{test_server}/upload", timeout=5000)
            await expect(page.locator(".drafts-banner")).not_to_be_visible()

            # Logout - clear cookies to simulate new session
            await page.context.clear_cookies()

            # Login again (new session)
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')
            await expect(page.locator(".success-message")).to_be_visible(timeout=5000)

            # Visit upload - banner should REAPPEAR (new session, dismissed flag cleared)
            await page.goto(f"{test_server}/upload")
            await expect(page.locator(".drafts-banner")).to_be_visible(timeout=5000)
            await expect(page.locator(".drafts-banner")).to_contain_text("draft")

        finally:
            await browser.close()
