"""E2E tests for account deletion flow.

Tests the critical path: login -> dashboard -> request deletion link -> open the emailed
link -> confirm -> verify logged out -> verify published scrolls remain accessible.

The e2e server cannot send email, so the test issues the deletion link itself in the
server's database.
"""

import os
import time

from playwright.async_api import async_playwright, expect
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.e2e


@pytest_asyncio.fixture
async def server_db(test_server):
    """Sessions on the database the e2e server uses.

    The deletion link is normally emailed, and the e2e server cannot send email (in CI it
    is a separate process with no email key). So the test issues the link itself, with the
    same code the server uses, straight into the server's database.
    """
    if os.getenv("CI"):
        engine = create_async_engine(os.environ["DATABASE_URL"])
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        await engine.dispose()
    else:
        from tests.e2e import conftest

        yield async_sessionmaker(
            conftest.LOCAL_ENGINE, class_=AsyncSession, expire_on_commit=False
        )


async def _issue_deletion_link(server_db, test_server, email):
    from app.auth.tokens import create_account_deletion_token, invalidate_user_tokens
    from app.models.user import User

    async with server_db() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        await invalidate_user_tokens(db, user.id, "account_deletion")
        token = await create_account_deletion_token(db, user.id)
    return f"{test_server}/account/delete-confirm?token={token}"


async def _request_and_confirm_deletion(page, test_server, server_db, email):
    """Press the dashboard button, then delete through the confirmation page."""
    await page.click("#delete-account-btn")
    await expect(page.locator("#delete-modal")).to_be_visible()
    await page.fill("#confirm-delete", "DELETE")
    await page.dispatch_event("#confirm-delete", "input")
    confirm_btn = page.locator("#confirm-delete-btn")
    await expect(confirm_btn).to_be_enabled()

    # The request reaches the server with a valid CSRF token and stops only because the
    # e2e server has no email service. A CSRF failure would give a different message.
    async with page.expect_event("dialog") as dialog_info:
        await confirm_btn.click()
    dialog = await dialog_info.value
    message = dialog.message
    await dialog.accept()
    assert message.startswith("Account deletion failed: "), message
    assert "Email is not available" in message, message

    # Pressing the button deletes nothing.
    await page.goto(f"{test_server}/dashboard")
    await expect(page.locator("h2:has-text('Account Management')")).to_be_visible()

    link = await _issue_deletion_link(server_db, test_server, email)

    # Opening the link shows the confirmation page and still deletes nothing.
    await page.goto(link)
    await expect(page.locator("body")).to_contain_text(email)
    await page.goto(f"{test_server}/dashboard")
    await expect(page.locator("h2:has-text('Account Management')")).to_be_visible()

    await page.goto(link)
    await page.click("#confirm-account-deletion")
    await page.wait_for_url("**/?message=account_deleted", timeout=10000)
    return link


async def test_account_deletion_flow(test_server, server_db):
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

            link = await _request_and_confirm_deletion(page, test_server, server_db, test_email)

            # Verify we're logged out: navigating to dashboard should redirect
            await page.goto(f"{test_server}/dashboard")
            current_url = page.url
            assert (
                "/login" in current_url or "/register" in current_url or current_url.endswith("/")
            ), f"Expected redirect away from dashboard after deletion, but URL is {current_url}"

            # The link works only once
            await page.goto(link)
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


async def test_account_deletion_preserves_published_scrolls(test_server, server_db):
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
                page, test_server, server_db, "john.smith@university.edu"
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
