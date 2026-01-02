"""Tests for CSRF protection."""

import pytest
from httpx import AsyncClient

from app.auth.session import create_session


@pytest.mark.asyncio
async def test_csrf_token_generated_on_session_creation(test_db, test_user):
    """Test that CSRF token is automatically generated when session is created."""
    from app.auth.csrf import get_csrf_token

    session_id = await create_session(test_db, test_user.id)

    csrf_token = await get_csrf_token(session_id)
    assert csrf_token is not None
    assert len(csrf_token) == 64  # 32 bytes in hex = 64 chars


@pytest.mark.asyncio
async def test_csrf_token_is_unique_per_session(test_db, test_user):
    """Test that each session gets a unique CSRF token."""
    from app.auth.csrf import get_csrf_token
    import uuid

    session_id_1 = await create_session(test_db, test_user.id)
    session_id_2 = await create_session(test_db, uuid.uuid4())

    token_1 = await get_csrf_token(session_id_1)
    token_2 = await get_csrf_token(session_id_2)

    assert token_1 != token_2


@pytest.mark.asyncio
async def test_csrf_token_validates_correctly(test_db, test_user):
    """Test that valid CSRF token passes validation."""
    from app.auth.csrf import get_csrf_token, validate_csrf_token

    session_id = await create_session(test_db, test_user.id)
    csrf_token = await get_csrf_token(session_id)

    is_valid = await validate_csrf_token(session_id, csrf_token)
    assert is_valid is True


@pytest.mark.asyncio
async def test_csrf_token_rejects_invalid_token(test_db, test_user):
    """Test that invalid CSRF token fails validation."""
    from app.auth.csrf import validate_csrf_token

    session_id = await create_session(test_db, test_user.id)

    is_valid = await validate_csrf_token(session_id, "invalid_token_123")
    assert is_valid is False


@pytest.mark.asyncio
async def test_csrf_token_rejects_token_from_different_session(test_db, test_user):
    """Test that CSRF token from one session doesn't work for another."""
    from app.auth.csrf import get_csrf_token, validate_csrf_token
    import uuid

    session_id_1 = await create_session(test_db, test_user.id)
    session_id_2 = await create_session(test_db, uuid.uuid4())

    token_1 = await get_csrf_token(session_id_1)

    # Try to use session 1's token for session 2
    is_valid = await validate_csrf_token(session_id_2, token_1)
    assert is_valid is False


@pytest.mark.asyncio
async def test_csrf_token_rejects_missing_token(test_db, test_user):
    """Test that missing CSRF token fails validation."""
    from app.auth.csrf import validate_csrf_token

    session_id = await create_session(test_db, test_user.id)

    is_valid = await validate_csrf_token(session_id, None)
    assert is_valid is False


# Form submission tests


@pytest.mark.asyncio
async def test_login_form_exempt_from_csrf(client: AsyncClient):
    """Test that login form is exempt from CSRF (uses rate limiting instead)."""
    # Login without CSRF token should work (form is exempt)
    # It will fail with 422 for invalid credentials, not 403 for CSRF
    response = await client.post(
        "/login-form",
        data={
            "email": "nonexistent@example.com",
            "password": "wrongpassword",
        },
    )

    # Should get validation error, not CSRF error
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_form_exempt_from_csrf(client: AsyncClient):
    """Test that register form is exempt from CSRF (uses rate limiting instead)."""
    # Register without CSRF token should work (form is exempt)
    response = await client.post(
        "/register-form",
        data={
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
            "display_name": "New User",
            "agree_terms": "true",
        },
    )

    # Should succeed (200) or fail with validation error, not CSRF error (403)
    assert response.status_code in [200, 422]


@pytest.mark.asyncio
async def test_login_with_valid_csrf_token(client: AsyncClient, test_user, test_db):
    """Test that login succeeds with valid CSRF token."""
    # First, visit the login page to get a session cookie
    login_page = await client.get("/login")
    assert login_page.status_code == 200

    # Get CSRF token - either from existing session or create one
    from app.auth.csrf import get_csrf_token

    session_id = client.cookies.get("session_id")

    # If there's no session from visiting the page, create a temporary one for test
    if not session_id:
        # Create a session with the test user
        session_id = await create_session(test_db, test_user.id)
        client.cookies.set("session_id", session_id)

    csrf_token = await get_csrf_token(session_id)

    # Now login with CSRF token
    response = await client.post(
        "/login-form",
        data={
            "email": test_user.email,
            "password": "testpassword",
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_form_requires_csrf_token(authenticated_client: AsyncClient, test_user, test_db):
    """Test that upload form requires CSRF token."""
    # Mark user as verified
    test_user.email_verified = True
    await test_db.commit()

    response = await authenticated_client.post(
        "/upload-form",
        data={
            "title": "Test Scroll",
            "authors": "Test Author",
            "abstract": "Test abstract",
            # Missing CSRF token
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_account_requires_csrf_token(authenticated_client: AsyncClient):
    """Test that account deletion requires CSRF token."""
    # DELETE request without X-CSRF-Token header should fail
    response = await authenticated_client.delete("/account")

    assert response.status_code == 403
