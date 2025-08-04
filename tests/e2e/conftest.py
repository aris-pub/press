"""E2E test configuration and fixtures for Scroll Press.

IMPORTANT: Due to pytest-asyncio event loop conflicts, DO NOT use the session-scoped
Playwright fixtures (browser, browser_context, page) in e2e tests. They cause deadlocks.

Instead, use async with async_playwright() directly in test functions:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # ... test code ...
        await browser.close()

The session fixtures below are kept for reference but should be avoided.
"""

import asyncio
import hashlib
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
from app.models.scroll import Scroll, Subject
from app.models.user import User

# Import moved inside function to avoid startup issues

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

    # Import FastAPI app after database setup to avoid startup issues
    from main import app as fastapi_app

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
async def test_server(test_app: FastAPI, seeded_database):
    """Start test server for e2e tests with seeded data."""
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
    await asyncio.sleep(2)  # Simple wait instead of health check

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


@pytest_asyncio.fixture(scope="session")
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

        # Refresh subjects and users to get their IDs
        for subject in subjects:
            await session.refresh(subject)
        for user in users:
            await session.refresh(user)

        # Create test scrolls
        scrolls_data = [
            {
                "title": "Machine Learning in Browser Testing",
                "authors": "Test User One",
                "abstract": "This paper explores the application of machine learning techniques in automated browser testing, focusing on element detection and user interaction prediction.",
                "keywords": ["machine learning", "testing", "automation", "browser"],
                "html_content": "<h1>ML in Browser Testing</h1><p>This scroll demonstrates computer science content filtering.</p><script>console.log('CS scroll loaded');</script>",
                "user_id": users[0].id,
                "subject_id": next(s.id for s in subjects if s.name == "Computer Science"),
                "license": "cc-by-4.0",
            },
            {
                "title": "Quantum Mechanics and Modern Physics",
                "authors": "Test User Two",
                "abstract": "An exploration of quantum mechanical principles and their applications in modern physics research.",
                "keywords": ["quantum", "physics", "mechanics", "research"],
                "html_content": "<h1>Quantum Mechanics</h1><p>This scroll demonstrates physics content filtering.</p><script>console.log('Physics scroll loaded');</script>",
                "user_id": users[1].id,
                "subject_id": next(s.id for s in subjects if s.name == "Physics"),
                "license": "cc-by-4.0",
            },
            {
                "title": "Biological Systems Analysis",
                "authors": "Test User One",
                "abstract": "A comprehensive analysis of complex biological systems using computational methods.",
                "keywords": ["biology", "systems", "analysis", "computational"],
                "html_content": "<h1>Biological Systems</h1><p>This scroll demonstrates biology content filtering.</p><script>console.log('Biology scroll loaded');</script>",
                "user_id": users[0].id,
                "subject_id": next(s.id for s in subjects if s.name == "Biology"),
                "license": "arr",
            },
            {
                "title": "Mathematical Proofs in Computer Science",
                "authors": "Test User Two",
                "abstract": "Exploring the mathematical foundations underlying computer science algorithms and data structures.",
                "keywords": ["mathematics", "proofs", "algorithms", "computer science"],
                "html_content": "<h1>Mathematical Proofs</h1><p>This scroll demonstrates math/CS content filtering.</p><script>console.log('Math scroll loaded');</script>",
                "user_id": users[1].id,
                "subject_id": next(s.id for s in subjects if s.name == "Mathematics"),
                "license": "cc-by-4.0",
            },
        ]

        scrolls = []
        for scroll_data in scrolls_data:
            # Generate content-addressable hash
            content_hash = hashlib.sha256(scroll_data["html_content"].encode()).hexdigest()
            url_hash = content_hash[:12]  # Use first 12 characters for URL

            scroll = Scroll(
                title=scroll_data["title"],
                authors=scroll_data["authors"],
                abstract=scroll_data["abstract"],
                keywords=scroll_data["keywords"],
                html_content=scroll_data["html_content"],
                content_hash=content_hash,
                url_hash=url_hash,
                license=scroll_data["license"],
                user_id=scroll_data["user_id"],
                subject_id=scroll_data["subject_id"],
                status="published",  # Make sure scrolls are published so they show on homepage
                version=1,
            )
            session.add(scroll)
            scrolls.append(scroll)

        await session.commit()

        yield {
            "subjects": subjects,
            "users": users,
            "scrolls": scrolls,
            "user_credentials": [
                {"email": u["email"], "password": u["password"]} for u in users_data
            ],
        }

    # Cleanup engine
    await engine.dispose()


@pytest_asyncio.fixture
async def sample_html_content():
    """Sample HTML content for testing scroll uploads - generates unique content per test."""
    import random
    import uuid

    # Generate unique content for each test to avoid database constraint violations
    test_id = uuid.uuid4().hex[:8]
    version = random.randint(1, 999)

    # Vary the research focus and methodology for each test
    research_topics = [
        ("Machine Learning Applications", "deep neural networks and transformer architectures"),
        ("Distributed Systems Design", "microservices and event-driven architectures"),
        ("Human-Computer Interaction", "user experience patterns and accessibility standards"),
        ("Data Science Methodologies", "statistical analysis and predictive modeling"),
        ("Cybersecurity Frameworks", "threat detection and vulnerability assessment"),
        ("Software Engineering Practices", "agile development and continuous integration"),
    ]

    topic, focus = random.choice(research_topics)

    return f"""
    <html>
    <head>
        <title>Research Paper v{version} - {topic}</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; line-height: 1.6; }}
            h1 {{ color: #2c3e50; font-family: Arial, sans-serif; }}
            h2 {{ color: #34495e; border-bottom: 2px solid #ecf0f1; font-family: Arial, sans-serif; }}
            .abstract {{ background: #f8f9fa; padding: 1rem; border-left: 4px solid #3498db; font-style: italic; }}
            .equation {{ text-align: center; margin: 1rem 0; font-family: Arial, sans-serif; background: #f5f5f5; padding: 1rem; }}
            .unique-id {{ font-size: 0.8em; color: #666; margin-top: 2rem; }}
        </style>
    </head>
    <body>
        <h1>A Novel Approach to {topic} in Modern Applications</h1>
        
        <div class="abstract">
            <strong>Abstract:</strong> This paper presents a comprehensive methodology for 
            implementing {focus} in contemporary software systems. 
            We demonstrate the effectiveness of our approach through rigorous testing and validation.
            Research ID: {test_id}
        </div>
        
        <h2>Introduction</h2>
        <p>The field of {topic.lower()} has evolved significantly in recent years. 
        Our research addresses critical challenges in {focus} and proposes innovative solutions.</p>
        
        <h2>Methodology</h2>
        <p>We implemented a comprehensive testing framework incorporating:</p>
        <ul>
            <li>Automated testing with Playwright v{version}</li>
            <li>Python-based test orchestration</li>
            <li>Cross-browser validation protocols</li>
            <li>Performance benchmarking suite</li>
        </ul>
        
        <div class="equation">
            <em>Effectiveness_Score = (Successful_Cases / Total_Cases) × {90 + random.randint(1, 10)}%</em>
        </div>
        
        <h2>Results</h2>
        <p>Our methodology achieved {85 + random.randint(1, 15)}% accuracy with minimal false positives. 
        The automated approach reduced manual intervention by {70 + random.randint(1, 25)}%.</p>
        
        <h2>Conclusion</h2>
        <p>The proposed framework for {topic.lower()} provides robust validation of system behaviors 
        and significantly enhances development workflow efficiency.</p>
        
        <div class="unique-id">
            <p><strong>Document ID:</strong> {test_id} | <strong>Version:</strong> {version}</p>
        </div>
        
        <script>
            // Add unique interactivity per test
            document.addEventListener('DOMContentLoaded', function() {{
                console.log('Research paper {test_id} loaded successfully');
                
                // Dynamic equation highlighting
                const equations = document.querySelectorAll('.equation');
                equations.forEach(eq => {{
                    eq.addEventListener('mouseenter', () => {{
                        eq.style.backgroundColor = '#fff3cd';
                        eq.style.transform = 'scale(1.02)';
                    }});
                    eq.addEventListener('mouseleave', () => {{
                        eq.style.backgroundColor = '#f5f5f5';
                        eq.style.transform = 'scale(1)';
                    }});
                }});
                
                // Unique test identifier
                console.log('Test version: {version}');
            }});
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
