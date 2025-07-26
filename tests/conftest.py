import asyncio
import os
import sys

import httpx
from httpx import AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Add the project root to the path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, get_db
from app.models.user import User
from main import app

# Test database URL (in-memory SQLite)
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
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False
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
    async with AsyncClient(
        transport=httpx.ASGITransport(app=app), 
        base_url="http://test"
    ) as ac:
        yield ac
    
    # Clean up
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def test_user(test_db):
    """Create a test user in the database."""
    from app.auth.utils import get_password_hash
    
    user = User(
        email="test@example.com",
        password_hash=get_password_hash("testpassword"),
        display_name="Test User",
        email_verified=True
    )
    
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    
    return user

@pytest_asyncio.fixture
async def auth_headers(client, test_user):
    """Get authentication headers for a test user."""
    login_data = {
        "email": test_user.email,
        "password": "testpassword"
    }
    
    response = await client.post("/auth/login", json=login_data)
    tokens = response.json()
    
    return {"Authorization": f"Bearer {tokens['access_token']}"}

# Configure pytest-asyncio  
pytest_plugins = ("pytest_asyncio",)