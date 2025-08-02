"""Simplified E2E test configuration."""

from playwright.async_api import async_playwright
import pytest_asyncio


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
