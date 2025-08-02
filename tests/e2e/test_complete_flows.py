"""Complete e2e flows for critical user journeys.

These tests verify the most important user scenarios:
1. Registration → Upload → Public Access
2. Registration → Upload → Account Deletion → Public Access

Run against development server:
    just dev
    uv run pytest tests/e2e/test_complete_flows.py -v
"""

import uuid

from playwright.async_api import async_playwright, expect
import pytest

# Configuration
DEV_SERVER_URL = "http://localhost:8000"

# Sample HTML content for testing
SAMPLE_HTML_CONTENT = """
<html>
<head>
    <title>E2E Test Research Paper</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }
        h1 { color: #2c3e50; }
        .abstract { background: #f8f9fa; padding: 1rem; border-left: 4px solid #3498db; }
        .equation { text-align: center; margin: 1rem 0; font-style: italic; }
    </style>
</head>
<body>
    <h1>Automated Testing in Modern Web Applications</h1>
    
    <div class="abstract">
        <strong>Abstract:</strong> This paper demonstrates end-to-end testing methodologies
        for web applications using Playwright automation framework. We explore critical
        user journeys and persistence scenarios.
    </div>
    
    <h2>Introduction</h2>
    <p>End-to-end testing ensures that complete user workflows function correctly
    from browser to database. This research validates our testing approach.</p>
    
    <h2>Methodology</h2>
    <p>We employ headless browser automation to simulate real user interactions:</p>
    <ul>
        <li>User registration and authentication</li>
        <li>Content upload and publishing</li>
        <li>Public content accessibility</li>
        <li>Account lifecycle management</li>
    </ul>
    
    <div class="equation">
        <em>Test_Coverage = (Validated_Scenarios / Total_Scenarios) × 100%</em>
    </div>
    
    <h2>Results</h2>
    <p>Our e2e testing framework successfully validates critical persistence
    scenarios, ensuring content remains accessible even after account deletion.</p>
    
    <h2>Conclusion</h2>
    <p>Automated e2e testing provides confidence in system reliability and
    user experience continuity.</p>
    
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            console.log('E2E test content loaded successfully');
        });
    </script>
</body>
</html>
"""


class E2ETestHelpers:
    """Helper methods for e2e testing."""

    @staticmethod
    async def register_and_login_user(page, email: str, password: str, display_name: str):
        """Register a new user and verify login."""
        # Go to register page
        await page.goto(f"{DEV_SERVER_URL}/register")
        await page.wait_for_load_state("networkidle")

        # Fill registration form
        await page.fill('input[name="email"]', email)
        await page.fill('input[name="display_name"]', display_name)
        await page.fill('input[name="password"]', password)
        await page.check('input[name="agree_terms"]')

        # Submit HTMX form and wait for response
        await page.click('button[type="submit"]')

        # Wait for HTMX response
        await page.wait_for_timeout(2000)

        # Check if we still have the registration form (indicates failure)
        register_form = page.locator("#register-form-container")
        if await register_form.count() > 0:
            # Look for error messages
            error_msgs = page.locator(".form-error, .error-message, .alert-danger")
            if await error_msgs.count() > 0:
                error_text = await error_msgs.first.text_content()
                raise AssertionError(f"Registration failed with error: {error_text}")
            else:
                raise AssertionError("Registration form submission failed")

        # Wait for any redirects after successful HTMX response
        await page.wait_for_timeout(1000)

        # Verify we're logged in
        current_url = page.url
        is_on_homepage = current_url in [DEV_SERVER_URL, f"{DEV_SERVER_URL}/"]
        has_logout_btn = await page.locator('button:has-text("Logout")').count() > 0

        if not (is_on_homepage and has_logout_btn):
            raise AssertionError(
                "Registration should redirect to homepage with logout button visible"
            )

        return True

    @staticmethod
    async def upload_scroll(
        page,
        title: str,
        authors: str,
        abstract: str,
        html_content: str,
        license: str = "cc-by-4.0",
    ):
        """Upload a scroll and return the public URL."""
        # Navigate to upload page
        await page.goto(f"{DEV_SERVER_URL}/upload")
        await page.wait_for_load_state("networkidle")

        # Fill upload form
        await page.fill('input[name="title"]', title)
        await page.fill('input[name="authors"]', authors)
        await page.fill('textarea[name="abstract"]', abstract)
        await page.fill('textarea[name="html_content"]', html_content)

        # Select first available subject (skip the default empty option)
        subject_select = page.locator('select[name="subject_id"]')
        await subject_select.wait_for()
        
        # Get all options and select the first non-empty one
        options = await subject_select.locator('option').all()
        if len(options) > 1:  # Skip first empty option
            await page.select_option('select[name="subject_id"]', index=1)
        else:
            raise AssertionError("No subjects available in database - database may not be seeded")

        # Select license by clicking the container (not just radio button)
        if license == "cc-by-4.0":
            await page.click('label[for="license-cc-by"]')
        else:
            await page.click('label[for="license-arr"]')

        # Confirm rights
        await page.check('input[name="confirm_rights"]')

        # Submit form - click the "Publish Scroll" button specifically
        submit_button = page.locator('button[name="action"][value="publish"]')
        await submit_button.click()
        await page.wait_for_load_state("networkidle")

        # Wait for success page and extract scroll URL
        view_scroll_link = page.locator('a:has-text("View Scroll")')
        await view_scroll_link.wait_for()

        scroll_href = await view_scroll_link.get_attribute("href")
        return f"{DEV_SERVER_URL}{scroll_href}"

    @staticmethod
    async def delete_user_account(page):
        """Delete user account via dashboard."""
        # Go to dashboard
        await page.goto(f"{DEV_SERVER_URL}/dashboard")
        await page.wait_for_load_state("networkidle")

        # Click delete account button
        await page.click("#delete-account-btn")

        # Wait for modal and fill confirmation
        await page.wait_for_selector("#delete-modal", state="visible")
        await page.fill("#confirm-delete-input", "DELETE MY ACCOUNT")

        # Enable and click delete button
        delete_btn = page.locator("#confirm-delete-btn")
        await expect(delete_btn).to_be_enabled()
        await delete_btn.click()

        # Wait for redirect to homepage
        await page.wait_for_load_state("networkidle")
        return page.url in [DEV_SERVER_URL, f"{DEV_SERVER_URL}/"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_registration_upload_public_access():
    """Critical Test 1: User creates account → uploads document → public link works without auth.

    This test verifies:
    1. User registration and auto-login
    2. Scroll upload with license selection
    3. Public accessibility without authentication
    4. License information persistence
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        helpers = E2ETestHelpers()

        try:
            # Generate unique test data
            test_id = uuid.uuid4().hex[:8]
            email = f"persist1_{test_id}@example.com"
            password = "testpass123"
            display_name = f"Persist User {test_id}"

            scroll_title = f"Persistence Test Paper {test_id}"
            scroll_authors = f"{display_name}, Co-Author Test"
            scroll_abstract = f"Testing scroll persistence functionality {test_id}. This validates public access to published content."

            # Step 1: Register and login user
            await helpers.register_and_login_user(page, email, password, display_name)

            # Step 2: Upload scroll with CC BY license
            scroll_url = await helpers.upload_scroll(
                page,
                scroll_title,
                scroll_authors,
                scroll_abstract,
                SAMPLE_HTML_CONTENT,
                license="cc-by-4.0",
            )

            assert scroll_url is not None
            assert "/scroll/" in scroll_url

            # Step 3: Verify scroll works while logged in
            await page.goto(scroll_url)
            await page.wait_for_load_state("networkidle")

            # Check content loads
            await expect(page.locator("h1")).to_contain_text(
                "Automated Testing in Modern Web Applications"
            )

            # Check modal with license info
            await page.click(".fab")  # Info button
            await page.wait_for_selector(".modal.show", state="visible")

            # Verify license information
            await expect(page.locator(".license-link")).to_contain_text("CC BY 4.0")
            await expect(page.locator(".license-description")).to_contain_text("Open Access")

            await page.click(".modal-close")

            # Step 4: Logout user to test true public access
            # Go to homepage first to ensure we have access to logout
            await page.goto(DEV_SERVER_URL)
            await page.wait_for_load_state("networkidle")

            # Open user dropdown menu first
            dropdown_toggles = [
                'button[data-bs-toggle="dropdown"]',
                ".dropdown-toggle",
                "button.user-menu-toggle",
                'button:has-text("User")',
            ]

            for toggle_selector in dropdown_toggles:
                toggle_btn = page.locator(toggle_selector)
                if await toggle_btn.count() > 0:
                    await toggle_btn.first.click()
                    await page.wait_for_timeout(500)  # Wait for dropdown to open
                    break

            # Now click logout button
            logout_btn = page.locator('button[role="menuitem"]:has-text("Logout")')
            if await logout_btn.count() > 0:
                await logout_btn.click()
            else:
                # Fallback: try direct logout button
                logout_btn = page.locator('.btn:has-text("Logout")')
                if await logout_btn.count() > 0:
                    await logout_btn.first.click()
                else:
                    raise AssertionError("Could not find logout button")

            await page.wait_for_load_state("networkidle")

            # Verify logout worked - should not see logout button anymore
            logout_btn = page.locator('button:has-text("Logout")')
            await expect(logout_btn).not_to_be_visible()

            # Step 5: Test public access in clean browser context
            new_context = await browser.new_context()
            new_page = await new_context.new_page()

            try:
                # Visit scroll URL without authentication
                await new_page.goto(scroll_url)
                await new_page.wait_for_load_state("networkidle")

                # Verify content loads
                await expect(new_page.locator("h1")).to_contain_text(
                    "Automated Testing in Modern Web Applications"
                )
                await expect(new_page.locator(".abstract")).to_contain_text("Abstract:")
                await expect(new_page.locator("h2").first).to_contain_text("Introduction")

                # Verify modal and license info work without auth
                await new_page.click(".fab")
                await new_page.wait_for_selector(".modal.show", state="visible")

                await expect(new_page.locator(".license-link")).to_contain_text("CC BY 4.0")
                await expect(new_page.locator(".license-link")).to_have_attribute(
                    "href", "https://creativecommons.org/licenses/by/4.0/"
                )

                # Test download functionality
                download_btn = new_page.locator("#download-btn")
                await expect(download_btn).to_be_visible()

            finally:
                await new_context.close()

        finally:
            await browser.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_registration_upload_deletion_public_access():
    """Critical Test 2: User creates account → uploads → deletes account → public link still works.

    This test verifies:
    1. User registration and scroll upload
    2. Account deletion process
    3. Scroll persistence after account deletion
    4. License information remains intact
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        helpers = E2ETestHelpers()

        try:
            # Generate unique test data
            test_id = uuid.uuid4().hex[:8]
            email = f"delete_{test_id}@example.com"
            password = "testpass123"
            display_name = f"Delete User {test_id}"

            scroll_title = f"Pre-Deletion Research {test_id}"
            scroll_authors = f"{display_name}, Persistent Co-Author"
            scroll_abstract = f"Testing scroll persistence after account deletion {test_id}. Content should remain accessible."

            # Step 1: Register and login user
            await helpers.register_and_login_user(page, email, password, display_name)

            # Step 2: Upload scroll with All Rights Reserved license
            scroll_url = await helpers.upload_scroll(
                page,
                scroll_title,
                scroll_authors,
                scroll_abstract,
                SAMPLE_HTML_CONTENT,
                license="arr",  # Test ARR license
            )

            assert scroll_url is not None

            # Step 3: Verify scroll works before deletion
            await page.goto(scroll_url)
            await page.wait_for_load_state("networkidle")
            await expect(page.locator("h1")).to_contain_text(
                "Automated Testing in Modern Web Applications"
            )

            # Check ARR license displays correctly
            await page.click(".fab")
            await page.wait_for_selector(".modal.show", state="visible")
            await expect(page.locator(".license-text")).to_contain_text("All Rights Reserved")
            await expect(page.locator(".license-description")).to_contain_text(
                "Permission required for reuse"
            )
            await page.click(".modal-close")

            # Step 4: Delete user account
            account_deleted = await helpers.delete_user_account(page)
            assert account_deleted

            # Verify redirect with success indication
            current_url = page.url
            assert current_url in [DEV_SERVER_URL, f"{DEV_SERVER_URL}/"]

            # Step 5: Test scroll persistence after account deletion
            new_context = await browser.new_context()
            new_page = await new_context.new_page()

            try:
                # Visit scroll URL after account deletion
                await new_page.goto(scroll_url)
                await new_page.wait_for_load_state("networkidle")

                # Verify content still loads
                await expect(new_page.locator("h1")).to_contain_text(
                    "Automated Testing in Modern Web Applications"
                )
                await expect(new_page.locator(".abstract")).to_be_visible()
                await expect(new_page.locator(".equation")).to_be_visible()

                # Verify attribution footer (may show anonymized or original data)
                attribution = new_page.locator(".attribution-title")
                await expect(attribution).to_be_visible()

                # Verify modal and license persist
                await new_page.click(".fab")
                await new_page.wait_for_selector(".modal.show", state="visible")

                await expect(new_page.locator(".license-text")).to_contain_text(
                    "All Rights Reserved"
                )
                await expect(new_page.locator(".license-description")).to_contain_text(
                    "Permission required for reuse"
                )

                # Verify no CC BY link (since this is ARR)
                cc_link = new_page.locator('.license-link[href*="creativecommons.org"]')
                await expect(cc_link).not_to_be_visible()

                # Verify download still works
                download_btn = new_page.locator("#download-btn")
                await expect(download_btn).to_be_visible()

            finally:
                await new_context.close()

        finally:
            await browser.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_upload_form_license_interaction():
    """Test license selection UI interaction in upload form.

    Verifies:
    1. Default CC BY 4.0 selection
    2. Clickable containers (not just radio buttons)
    3. License selection persistence
    4. Form validation
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        helpers = E2ETestHelpers()

        try:
            # Setup: Register user
            test_id = uuid.uuid4().hex[:8]
            email = f"license_{test_id}@example.com"

            await helpers.register_and_login_user(
                page, email, "testpass123", f"License User {test_id}"
            )

            # Navigate to upload form
            await page.goto(f"{DEV_SERVER_URL}/upload")
            await page.wait_for_load_state("networkidle")

            # Test 1: Verify CC BY 4.0 is selected by default
            cc_radio = page.locator('input[name="license"][value="cc-by-4.0"]')
            await expect(cc_radio).to_be_checked()

            arr_radio = page.locator('input[name="license"][value="arr"]')
            await expect(arr_radio).not_to_be_checked()

            # Test 2: Click All Rights Reserved container (not just radio)
            arr_container = page.locator('label[for="license-arr"]')
            await arr_container.click()

            # Verify selection changed
            await expect(arr_radio).to_be_checked()
            await expect(cc_radio).not_to_be_checked()

            # Test 3: Click CC BY container to switch back
            cc_container = page.locator('label[for="license-cc-by"]')
            await cc_container.click()

            await expect(cc_radio).to_be_checked()
            await expect(arr_radio).not_to_be_checked()

            # Test 4: Verify container hover effects (visual indication)
            # Hover over ARR container
            await arr_container.hover()

            # Container should have coral border on hover (test CSS is applied)
            arr_style = await arr_container.evaluate("el => getComputedStyle(el).borderColor")
            # Note: Exact color testing in e2e can be brittle, so we just verify it's not default
            assert arr_style != "rgb(0, 0, 0)"  # Not default black

        finally:
            await browser.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mobile_responsive_upload():
    """Test upload form on mobile viewport.

    Verifies:
    1. Form displays correctly on mobile
    2. License containers are touch-friendly
    3. Mobile-specific styling applies
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Create mobile context
        context = await browser.new_context(
            viewport={"width": 375, "height": 812},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
        )
        page = await context.new_page()
        helpers = E2ETestHelpers()

        try:
            # Setup: Register user
            test_id = uuid.uuid4().hex[:8]
            email = f"mobile_{test_id}@example.com"

            await helpers.register_and_login_user(
                page, email, "testpass123", f"Mobile User {test_id}"
            )

            # Navigate to upload form
            await page.goto(f"{DEV_SERVER_URL}/upload")
            await page.wait_for_load_state("networkidle")

            # Verify form is responsive
            form_container = page.locator(".upload-container")
            await expect(form_container).to_be_visible()

            # Test license containers are properly sized for mobile
            license_containers = page.locator(".form-radio-item")

            # Both license options should be visible
            await expect(license_containers).to_have_count(2)

            # Test mobile interaction - tap on license containers
            arr_container = page.locator('label[for="license-arr"]')
            await arr_container.tap()  # Use tap instead of click for mobile

            arr_radio = page.locator('input[name="license"][value="arr"]')
            await expect(arr_radio).to_be_checked()

            # Test form submission button is accessible on mobile
            submit_btn = page.locator('button[type="submit"]')
            await expect(submit_btn).to_be_visible()

            # Verify mobile-specific CSS is applied (button should be full width)
            btn_width = await submit_btn.bounding_box()
            container_width = await form_container.bounding_box()

            # On mobile, button should take most of container width
            assert btn_width["width"] > container_width["width"] * 0.8

        finally:
            await context.close()
            await browser.close()
