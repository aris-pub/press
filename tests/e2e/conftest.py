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

        # Seed with test data
        TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        session = TestSessionLocal()
        try:
            # Manually seed basic data needed for E2E tests
            from sqlalchemy import text

            from app.auth.utils import get_password_hash
            from app.models.scroll import Scroll, Subject
            from app.models.user import User

            # Create subjects
            subjects_data = [
                {"name": "Computer Science", "description": "Computing and software"},
                {"name": "Physics", "description": "Physical sciences"},
                {"name": "Biology", "description": "Life sciences"},
            ]

            for subject_data in subjects_data:
                subject = Subject(**subject_data)
                session.add(subject)

            await session.commit()

            # Create a test user
            test_user = User(
                email="testuser@example.com",
                password_hash=get_password_hash("testpass"),
                display_name="Test User",
                email_verified=True,
            )
            session.add(test_user)
            await session.commit()
            await session.refresh(test_user)

            # Get first subject for scrolls
            subjects = await session.execute(text("SELECT * FROM subjects LIMIT 1"))
            first_subject = subjects.first()

            if first_subject:
                # Create a test scroll
                test_scroll = Scroll(
                    title="Test Research Paper",
                    authors="Test Author",
                    abstract="This is a test research paper for E2E testing.",
                    html_content="<h1>Test Paper</h1><p>Test content</p>",
                    keywords=["test", "research"],
                    license="cc-by-4.0",
                    content_hash="test_hash",
                    url_hash="test_url_hash",
                    status="published",
                    user_id=test_user.id,
                    subject_id=first_subject.id,
                )
                session.add(test_scroll)
                await session.commit()

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
