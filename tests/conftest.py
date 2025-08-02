import asyncio
import os
import sys

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


@pytest_asyncio.fixture
async def client(test_db):
    """Create a test client with dependency override."""

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    # Use httpx AsyncClient with the app's ASGI callable
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
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
async def authenticated_client(client, test_user):
    """Get an authenticated client with session cookies."""
    login_data = {"email": test_user.email, "password": "testpassword"}

    # Login via form submission - should set session cookie
    response = await client.post("/login-form", data=login_data)

    # Verify login worked
    assert response.status_code == 200
    assert "session_id" in response.cookies

    # Return the client which now has session cookies
    return client


# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)
