"""Tests for session rotation on authentication state changes."""

from httpx import AsyncClient
import pytest


@pytest.mark.asyncio
async def test_login_rotates_session_id(client: AsyncClient, test_user):
    """Test that session ID changes after successful login."""
    # Visit a page to get an initial session (if any)
    await client.get("/login")
    initial_session = client.cookies.get("session_id")

    # Login
    response = await client.post(
        "/login-form",
        data={
            "email": test_user.email,
            "password": "testpassword123",
        },
    )

    assert response.status_code == 200
    new_session = client.cookies.get("session_id")

    # Session ID should change after login
    assert new_session is not None
    assert new_session != initial_session


@pytest.mark.asyncio
async def test_password_change_rotates_session(
    authenticated_client: AsyncClient, test_user, test_db
):
    """Test that session ID changes after password change."""
    # Get initial session (handle multiple cookies)
    initial_session = None
    try:
        initial_session = authenticated_client.cookies.get("session_id")
    except Exception:
        for cookie in authenticated_client.cookies.jar:
            if cookie.name == "session_id":
                initial_session = cookie.value
                break

    assert initial_session is not None

    # Change password
    response = await authenticated_client.post(
        "/change-password-form",
        data={
            "current_password": "testpassword123",
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        },
    )

    assert response.status_code == 200

    # Get new session ID from response cookies
    new_session = response.cookies.get("session_id")

    # Should get a new session ID
    assert new_session is not None
    assert new_session != initial_session


@pytest.mark.asyncio
async def test_email_verification_rotates_session(client: AsyncClient, test_user, test_db):
    """Test that session ID changes after email verification."""
    from app.auth.tokens import create_verification_token

    # Mark user as unverified
    test_user.email_verified = False
    await test_db.commit()

    # Login as unverified user
    await client.post(
        "/login-form",
        data={
            "email": test_user.email,
            "password": "testpassword123",
        },
    )

    initial_session = client.cookies.get("session_id")

    # Create verification token
    token = await create_verification_token(test_db, test_user.id)

    # Verify email
    response = await client.get(f"/verify-email?token={token}")

    assert response.status_code == 200

    # Session should be rotated
    new_session = client.cookies.get("session_id")
    assert new_session is not None
    assert new_session != initial_session


@pytest.mark.asyncio
async def test_rotated_session_preserves_user_data(client: AsyncClient, test_user):
    """Test that session rotation preserves user authentication."""
    # Login
    await client.post(
        "/login-form",
        data={
            "email": test_user.email,
            "password": "testpassword123",
        },
    )

    # Verify we can access authenticated page
    response = await client.get("/dashboard")
    assert response.status_code == 200

    # User should still be authenticated after session rotation
    # (The login itself rotates the session)


# Unit tests for get_session()


def test_get_session_creates_new_session_dict():
    """Test that get_session() creates a new dict for new session IDs."""
    from app.auth.session import get_session

    session_id = "test_session_123"
    session = get_session(session_id)

    assert session is not None
    assert isinstance(session, dict)
    assert len(session) == 0


def test_get_session_returns_same_dict_for_same_id():
    """Test that get_session() returns the same dict for the same session ID."""
    from app.auth.session import get_session

    session_id = "test_session_456"
    session1 = get_session(session_id)
    session1["test_key"] = "test_value"

    session2 = get_session(session_id)

    assert session2 is session1
    assert session2["test_key"] == "test_value"


def test_get_session_isolates_different_sessions():
    """Test that different session IDs get different dicts."""
    from app.auth.session import get_session

    session_a = get_session("session_a")
    session_b = get_session("session_b")

    session_a["data"] = "session_a_data"
    session_b["data"] = "session_b_data"

    assert session_a["data"] == "session_a_data"
    assert session_b["data"] == "session_b_data"
    assert session_a is not session_b


def test_get_session_stores_complex_data():
    """Test that get_session() can store complex nested data structures."""
    from app.auth.session import get_session

    session_id = "test_complex_session"
    session = get_session(session_id)

    session["form_data"] = {
        "title": "Test Title",
        "authors": "Test Author",
        "nested": {"key": "value", "list": [1, 2, 3]},
    }

    retrieved_session = get_session(session_id)
    assert retrieved_session["form_data"]["title"] == "Test Title"
    assert retrieved_session["form_data"]["nested"]["list"] == [1, 2, 3]
