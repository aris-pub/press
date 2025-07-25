import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_simple_client(client):
    """Simple test to check if client fixture works."""
    response = await client.get("/")
    assert response.status_code == 200

async def test_simple_db(test_db):
    """Simple test to check if test_db fixture works."""
    assert test_db is not None