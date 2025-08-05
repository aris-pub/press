"""E2E test configuration and fixtures for Scroll Press.

IMPORTANT: Due to pytest-asyncio event loop conflicts, DO NOT use session-scoped
Playwright fixtures (browser, browser_context, page) in e2e tests. They cause deadlocks.

Instead, use async with async_playwright() directly in test functions:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # ... test code ...
        await browser.close()
"""

import os

import pytest


@pytest.fixture
def test_server():
    """Get the test server URL based on environment.

    Uses the existing server that's already running:
    - CI: http://127.0.0.1:8000 (started by CI workflow)
    - Local: http://127.0.0.1:7999 (started with `just dev`)
    """
    if os.getenv("CI"):
        return "http://127.0.0.1:8000"
    else:
        return "http://127.0.0.1:7999"
