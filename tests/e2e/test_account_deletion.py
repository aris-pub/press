"""E2E tests for account deletion flow.

Tests the critical path: login -> dashboard -> request deletion link -> open the emailed
link -> confirm -> verify logged out -> verify published scrolls remain accessible.

The e2e server runs in this process, so the email service is replaced with one that
records the link instead of sending it.
"""

import time

from playwright.async_api import async_playwright, expect
import pytest

pytestmark = pytest.mark.e2e


class CapturingEmailService:
    def __init__(self):
        self.tokens = []

    async def send_account_deletion_email(self, to_email, name, token):
        self.tokens.append((to_email, token))
        return True

    def __getattr__(self, name):
        # Signup also sends emails (verification, admin notice). Accept and drop them.
        async def accept(*args, **kwargs):
            return True

        return accept


@pytest.fixture
def deletion_emails(monkeypatch):
    service = CapturingEmailService()
    monkeypatch.setattr("app.routes.auth.get_email_service", lambda: service)
    return service


async def _request_and_confirm_deletion(page, test_server, deletion_emails, email):
    """Use the dashboard modal to get a link, then delete through the confirmation page."""
    await page.click("#delete-account-btn")
    await expect(page.locator("#delete-modal")).to_be_visible()
    await page.fill("#confirm-delete", "DELETE")
    await page.dispatch_event("#confirm-delete", "input")
    confirm_btn = page.locator("#confirm-delete-btn")
    await expect(confirm_btn).to_be_enabled()
    await confirm_btn.click()

    await expect(page.locator("#delete-request-status")).to_contain_text(
        f"We sent a link to {email}"
    )
    assert [to for to, _ in deletion_emails.tokens] == [email]
    token = deletion_emails.tokens[0][1]

    # Requesting the link deletes nothing: the dashboard still loads.
    await page.goto(f"{test_server}/dashboard")
    await expect(page.locator("h2:has-text('Account Management')")).to_be_visible()

    # Opening the link shows a confirmation page and still deletes nothing.
    await page.goto(f"{test_server}/account/delete-confirm?token={token}")
    await expect(page.locator("body")).to_contain_text(email)
    await page.goto(f"{test_server}/dashboard")
    await expect(page.locator("h2:has-text('Account Management')")).to_be_visible()

    await page.goto(f"{test_server}/account/delete-confirm?token={token}")
    await page.click("#confirm-account-deletion")
    await page.wait_for_url("**/?message=account_deleted", timeout=10000)
    return token


async def test_account_deletion_flow(test_server, deletion_emails):
    """Test complete account deletion: register, request link, confirm, verify logged out."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(f"{test_server}/register")

            timestamp = int(time.time())
            test_email = f"delete-test-{timestamp}@example.com"
            await page.fill('input[name="email"]', test_email)
            await page.fill('input[name="display_name"]', "Delete Test User")
            await page.fill('input[name="password"]', "deletepassword123")
            await page.fill('input[name="confirm_password"]', "deletepassword123")
            await page.check('input[name="agree_terms"]')
            await page.click('button[type="submit"]')
            await page.wait_for_url(f"{test_server}/")

            await page.goto(f"{test_server}/dashboard")
            await expect(page.locator("h2:has-text('Account Management')")).to_be_visible()

            token = await _request_and_confirm_deletion(
                page, test_server, deletion_emails, test_email
            )

            # Verify we're logged out: navigating to dashboard should redirect
            await page.goto(f"{test_server}/dashboard")
            current_url = page.url
            assert (
                "/login" in current_url or "/register" in current_url or current_url.endswith("/")
            ), f"Expected redirect away from dashboard after deletion, but URL is {current_url}"

            # The link works only once
            await page.goto(f"{test_server}/account/delete-confirm?token={token}")
            await expect(page.locator("body")).to_contain_text("invalid or expired")

            # Verify login with deleted credentials fails
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', test_email)
            await page.fill('input[name="password"]', "deletepassword123")
            await page.click('button[type="submit"]')

            await expect(
                page.locator('li:has-text("Incorrect email or password")')
            ).to_be_visible()

        finally:
            await browser.close()


async def test_account_deletion_preserves_published_scrolls(test_server, deletion_emails):
    """Test that published scrolls remain accessible after account deletion.

    Uses a seeded user who owns published scrolls. After deleting the account,
    verifies the scrolls are still publicly accessible.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login as a seeded user who has published scrolls
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "john.smith@university.edu")
            await page.fill('input[name="password"]', "password123")
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(1500)

            # Navigate to dashboard and collect scroll URLs
            await page.goto(f"{test_server}/dashboard")
            await page.wait_for_load_state("networkidle")

            scroll_links = page.locator("a.scroll-card-link")
            scroll_count = await scroll_links.count()

            if scroll_count == 0:
                pytest.skip("No published scrolls found for seeded user")

            # Collect all scroll URLs before deletion
            scroll_urls = []
            for i in range(scroll_count):
                href = await scroll_links.nth(i).get_attribute("href")
                scroll_urls.append(f"{test_server}{href}")

            await _request_and_confirm_deletion(
                page, test_server, deletion_emails, "john.smith@university.edu"
            )

            # Verify each scroll is still publicly accessible
            for url in scroll_urls:
                response = await page.goto(url)
                assert response.status == 200, (
                    f"Scroll at {url} returned {response.status} after account deletion"
                )
                # Verify the page has scroll content (not an error page)
                await expect(page.locator("#paper-frame")).to_be_visible(timeout=5000)

        finally:
            await browser.close()


async def test_account_deletion_cancel(test_server):
    """Test that cancelling account deletion does not delete the account."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Register and login
            await page.goto(f"{test_server}/register")

            timestamp = int(time.time())
            test_email = f"cancel-delete-{timestamp}@example.com"
            await page.fill('input[name="email"]', test_email)
            await page.fill('input[name="display_name"]', "Cancel Delete User")
            await page.fill('input[name="password"]', "cancelpassword123")
            await page.fill('input[name="confirm_password"]', "cancelpassword123")
            await page.check('input[name="agree_terms"]')
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(2500)

            # Navigate to dashboard
            await page.goto(f"{test_server}/dashboard")
            await page.wait_for_load_state("networkidle")

            # Open delete modal
            await page.click("#delete-account-btn")
            await expect(page.locator("#delete-modal")).to_be_visible()

            # Type DELETE but then cancel
            await page.fill("#confirm-delete", "DELETE")
            await page.dispatch_event("#confirm-delete", "input")

            # Click Cancel
            await page.click("#delete-modal .btn-secondary")

            # Modal should be hidden
            await expect(page.locator("#delete-modal")).to_be_hidden()

            # Account should still work - reload dashboard
            await page.goto(f"{test_server}/dashboard")
            await page.wait_for_load_state("networkidle")
            await expect(page.locator("h2:has-text('Account Management')")).to_be_visible()

        finally:
            await browser.close()


async def test_account_deletion_requires_confirmation(test_server):
    """Test that the delete button stays disabled without typing DELETE."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Register and login
            await page.goto(f"{test_server}/register")

            timestamp = int(time.time())
            test_email = f"noconfirm-delete-{timestamp}@example.com"
            await page.fill('input[name="email"]', test_email)
            await page.fill('input[name="display_name"]', "No Confirm User")
            await page.fill('input[name="password"]', "noconfirmpassword123")
            await page.fill('input[name="confirm_password"]', "noconfirmpassword123")
            await page.check('input[name="agree_terms"]')
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(2500)

            await page.goto(f"{test_server}/dashboard")
            await page.wait_for_load_state("networkidle")

            # Open delete modal
            await page.click("#delete-account-btn")
            await expect(page.locator("#delete-modal")).to_be_visible()

            confirm_btn = page.locator("#confirm-delete-btn")

            # Button disabled with empty input
            await expect(confirm_btn).to_be_disabled()

            # Button disabled with wrong text
            await page.fill("#confirm-delete", "delete")
            await page.dispatch_event("#confirm-delete", "input")
            await expect(confirm_btn).to_be_disabled()

            await page.fill("#confirm-delete", "DELET")
            await page.dispatch_event("#confirm-delete", "input")
            await expect(confirm_btn).to_be_disabled()

            # Button enabled only with exact "DELETE"
            await page.fill("#confirm-delete", "DELETE")
            await page.dispatch_event("#confirm-delete", "input")
            await expect(confirm_btn).to_be_enabled()

        finally:
            await browser.close()
