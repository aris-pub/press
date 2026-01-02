"""Tests for session rotation on authentication state changes."""

import pytest
from httpx import AsyncClient

from app.auth.session import create_session


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
            "password": "testpassword",
        },
    )

    assert response.status_code == 200
    new_session = client.cookies.get("session_id")

    # Session ID should change after login
    assert new_session is not None
    assert new_session != initial_session


@pytest.mark.asyncio
async def test_password_change_rotates_session(authenticated_client: AsyncClient, test_user, test_db):
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

    # Change password (when we implement this feature)
    # For now, test the underlying rotate_session function
    from app.auth.session import rotate_session

    new_session_id = await rotate_session(test_db, initial_session)

    # Should get a new session ID
    assert new_session_id is not None
    assert new_session_id != initial_session


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
            "password": "testpassword",
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
            "password": "testpassword",
        },
    )

    # Verify we can access authenticated page
    response = await client.get("/dashboard")
    assert response.status_code == 200

    # User should still be authenticated after session rotation
    # (The login itself rotates the session)
