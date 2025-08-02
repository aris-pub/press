"""E2E test configuration and fixtures for Scroll Press."""

import asyncio
import os
import socket
import tempfile
from typing import AsyncGenerator
import uuid

from fastapi import FastAPI
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
import uvicorn

from app.auth.utils import get_password_hash
from app.database import Base, get_db
from app.models.scroll import Subject
from app.models.user import User
from main import app as fastapi_app

# Test server configuration
TEST_SERVER_HOST = "127.0.0.1"


def find_free_port():
    """Find a free port for the test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest_asyncio.fixture(scope="session")
async def test_database_url():
    """Create a test database for e2e tests using SQLite."""
    # Create a temporary SQLite database file for e2e tests
    temp_dir = tempfile.mkdtemp()
    test_db_file = os.path.join(temp_dir, f"test_press_e2e_{uuid.uuid4().hex[:8]}.db")
    test_db_url = f"sqlite+aiosqlite:///{test_db_file}"

    yield test_db_url

    # Cleanup: remove temp database file
    if os.path.exists(test_db_file):
        os.unlink(test_db_file)


@pytest_asyncio.fixture(scope="session")
async def test_app(test_database_url: str):
    """Create and configure FastAPI app for e2e testing."""
    # Override database URL for testing
    original_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_database_url
    os.environ["TESTING"] = "1"

    # Create engine for SQLite
    engine = create_async_engine(
        test_database_url,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory for dependency override
    TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            await session.close()

    # Override the database dependency
    fastapi_app.dependency_overrides[get_db] = override_get_db

    yield fastapi_app

    # Cleanup
    fastapi_app.dependency_overrides.clear()
    await engine.dispose()

    # Restore original DATABASE_URL
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)


@pytest_asyncio.fixture(scope="session")
async def test_server(test_app: FastAPI):
    """Start test server for e2e tests."""
    # Find a free port for the test server
    test_port = find_free_port()
    test_server_url = f"http://{TEST_SERVER_HOST}:{test_port}"

    config = uvicorn.Config(
        app=test_app,
        host=TEST_SERVER_HOST,
        port=test_port,
        log_level="critical",  # Suppress server logs during tests
    )
    server = uvicorn.Server(config)

    # Start server in background task
    server_task = asyncio.create_task(server.serve())

    # Wait for server to start
    await asyncio.sleep(1)

    yield test_server_url

    # Shutdown server
    server.should_exit = True
    await server_task


@pytest_asyncio.fixture(scope="session")
async def playwright():
    """Playwright instance for e2e tests."""
    async with async_playwright() as p:
        yield p


@pytest_asyncio.fixture(scope="session")
async def browser(playwright):
    """Browser instance (Chromium only for now)."""
    browser = await playwright.chromium.launch(headless=True)
    yield browser
    await browser.close()


@pytest_asyncio.fixture
async def browser_context(browser: Browser) -> AsyncGenerator[BrowserContext, None]:
    """Browser context for each test (clean state)."""
    context = await browser.new_context(viewport={"width": 1280, "height": 720}, locale="en-US")
    yield context
    await context.close()


@pytest_asyncio.fixture
async def page(browser_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """Page instance for each test."""
    page = await browser_context.new_page()
    yield page
    await page.close()


@pytest_asyncio.fixture
async def mobile_context(browser: Browser) -> AsyncGenerator[BrowserContext, None]:
    """Mobile browser context for responsive testing."""
    context = await browser.new_context(
        viewport={"width": 375, "height": 812},
        locale="en-US",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
    )
    yield context
    await context.close()


@pytest_asyncio.fixture
async def mobile_page(mobile_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """Mobile page instance for responsive testing."""
    page = await mobile_context.new_page()
    yield page
    await page.close()


@pytest_asyncio.fixture
async def seeded_database(test_database_url: str):
    """Database with seeded test data for e2e tests."""
    # Create session for the test database
    engine = create_async_engine(
        test_database_url,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSessionLocal() as session:
        # Create test subjects
        subjects_data = [
            {"name": "Computer Science", "description": "Computing and algorithms"},
            {"name": "Physics", "description": "Theoretical and experimental physics"},
            {"name": "Biology", "description": "Life sciences research"},
            {"name": "Mathematics", "description": "Pure and applied mathematics"},
        ]

        subjects = []
        for subject_data in subjects_data:
            subject = Subject(**subject_data)
            session.add(subject)
            subjects.append(subject)

        await session.commit()

        # Create test users
        users_data = [
            {
                "email": "testuser1@example.com",
                "display_name": "Test User One",
                "password": "testpass123",
            },
            {
                "email": "testuser2@example.com",
                "display_name": "Test User Two",
                "password": "testpass123",
            },
        ]

        users = []
        for user_data in users_data:
            user = User(
                email=user_data["email"],
                display_name=user_data["display_name"],
                password_hash=get_password_hash(user_data["password"]),
                email_verified=True,
            )
            session.add(user)
            users.append(user)

        await session.commit()

        yield {
            "subjects": subjects,
            "users": users,
            "user_credentials": [
                {"email": u["email"], "password": u["password"]} for u in users_data
            ],
        }

    # Cleanup engine
    await engine.dispose()


@pytest_asyncio.fixture
async def sample_html_content():
    """Sample HTML content for testing scroll uploads."""
    return """
    <html>
    <head>
        <title>Test Research Paper</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }
            h1 { color: #2c3e50; }
            h2 { color: #34495e; border-bottom: 2px solid #ecf0f1; }
            .abstract { background: #f8f9fa; padding: 1rem; border-left: 4px solid #3498db; }
            .equation { text-align: center; margin: 1rem 0; font-family: 'Times New Roman', serif; }
        </style>
    </head>
    <body>
        <h1>A Novel Approach to E2E Testing in Web Applications</h1>
        
        <div class="abstract">
            <strong>Abstract:</strong> This paper presents a comprehensive methodology for 
            implementing end-to-end testing in modern web applications using Playwright. 
            We demonstrate the effectiveness of our approach through real-world testing scenarios.
        </div>
        
        <h2>Introduction</h2>
        <p>End-to-end testing has become crucial for ensuring web application reliability. 
        Our research focuses on creating robust testing frameworks that simulate real user interactions.</p>
        
        <h2>Methodology</h2>
        <p>We implemented a testing suite using the following technologies:</p>
        <ul>
            <li>Playwright for browser automation</li>
            <li>Python for test scripting</li>
            <li>Headless browser execution</li>
        </ul>
        
        <div class="equation">
            <em>Testing_Coverage = (Tested_Scenarios / Total_Scenarios) × 100%</em>
        </div>
        
        <h2>Results</h2>
        <p>Our approach achieved 95% test coverage with minimal false positives. 
        The automated testing reduced manual testing time by 80%.</p>
        
        <h2>Conclusion</h2>
        <p>E2E testing with Playwright provides reliable validation of user workflows 
        and significantly improves application quality assurance.</p>
        
        <script>
            // Add some interactivity
            document.addEventListener('DOMContentLoaded', function() {
                console.log('Test paper loaded successfully');
                
                // Highlight equations on hover
                const equations = document.querySelectorAll('.equation');
                equations.forEach(eq => {
                    eq.addEventListener('mouseenter', () => {
                        eq.style.backgroundColor = '#fff3cd';
                    });
                    eq.addEventListener('mouseleave', () => {
                        eq.style.backgroundColor = 'transparent';
                    });
                });
            });
        </script>
    </body>
    </html>
    """


# Helper functions for e2e tests
class E2EHelpers:
    """Helper functions for e2e tests."""

    @staticmethod
    async def register_user(
        page: Page, server_url: str, email: str, password: str, display_name: str
    ):
        """Register a new user and return success status."""
        await page.goto(f"{server_url}/register")

        # Fill registration form
        await page.fill('input[name="email"]', email)
        await page.fill('input[name="display_name"]', display_name)
        await page.fill('input[name="password"]', password)
        await page.check('input[name="agree_terms"]')

        # Submit form
        await page.click('button[type="submit"]')

        # Wait for redirect or success message
        await page.wait_for_load_state("networkidle")

        # Check if registration succeeded (redirected to home)
        return page.url == f"{server_url}/"

    @staticmethod
    async def login_user(page: Page, server_url: str, email: str, password: str):
        """Login user and return success status."""
        await page.goto(f"{server_url}/login")

        # Fill login form
        await page.fill('input[name="email"]', email)
        await page.fill('input[name="password"]', password)

        # Submit form
        await page.click('button[type="submit"]')

        # Wait for redirect
        await page.wait_for_load_state("networkidle")

        # Check if login succeeded (redirected to home)
        return page.url == f"{server_url}/"

    @staticmethod
    async def upload_scroll(
        page: Page,
        server_url: str,
        title: str,
        authors: str,
        abstract: str,
        html_content: str,
        subject_name: str = "Computer Science",
        license: str = "cc-by-4.0",
    ):
        """Upload a scroll and return the scroll URL."""
        await page.goto(f"{server_url}/upload")

        # Fill upload form
        await page.fill('input[name="title"]', title)
        await page.fill('input[name="authors"]', authors)
        await page.fill('textarea[name="abstract"]', abstract)
        await page.fill('textarea[name="html_content"]', html_content)

        # Select subject
        await page.select_option('select[name="subject_id"]', label=subject_name)

        # Select license
        license_selector = f'input[name="license"][value="{license}"]'
        await page.check(license_selector)

        # Confirm rights
        await page.check('input[name="confirm_rights"]')

        # Submit form
        await page.click('button[type="submit"]')

        # Wait for success page
        await page.wait_for_load_state("networkidle")

        # Extract scroll URL from success page
        scroll_link = await page.locator('a:has-text("View Scroll")').get_attribute("href")
        return f"{server_url}{scroll_link}" if scroll_link else None

    @staticmethod
    async def delete_user_account(page: Page, server_url: str):
        """Delete user account via dashboard."""
        await page.goto(f"{server_url}/dashboard")

        # Click delete account button
        await page.click("#delete-account-btn")

        # Wait for modal
        await page.wait_for_selector("#delete-modal", state="visible")

        # Type confirmation text
        await page.fill("#confirm-delete-input", "DELETE MY ACCOUNT")

        # Click confirm delete
        await page.click("#confirm-delete-btn")

        # Wait for redirect to home with success message
        await page.wait_for_load_state("networkidle")

        return page.url == f"{server_url}/"


@pytest_asyncio.fixture
async def e2e_helpers():
    """E2E helper functions."""
    return E2EHelpers()
