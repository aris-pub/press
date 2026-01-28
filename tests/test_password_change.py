"""Tests for password change functionality (authenticated user changing password)."""

import pytest

from app.auth.utils import verify_password


# Page Load Tests


@pytest.mark.asyncio
async def test_change_password_page_requires_auth(client):
    """Test that change password page redirects unauthenticated users to login."""
    response = await client.get("/change-password")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_change_password_page_loads_for_authenticated_user(authenticated_client):
    """Test that authenticated users can access change password page."""
    response = await authenticated_client.get("/change-password")
    assert response.status_code == 200
    assert b"change" in response.content.lower() and b"password" in response.content.lower()


# Form Submission Tests


@pytest.mark.asyncio
async def test_change_password_with_valid_data(authenticated_client, test_user, test_db):
    """Test that valid password change works."""
    response = await authenticated_client.post(
        "/change-password-form",
        data={
            "current_password": "testpassword123",
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        },
    )

    assert response.status_code == 200
    assert b"success" in response.content.lower() or b"changed" in response.content.lower()

    # Verify password was changed
    await test_db.refresh(test_user)
    assert verify_password("NewSecurePass123!", test_user.password_hash)


@pytest.mark.asyncio
async def test_change_password_requires_auth(client, test_user, test_db):
    """Test that unauthenticated users cannot change password."""
    response = await client.post(
        "/change-password-form",
        data={
            "current_password": "testpassword123",
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        },
    )

    # Should redirect to login
    assert response.status_code == 302
    assert response.headers["location"] == "/login"

    # Password should not have changed
    await test_db.refresh(test_user)
    assert verify_password("testpassword123", test_user.password_hash)


# Validation Tests


@pytest.mark.asyncio
async def test_change_password_incorrect_current_password(authenticated_client, test_user, test_db):
    """Test that incorrect current password is rejected."""
    response = await authenticated_client.post(
        "/change-password-form",
        data={
            "current_password": "wrongpassword",
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        },
    )

    assert response.status_code == 422
    assert b"incorrect" in response.content.lower()

    # Password should not have changed
    await test_db.refresh(test_user)
    assert verify_password("testpassword123", test_user.password_hash)


@pytest.mark.asyncio
async def test_change_password_new_password_too_short(authenticated_client, test_user, test_db):
    """Test that new password must be at least 8 characters."""
    response = await authenticated_client.post(
        "/change-password-form",
        data={
            "current_password": "testpassword123",
            "new_password": "short1",
            "confirm_new_password": "short1",
        },
    )

    assert response.status_code == 422
    assert b"8 characters" in response.content.lower()

    # Password should not have changed
    await test_db.refresh(test_user)
    assert verify_password("testpassword123", test_user.password_hash)


@pytest.mark.asyncio
async def test_change_password_new_password_requires_number(
    authenticated_client, test_user, test_db
):
    """Test that new password must contain at least one number."""
    response = await authenticated_client.post(
        "/change-password-form",
        data={
            "current_password": "testpassword123",
            "new_password": "NoNumbersHere",
            "confirm_new_password": "NoNumbersHere",
        },
    )

    assert response.status_code == 422
    assert b"number" in response.content.lower()

    # Password should not have changed
    await test_db.refresh(test_user)
    assert verify_password("testpassword123", test_user.password_hash)


@pytest.mark.asyncio
async def test_change_password_new_passwords_must_match(
    authenticated_client, test_user, test_db
):
    """Test that new password and confirmation must match."""
    response = await authenticated_client.post(
        "/change-password-form",
        data={
            "current_password": "testpassword123",
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "DifferentPass123!",
        },
    )

    assert response.status_code == 422
    assert b"match" in response.content.lower()

    # Password should not have changed
    await test_db.refresh(test_user)
    assert verify_password("testpassword123", test_user.password_hash)


@pytest.mark.asyncio
async def test_change_password_new_must_differ_from_current(
    authenticated_client, test_user, test_db
):
    """Test that new password must be different from current password."""
    response = await authenticated_client.post(
        "/change-password-form",
        data={
            "current_password": "testpassword123",
            "new_password": "testpassword123",
            "confirm_new_password": "testpassword123",
        },
    )

    assert response.status_code == 422
    assert b"different" in response.content.lower()


# Security Tests


@pytest.mark.asyncio
async def test_change_password_rotates_session(authenticated_client, test_user, test_db):
    """Test that changing password rotates the session ID."""
    # Get initial session ID
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

    # Session should have been rotated
    assert new_session is not None
    assert new_session != initial_session


@pytest.mark.asyncio
async def test_old_password_invalid_after_change(authenticated_client, test_user, test_db):
    """Test that old password doesn't work after change."""
    # Change password
    await authenticated_client.post(
        "/change-password-form",
        data={
            "current_password": "testpassword123",
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        },
    )

    # Logout
    await authenticated_client.post("/logout")

    # Try to login with old password
    response = await authenticated_client.post(
        "/login-form", data={"email": test_user.email, "password": "testpassword123"}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_new_password_valid_after_change(authenticated_client, test_user, test_db):
    """Test that new password works after change."""
    # Change password
    await authenticated_client.post(
        "/change-password-form",
        data={
            "current_password": "testpassword123",
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        },
    )

    # Logout
    await authenticated_client.post("/logout")

    # Login with new password
    response = await authenticated_client.post(
        "/login-form", data={"email": test_user.email, "password": "NewSecurePass123!"}
    )

    assert response.status_code == 200
    assert "session_id" in response.cookies


@pytest.mark.asyncio
async def test_change_password_preserves_authentication(
    authenticated_client, test_user, test_db
):
    """Test that user remains authenticated after password change."""
    # Change password
    await authenticated_client.post(
        "/change-password-form",
        data={
            "current_password": "testpassword123",
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        },
    )

    # Should still be able to access authenticated pages
    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200


# Edge Cases


@pytest.mark.asyncio
async def test_change_password_multiple_times(authenticated_client, test_user, test_db):
    """Test that password can be changed multiple times."""
    # First change
    response1 = await authenticated_client.post(
        "/change-password-form",
        data={
            "current_password": "testpassword123",
            "new_password": "NewPass123!",
            "confirm_new_password": "NewPass123!",
        },
    )
    assert response1.status_code == 200

    # Manually update client cookies from response (session was rotated)
    if "session_id" in response1.cookies:
        authenticated_client.cookies.set("session_id", response1.cookies["session_id"])

    # Second change (with new session)
    response2 = await authenticated_client.post(
        "/change-password-form",
        data={
            "current_password": "NewPass123!",
            "new_password": "AnotherPass456!",
            "confirm_new_password": "AnotherPass456!",
        },
    )
    assert response2.status_code == 200

    # Verify final password works
    await authenticated_client.post("/logout")
    response3 = await authenticated_client.post(
        "/login-form", data={"email": test_user.email, "password": "AnotherPass456!"}
    )
    assert response3.status_code == 200


@pytest.mark.asyncio
async def test_change_password_with_special_characters(
    authenticated_client, test_user, test_db
):
    """Test that passwords with special characters are supported."""
    response = await authenticated_client.post(
        "/change-password-form",
        data={
            "current_password": "testpassword123",
            "new_password": "P@ssw0rd!#$%^&*()",
            "confirm_new_password": "P@ssw0rd!#$%^&*()",
        },
    )

    assert response.status_code == 200

    # Verify new password works
    await authenticated_client.post("/logout")
    login_response = await authenticated_client.post(
        "/login-form", data={"email": test_user.email, "password": "P@ssw0rd!#$%^&*()"}
    )
    assert login_response.status_code == 200
