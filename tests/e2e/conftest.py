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

import asyncio
import os
import sys
import time

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import Base
from main import app


@pytest.fixture(scope="session")
def test_server():
    """Start a test server with in-memory SQLite database."""
    if os.getenv("CI"):
        # CI uses the server started by the workflow
        yield "http://127.0.0.1:8000"
        return

    # Local: Start our own test server
    import socket
    import threading

    import uvicorn

    # Find available port
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()

    # Set up test environment
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["TESTING"] = "1"
    os.environ["E2E_TESTING"] = "1"  # Disable HTTPS redirect for E2E tests

    # Override the database connection in the app
    TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    async def setup_test_db():
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Use the same seed functions as CI for consistency
        from scripts.seed import seed_subjects, seed_users, seed_scrolls

        TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        session = TestSessionLocal()
        try:
            await seed_subjects(session)
            await seed_users(session)
            await seed_scrolls(session)
        finally:
            await session.close()

    # Set up the database
    asyncio.run(setup_test_db())

    # Override the database dependency
    from app.database import get_db

    async def override_get_db():
        TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        session = TestSessionLocal()
        try:
            yield session
        finally:
            await session.close()

    app.dependency_overrides[get_db] = override_get_db

    # Start server in thread
    def run_server():
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to start
    server_url = f"http://127.0.0.1:{port}"
    for _ in range(30):  # Wait up to 30 seconds
        try:
            response = httpx.get(server_url, timeout=1)
            if response.status_code == 200:
                break
        except (httpx.RequestError, httpx.HTTPStatusError):
            time.sleep(1)
    else:
        raise RuntimeError("Test server failed to start")

    yield server_url

    # Cleanup
    app.dependency_overrides.clear()
