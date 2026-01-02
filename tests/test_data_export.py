"""Tests for GDPR data export endpoint."""

import pytest
from httpx import AsyncClient
from app.models.scroll import Scroll
from app.storage.content_processing import generate_permanent_url


@pytest.mark.asyncio
async def test_export_data_requires_authentication(client: AsyncClient):
    """Test that data export requires authentication."""
    response = await client.get("/user/export-data")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_data_returns_user_data(client: AsyncClient, test_db, test_user, test_subject):
    """Test that authenticated user can export their data."""
    from app.auth.session import create_session

    # Create session for test user
    session_id = await create_session(test_db, test_user.id)

    # Create a scroll for the user
    url_hash, content_hash, _ = await generate_permanent_url("<html><body>Test Export</body></html>")
    scroll = Scroll(
        user_id=test_user.id,
        subject_id=test_subject.id,
        title="Test Export Scroll",
        authors="Test Author",
        abstract="Test abstract for export",
        html_content="<html><body>Test Export</body></html>",
        license="cc-by-4.0",
        status="published",
        url_hash=url_hash,
        content_hash=content_hash,
    )
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)

    # Make request with session cookie
    response = await client.get(
        "/user/export-data",
        cookies={"session_id": session_id}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    data = response.json()

    # Check user data is present
    assert "user" in data
    assert data["user"]["email"] == test_user.email
    assert data["user"]["display_name"] == test_user.display_name
    assert data["user"]["email_verified"] == test_user.email_verified
    assert "created_at" in data["user"]

    # Check scrolls data is present
    assert "scrolls" in data
    assert len(data["scrolls"]) == 1
    assert data["scrolls"][0]["title"] == "Test Export Scroll"
    assert data["scrolls"][0]["authors"] == "Test Author"
    assert data["scrolls"][0]["status"] == "published"
    assert data["scrolls"][0]["url_hash"] == url_hash

    # Check sessions data is present
    assert "sessions" in data
    assert len(data["sessions"]) >= 1
    assert any(s["session_id"] == session_id for s in data["sessions"])


@pytest.mark.asyncio
async def test_export_data_only_returns_own_data(client: AsyncClient, test_db, test_user, test_subject):
    """Test that users can only export their own data, not other users'."""
    from app.auth.session import create_session
    from app.models.user import User
    from app.auth.utils import get_password_hash

    # Create another user
    other_user = User(
        email="other@example.com",
        password_hash=get_password_hash("password123"),
        display_name="Other User",
        email_verified=True,
    )
    test_db.add(other_user)
    await test_db.commit()
    await test_db.refresh(other_user)

    # Create scroll for other user
    url_hash, content_hash, _ = await generate_permanent_url("<html><body>Other Content</body></html>")
    other_scroll = Scroll(
        user_id=other_user.id,
        subject_id=test_subject.id,
        title="Other User's Scroll",
        authors="Other Author",
        abstract="Other abstract",
        html_content="<html><body>Other Content</body></html>",
        license="cc-by-4.0",
        status="published",
        url_hash=url_hash,
        content_hash=content_hash,
    )
    test_db.add(other_scroll)
    await test_db.commit()

    # Login as test_user
    session_id = await create_session(test_db, test_user.id)

    # Export data
    response = await client.get(
        "/user/export-data",
        cookies={"session_id": session_id}
    )

    assert response.status_code == 200
    data = response.json()

    # Should only see test_user's data
    assert data["user"]["email"] == test_user.email
    assert data["user"]["email"] != other_user.email

    # Should not see other user's scrolls
    assert len(data["scrolls"]) == 0
    assert not any(s["title"] == "Other User's Scroll" for s in data["scrolls"])


@pytest.mark.asyncio
async def test_export_data_includes_all_scroll_fields(client: AsyncClient, test_db, test_user, test_subject):
    """Test that all relevant scroll fields are included in export."""
    from app.auth.session import create_session

    session_id = await create_session(test_db, test_user.id)

    # Create scroll with all fields populated
    url_hash, content_hash, _ = await generate_permanent_url("<html><body>Complete</body></html>")
    scroll = Scroll(
        user_id=test_user.id,
        subject_id=test_subject.id,
        title="Complete Scroll",
        authors="Author One, Author Two",
        abstract="Full abstract with details",
        keywords=["keyword1", "keyword2", "keyword3"],
        html_content="<html><body>Complete</body></html>",
        license="arr",
        status="draft",
        url_hash=url_hash,
        content_hash=content_hash,
    )
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)

    response = await client.get(
        "/user/export-data",
        cookies={"session_id": session_id}
    )

    data = response.json()
    scroll_data = data["scrolls"][0]

    # Verify all important fields are present
    assert scroll_data["title"] == "Complete Scroll"
    assert scroll_data["authors"] == "Author One, Author Two"
    assert scroll_data["abstract"] == "Full abstract with details"
    assert scroll_data["keywords"] == ["keyword1", "keyword2", "keyword3"]
    assert scroll_data["license"] == "arr"
    assert scroll_data["status"] == "draft"
    assert scroll_data["url_hash"] == url_hash
    assert scroll_data["content_hash"] == content_hash
    assert "created_at" in scroll_data
    assert "updated_at" in scroll_data
