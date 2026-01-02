import asyncio
import os
import sys
from unittest.mock import patch

import httpx
from httpx import AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Set testing environment variable
os.environ["TESTING"] = "1"

# Add the project root to the path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, get_db
from app.models.user import User
from main import app

# Test database URL - use PostgreSQL in CI, SQLite locally
# Check if we're in CI by looking for CI environment variable
if os.getenv("CI") and os.getenv("DATABASE_URL"):
    TEST_DATABASE_URL = os.getenv("DATABASE_URL")
else:
    TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db():
    """Create a test database session."""
    # Different connection args for SQLite vs PostgreSQL
    if "sqlite" in TEST_DATABASE_URL:
        connect_args = {"check_same_thread": False}
        poolclass = StaticPool
    else:
        connect_args = {}
        poolclass = None

    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=poolclass,
        connect_args=connect_args,
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    session = TestSessionLocal()
    try:
        yield session
    finally:
        await session.close()
        # Clean up
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


class CSRFClient(AsyncClient):
    """AsyncClient that automatically injects CSRF tokens into form submissions."""

    async def post(self, url, **kwargs):
        """Override post to automatically inject CSRF token if data/form present."""
        return await self._add_csrf_and_send("POST", url, **kwargs)

    async def put(self, url, **kwargs):
        """Override put to automatically inject CSRF token if data/form present."""
        return await self._add_csrf_and_send("PUT", url, **kwargs)

    async def patch(self, url, **kwargs):
        """Override patch to automatically inject CSRF token if data/form present."""
        return await self._add_csrf_and_send("PATCH", url, **kwargs)

    async def delete(self, url, **kwargs):
        """Override delete to automatically inject CSRF token header."""
        return await self._add_csrf_and_send("DELETE", url, **kwargs)

    async def _add_csrf_and_send(self, method, url, **kwargs):
        """Add CSRF token to request and send."""
        from app.auth.csrf import get_csrf_token

        # Get session ID from cookies (handle multiple cookies with same name)
        session_id = None
        try:
            session_id = self.cookies.get("session_id")
        except Exception:
            # If multiple cookies with same name, get the most recent one
            for cookie in self.cookies.jar:
                if cookie.name == "session_id":
                    session_id = cookie.value
                    break

        if session_id:
            # Get CSRF token for this session
            csrf_token = await get_csrf_token(session_id)

            if method in {"POST", "PUT", "PATCH"}:
                # Add CSRF token to data or create minimal form
                if "data" in kwargs:
                    if isinstance(kwargs["data"], dict):
                        kwargs["data"] = {**kwargs["data"], "csrf_token": csrf_token}
                    # If data is already form-encoded, user must handle csrf_token manually
                elif "files" in kwargs:
                    # File upload - add CSRF token as regular form field
                    # Create data dict with just the token (files are separate)
                    kwargs["data"] = {"csrf_token": csrf_token}
                else:
                    # No data or files, create minimal form with just CSRF token
                    kwargs["data"] = {"csrf_token": csrf_token}
            elif method == "DELETE":
                # Add to headers for DELETE
                if "headers" not in kwargs:
                    kwargs["headers"] = {}
                kwargs["headers"]["X-CSRF-Token"] = csrf_token

        # Call parent method
        return await super().request(method, url, **kwargs)


@pytest_asyncio.fixture
async def client(test_db):
    """Create a test client with dependency override and automatic CSRF injection."""

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    # Use CSRFClient which automatically injects CSRF tokens
    async with CSRFClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://test",
        cookies=httpx.Cookies(),  # Enable cookie jar for session persistence
    ) as ac:
        yield ac

    # Clean up
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_subject(test_db):
    """Create a test subject in the database."""
    from app.models.scroll import Subject

    subject = Subject(
        name="Computer Science",
        description="Computing, algorithms, and software engineering",
    )

    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    return subject


async def create_content_addressable_scroll(
    test_db,
    test_user,
    test_subject,
    title: str = "Test Scroll",
    authors: str = "Test Author",
    abstract: str = "Test abstract",
    html_content: str = "<h1>Test Content</h1>",
    license: str = "cc-by-4.0",
    keywords: list = None,
):
    """Helper function to create a scroll with proper content-addressable storage."""
    from app.models.scroll import Scroll
    from app.storage.content_processing import generate_permanent_url

    if keywords is None:
        keywords = []

    # Generate content-addressable storage fields
    url_hash, content_hash, tar_data = await generate_permanent_url(html_content)

    scroll = Scroll(
        title=title,
        authors=authors,
        abstract=abstract,
        keywords=keywords,
        html_content=html_content,
        license=license,
        content_hash=content_hash,
        url_hash=url_hash,
        status="draft",
        user_id=test_user.id,
        subject_id=test_subject.id,
    )

    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)

    return scroll


@pytest_asyncio.fixture
async def test_user(test_db):
    """Create a test user in the database."""
    from app.auth.utils import get_password_hash

    user = User(
        email="test@example.com",
        password_hash=get_password_hash("testpassword"),
        display_name="Test User",
        email_verified=True,
    )

    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)

    return user


@pytest_asyncio.fixture
async def authenticated_client(client, test_user, test_db):
    """Get an authenticated client with session cookies.

    Creates a session directly instead of going through login flow.
    CSRF token is automatically generated when session is created.
    """
    from app.auth.session import create_session

    # Create a session directly (CSRF token auto-generated)
    session_id = await create_session(test_db, test_user.id)
    client.cookies.set("session_id", session_id)

    # Return the client with session cookie
    # CSRFClient will automatically inject tokens for POST/PUT/PATCH/DELETE
    return client


# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(autouse=True, scope="function")
def mock_resend_globally():
    """CRITICAL: Mock Resend email sending for ALL tests to prevent sending real emails.

    This fixture automatically applies to every test function to prevent accidentally
    burning through Resend quota during test runs.
    """
    with patch("app.emails.service.resend.Emails.send") as mock_send:
        # Make the mock return a successful response
        mock_send.return_value = {"id": "test-email-id"}
        yield mock_send


def pytest_configure(config):
    """Configure pytest with environment-specific settings."""
    # Set different event loop scopes based on environment
    # CI needs function scope to avoid event loop conflicts with PostgreSQL
    # Local can use session scope for better performance with SQLite
    if os.getenv("CI") and os.getenv("DATABASE_URL"):
        # CI environment - use function scope to avoid event loop conflicts
        config._inicache["asyncio_default_test_loop_scope"] = "function"
    else:
        # Local environment - use session scope for better performance
        config._inicache["asyncio_default_test_loop_scope"] = "session"
