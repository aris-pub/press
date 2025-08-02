"""E2E test configuration and fixtures for Scroll Press - Simplified Version."""

import asyncio
import os

from playwright.async_api import async_playwright
import pytest_asyncio
import uvicorn

# Test server configuration
TEST_SERVER_HOST = "127.0.0.1"
TEST_SERVER_PORT = 8001
TEST_SERVER_URL = f"http://{TEST_SERVER_HOST}:{TEST_SERVER_PORT}"


@pytest_asyncio.fixture(scope="session")
async def test_server():
    """Start test server for e2e tests."""
    # Set up environment for testing
    os.environ["TESTING"] = "1"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_e2e.db"

    # Import after setting env vars
    from main import app

    config = uvicorn.Config(
        app=app,
        host=TEST_SERVER_HOST,
        port=TEST_SERVER_PORT,
        log_level="error",  # Suppress server logs
    )
    server = uvicorn.Server(config)

    # Start server in background
    server_task = asyncio.create_task(server.serve())

    # Wait for server to start
    await asyncio.sleep(2)

    yield TEST_SERVER_URL

    # Shutdown
    server.should_exit = True
    await server_task


@pytest_asyncio.fixture(scope="session")
async def playwright():
    """Playwright instance."""
    async with async_playwright() as p:
        yield p


@pytest_asyncio.fixture(scope="session")
async def browser(playwright):
    """Browser instance."""
    browser = await playwright.chromium.launch(headless=True)
    yield browser
    await browser.close()


@pytest_asyncio.fixture
async def page(browser):
    """Page instance."""
    context = await browser.new_context()
    page = await context.new_page()
    yield page
    await context.close()


# Simple helper class
class SimpleE2EHelpers:
    @staticmethod
    async def register_user(page, server_url: str, email: str, password: str, display_name: str):
        """Register a new user."""
        await page.goto(f"{server_url}/register")

        await page.fill('input[name="email"]', email)
        await page.fill('input[name="password"]', password)
        await page.fill('input[name="confirm_password"]', password)
        await page.fill('input[name="display_name"]', display_name)
        await page.check('input[name="agree_terms"]')

        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")

        return page.url == f"{server_url}/"


@pytest_asyncio.fixture
async def e2e_helpers():
    """Simple e2e helpers."""
    return SimpleE2EHelpers()
