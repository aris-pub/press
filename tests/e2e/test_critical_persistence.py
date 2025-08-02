"""Critical persistence tests for Scroll Press e2e testing.

These tests verify the core functionality that scrolls remain publicly accessible
through permanent links, both with active user accounts and after account deletion.
"""

from playwright.async_api import Page, expect
import pytest

from tests.e2e.conftest import E2EHelpers


@pytest.mark.e2e
@pytest.mark.asyncio
class TestCriticalPersistence:
    """Test critical persistence scenarios for public scroll access."""

    async def test_registration_upload_public_access(
        self,
        page: Page,
        test_server: str,
        seeded_database: dict,
        sample_html_content: str,
        e2e_helpers: E2EHelpers,
    ):
        """Test: User creates new account → uploads document → permanent public link created → link works without auth.

                This test verifies the core publishing workflow:
                1. New user registration with auto-login
                2. Upload scroll with license selection
                3. Scroll receives permanent public URL
                4. Public URL works without authentication
        5. License information displays correctly
        """
        # Generate unique test data
        import uuid

        test_id = uuid.uuid4().hex[:8]
        user_email = f"testuser_{test_id}@example.com"
        user_password = "testpass123"
        user_display_name = f"Test User {test_id}"

        scroll_title = f"Test Research Paper {test_id}"
        scroll_authors = f"{user_display_name}, Co-Author Example"
        scroll_abstract = f"This is a test abstract for paper {test_id}. It contains research findings about e2e testing methodologies."

        # Step 1: Register new user (should auto-login)
        success = await e2e_helpers.register_user(
            page, test_server, user_email, user_password, user_display_name
        )
        assert success, "User registration should succeed"

        # Verify user is logged in (check for logout button or user menu)
        await expect(page.locator('text="Upload"')).to_be_visible()

        # Step 2: Upload scroll
        scroll_url = await e2e_helpers.upload_scroll(
            page=page,
            server_url=test_server,
            title=scroll_title,
            authors=scroll_authors,
            abstract=scroll_abstract,
            html_content=sample_html_content,
            subject_name="Computer Science",
            license="cc-by-4.0",
        )

        assert scroll_url is not None, "Scroll upload should return a URL"
        assert "/scroll/" in scroll_url, "Scroll URL should contain /scroll/ path"

        # Step 3: Verify scroll is accessible while logged in
        await page.goto(scroll_url)
        await page.wait_for_load_state("networkidle")

        # Verify scroll content loads
        await expect(page.locator("h1")).to_contain_text("A Novel Approach to E2E Testing")

        # Verify scroll info modal works
        await page.click(".fab")  # Click info button
        await page.wait_for_selector(".modal.show", state="visible")

        # Verify scroll metadata in modal
        await expect(page.locator(".modal")).to_contain_text(scroll_title)
        await expect(page.locator(".modal")).to_contain_text(scroll_authors)
        await expect(page.locator(".modal")).to_contain_text("CC BY 4.0")

        # Close modal
        await page.click(".modal-close")
        await page.wait_for_selector(".modal.show", state="hidden")

        # Step 4: Logout user
        await page.click('button:has-text("Logout")')
        await page.wait_for_load_state("networkidle")

        # Verify logout successful (should be on homepage without upload link)
        await expect(page.locator('text="Upload"')).not_to_be_visible()
        await expect(page.locator('text="Login"')).to_be_visible()

        # Step 5: Test public access without authentication
        # Use new browser context to ensure no session data
        new_context = await page.context.browser.new_context()
        new_page = await new_context.new_page()

        try:
            # Visit scroll URL in clean browser context
            await new_page.goto(scroll_url)
            await new_page.wait_for_load_state("networkidle")

            # Verify content loads without authentication
            await expect(new_page.locator("h1")).to_contain_text("A Novel Approach to E2E Testing")

            # Verify interactive elements work
            await expect(new_page.locator("h2")).to_contain_text("Introduction")
            await expect(new_page.locator("h2")).to_contain_text("Methodology")
            await expect(new_page.locator("h2")).to_contain_text("Results")

            # Verify modal still works without auth
            await new_page.click(".fab")
            await new_page.wait_for_selector(".modal.show", state="visible")

            # Verify license information displays correctly
            await expect(new_page.locator(".license-info")).to_contain_text("License:")
            await expect(new_page.locator(".license-link")).to_contain_text("CC BY 4.0")
            await expect(new_page.locator(".license-description")).to_contain_text("Open Access")

            # Verify CC BY link works
            cc_link = new_page.locator('.license-link[href*="creativecommons.org"]')
            await expect(cc_link).to_be_visible()

            # Close modal
            await new_page.click(".modal-close")

            # Verify scroll metadata
            await expect(new_page.locator(".attribution-title")).to_contain_text(scroll_title[:60])
            await expect(new_page.locator(".attribution-meta")).to_contain_text(scroll_authors)
            await expect(new_page.locator(".attribution-meta")).to_contain_text("Computer Science")

        finally:
            await new_context.close()

    async def test_registration_upload_account_deletion_public_access(
        self,
        page: Page,
        test_server: str,
        seeded_database: dict,
        sample_html_content: str,
        e2e_helpers: E2EHelpers,
    ):
        """Test: User creates account → uploads document → deletes account → link works without auth.

        This test verifies scroll persistence after account deletion:
        1. New user registration with auto-login
        2. Upload scroll with license selection
        3. Delete user account
        4. Verify scroll URL still works without authentication
        5. Verify license and metadata still display correctly
        """
        # Generate unique test data
        import uuid

        test_id = uuid.uuid4().hex[:8]
        user_email = f"deluser_{test_id}@example.com"
        user_password = "testpass123"
        user_display_name = f"Delete User {test_id}"

        scroll_title = f"Research Before Deletion {test_id}"
        scroll_authors = f"{user_display_name}, Persistent Co-Author"
        scroll_abstract = (
            f"This paper {test_id} tests scroll persistence after user account deletion."
        )

        # Step 1: Register new user
        success = await e2e_helpers.register_user(
            page, test_server, user_email, user_password, user_display_name
        )
        assert success, "User registration should succeed"

        # Step 2: Upload scroll with All Rights Reserved license
        scroll_url = await e2e_helpers.upload_scroll(
            page=page,
            server_url=test_server,
            title=scroll_title,
            authors=scroll_authors,
            abstract=scroll_abstract,
            html_content=sample_html_content,
            subject_name="Biology",
            license="arr",  # Test All Rights Reserved license
        )

        assert scroll_url is not None, "Scroll upload should return a URL"

        # Step 3: Verify scroll works before deletion
        await page.goto(scroll_url)
        await page.wait_for_load_state("networkidle")
        await expect(page.locator("h1")).to_contain_text("A Novel Approach to E2E Testing")

        # Verify All Rights Reserved license displays
        await page.click(".fab")
        await page.wait_for_selector(".modal.show", state="visible")
        await expect(page.locator(".license-text")).to_contain_text("All Rights Reserved")
        await expect(page.locator(".license-description")).to_contain_text("Standard copyright")
        await page.click(".modal-close")

        # Step 4: Delete user account
        account_deleted = await e2e_helpers.delete_user_account(page, test_server)
        assert account_deleted, "Account deletion should succeed"

        # Verify redirect to homepage with success message
        await expect(page.locator("body")).to_contain_text("account_deleted")

        # Step 5: Test scroll persistence after account deletion
        # Use new browser context to ensure clean state
        new_context = await page.context.browser.new_context()
        new_page = await new_context.new_page()

        try:
            # Visit scroll URL after account deletion
            await new_page.goto(scroll_url)
            await new_page.wait_for_load_state("networkidle")

            # Verify scroll content still loads
            await expect(new_page.locator("h1")).to_contain_text("A Novel Approach to E2E Testing")

            # Verify scroll structure is intact
            await expect(new_page.locator(".abstract")).to_contain_text("Abstract:")
            await expect(new_page.locator("h2")).to_contain_text("Introduction")
            await expect(new_page.locator(".equation")).to_be_visible()

            # Verify attribution still shows (though user may be anonymized)
            await expect(new_page.locator(".attribution-title")).to_contain_text(scroll_title[:60])
            await expect(new_page.locator(".attribution-meta")).to_contain_text("Biology")

            # Verify modal and license information persists
            await new_page.click(".fab")
            await new_page.wait_for_selector(".modal.show", state="visible")

            # Verify license information is preserved
            await expect(new_page.locator(".license-info")).to_contain_text("License:")
            await expect(new_page.locator(".license-text")).to_contain_text("All Rights Reserved")
            await expect(new_page.locator(".license-description")).to_contain_text(
                "Permission required for reuse"
            )

            # Verify no CC BY link (since this is ARR license)
            cc_link = new_page.locator('.license-link[href*="creativecommons.org"]')
            await expect(cc_link).not_to_be_visible()

            # Verify download still works
            download_btn = new_page.locator("#download-btn")
            await expect(download_btn).to_be_visible()

            # Close modal
            await new_page.click(".modal-close")

            # Verify interactive JavaScript still works
            equation = new_page.locator(".equation").first()
            await equation.hover()
            # Note: Can't easily test hover styles in Playwright, but hover action should not error

        finally:
            await new_context.close()

    async def test_cross_browser_public_access(
        self,
        playwright,
        test_server: str,
        seeded_database: dict,
        sample_html_content: str,
        e2e_helpers: E2EHelpers,
    ):
        """Test scroll public access across both Chromium and Firefox browsers."""
        import uuid

        test_id = uuid.uuid4().hex[:8]

        # Create scroll in Chromium
        chromium = await playwright.chromium.launch(headless=True)
        chromium_context = await chromium.new_context()
        chromium_page = await chromium_context.new_page()

        scroll_url = None

        try:
            user_email = f"crossbrowser_{test_id}@example.com"

            # Register and upload in Chromium
            await e2e_helpers.register_user(
                chromium_page, test_server, user_email, "testpass123", f"Cross Browser {test_id}"
            )

            scroll_url = await e2e_helpers.upload_scroll(
                page=chromium_page,
                server_url=test_server,
                title=f"Cross Browser Test {test_id}",
                authors=f"Cross Browser {test_id}",
                abstract="Testing cross-browser compatibility",
                html_content=sample_html_content,
                license="cc-by-4.0",
            )

            assert scroll_url is not None

        finally:
            await chromium_context.close()
            await chromium.close()

        # Test access in Firefox
        firefox = await playwright.firefox.launch(headless=True)
        firefox_context = await firefox.new_context()
        firefox_page = await firefox_context.new_page()

        try:
            # Access scroll in Firefox
            await firefox_page.goto(scroll_url)
            await firefox_page.wait_for_load_state("networkidle")

            # Verify content loads in Firefox
            await expect(firefox_page.locator("h1")).to_contain_text(
                "A Novel Approach to E2E Testing"
            )

            # Verify modal works in Firefox
            await firefox_page.click(".fab")
            await firefox_page.wait_for_selector(".modal.show", state="visible")
            await expect(firefox_page.locator(".license-link")).to_contain_text("CC BY 4.0")

        finally:
            await firefox_context.close()
            await firefox.close()
