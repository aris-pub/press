from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.auth.tokens import create_password_reset_token, hash_token
from app.models.token import Token


# Global mock to prevent any real email sending during tests
@pytest.fixture(autouse=True)
def mock_resend_emails():
    """Automatically mock Resend email sending for all tests in this module."""
    with patch("app.email.service.resend.Emails.send") as mock_send:
        yield mock_send


# Request Reset Tests


@pytest.mark.asyncio
async def test_forgot_password_page_loads(client):
    """Test that forgot password page loads successfully."""
    response = await client.get("/forgot-password")
    assert response.status_code == 200
    assert b"forgot" in response.content.lower() or b"reset" in response.content.lower()


@pytest.mark.asyncio
async def test_forgot_password_with_valid_email(client, test_db, test_user):
    """Test that valid email creates token and sends email."""
    with patch.dict(
        "os.environ",
        {
            "RESEND_API_KEY": "test_key",
            "FROM_EMAIL": "test@example.com",
            "BASE_URL": "http://localhost:8000",
        },
    ):
        response = await client.post("/forgot-password-form", data={"email": test_user.email})

        assert response.status_code == 200

        # Check token was created
        from sqlalchemy import select

        result = await test_db.execute(
            select(Token)
            .where(Token.user_id == test_user.id)
            .where(Token.token_type == "password_reset")
        )
        token = result.scalar_one_or_none()
        assert token is not None


@pytest.mark.asyncio
async def test_forgot_password_with_nonexistent_email(client, test_db):
    """Test that nonexistent email still returns success (security)."""
    with patch.dict(
        "os.environ",
        {
            "RESEND_API_KEY": "test_key",
            "FROM_EMAIL": "test@example.com",
            "BASE_URL": "http://localhost:8000",
        },
    ):
        response = await client.post(
            "/forgot-password-form", data={"email": "nonexistent@example.com"}
        )

        # Should return success to avoid revealing if email exists
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_creates_token_with_1hr_expiry(client, test_db, test_user):
    """Test that password reset tokens expire in 1 hour."""
    with patch.dict(
        "os.environ",
        {
            "RESEND_API_KEY": "test_key",
            "FROM_EMAIL": "test@example.com",
            "BASE_URL": "http://localhost:8000",
        },
    ):
        await client.post("/forgot-password-form", data={"email": test_user.email})

        # Check token expiry is ~1 hour from now
        from sqlalchemy import select

        result = await test_db.execute(
            select(Token)
            .where(Token.user_id == test_user.id)
            .where(Token.token_type == "password_reset")
        )
        token = result.scalar_one()

        # Allow 1 minute of tolerance for test execution time
        expected_expiry = datetime.now(UTC) + timedelta(hours=1)
        # Make token.expires_at timezone-aware if it's naive (SQLite returns naive datetimes)
        token_expiry = (
            token.expires_at.replace(tzinfo=UTC)
            if token.expires_at.tzinfo is None
            else token.expires_at
        )
        time_diff = abs((token_expiry - expected_expiry).total_seconds())
        assert time_diff < 60  # Within 1 minute


@pytest.mark.asyncio
async def test_forgot_password_invalidates_old_tokens(client, test_db, test_user):
    """Test that requesting password reset invalidates old tokens."""
    # Create initial token
    old_token = await create_password_reset_token(test_db, test_user.id)

    with patch.dict(
        "os.environ",
        {
            "RESEND_API_KEY": "test_key",
            "FROM_EMAIL": "test@example.com",
            "BASE_URL": "http://localhost:8000",
        },
    ):
        # Request new reset
        await client.post("/forgot-password-form", data={"email": test_user.email})

        # Old token should be marked as used
        from sqlalchemy import select

        result = await test_db.execute(select(Token).where(Token.token == hash_token(old_token)))
        token = result.scalar_one()
        assert token.used_at is not None


# Reset Password Tests


@pytest.mark.asyncio
async def test_reset_password_page_with_valid_token(client, test_db, test_user):
    """Test that reset password page shows form with valid token."""
    token = await create_password_reset_token(test_db, test_user.id)

    response = await client.get(f"/reset-password?token={token}")
    assert response.status_code == 200
    assert b"password" in response.content.lower()
    assert b"reset" in response.content.lower()


@pytest.mark.asyncio
async def test_reset_password_page_with_invalid_token(client, test_db):
    """Test that invalid token shows error."""
    response = await client.get("/reset-password?token=invalid_token_123")

    assert response.status_code == 200
    assert b"invalid" in response.content.lower() or b"expired" in response.content.lower()


@pytest.mark.asyncio
async def test_reset_password_page_with_expired_token(client, test_db, test_user):
    """Test that expired token shows error."""
    from app.auth.tokens import generate_token

    plain_token = generate_token()
    hashed = hash_token(plain_token)

    # Create expired token
    expired_token = Token(
        user_id=test_user.id,
        token=hashed,
        token_type="password_reset",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    test_db.add(expired_token)
    await test_db.commit()

    response = await client.get(f"/reset-password?token={plain_token}")

    assert response.status_code == 200
    assert b"invalid" in response.content.lower() or b"expired" in response.content.lower()


@pytest.mark.asyncio
async def test_reset_password_form_valid_submission(client, test_db, test_user):
    """Test that valid password reset works."""
    token = await create_password_reset_token(test_db, test_user.id)

    response = await client.post(
        "/reset-password-form",
        data={
            "token": token,
            "password": "NewSecurePass123!",
            "confirm_password": "NewSecurePass123!",
        },
    )

    assert response.status_code in [200, 302]  # Success or redirect

    # Verify password was changed
    from app.auth.utils import verify_password

    await test_db.refresh(test_user)
    assert verify_password("NewSecurePass123!", test_user.password_hash)


@pytest.mark.asyncio
async def test_reset_password_form_marks_token_used(client, test_db, test_user):
    """Test that password reset marks token as used."""
    token = await create_password_reset_token(test_db, test_user.id)

    await client.post(
        "/reset-password-form",
        data={
            "token": token,
            "password": "NewSecurePass123!",
            "confirm_password": "NewSecurePass123!",
        },
    )

    # Check token is marked as used
    from sqlalchemy import select

    result = await test_db.execute(
        select(Token)
        .where(Token.user_id == test_user.id)
        .where(Token.token_type == "password_reset")
    )
    token_obj = result.scalar_one()
    assert token_obj.used_at is not None


@pytest.mark.asyncio
async def test_reset_password_form_password_validation(client, test_db, test_user):
    """Test that password validation works."""
    token = await create_password_reset_token(test_db, test_user.id)

    # Test password too short
    response = await client.post(
        "/reset-password-form",
        data={"token": token, "password": "short", "confirm_password": "short"},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_reset_password_form_passwords_must_match(client, test_db, test_user):
    """Test that passwords must match."""
    token = await create_password_reset_token(test_db, test_user.id)

    response = await client.post(
        "/reset-password-form",
        data={
            "token": token,
            "password": "NewSecurePass123!",
            "confirm_password": "DifferentPass123!",
        },
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_reset_password_logs_user_in(client, test_db, test_user):
    """Test that password reset auto-logs user in."""
    token = await create_password_reset_token(test_db, test_user.id)

    await client.post(
        "/reset-password-form",
        data={
            "token": token,
            "password": "NewSecurePass123!",
            "confirm_password": "NewSecurePass123!",
        },
    )

    # Try to access dashboard (should work if logged in)
    response = await client.get("/dashboard")

    # Should not redirect to login
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_with_used_token(client, test_db, test_user):
    """Test that used tokens cannot be reused."""
    token = await create_password_reset_token(test_db, test_user.id)

    # Use token once
    await client.post(
        "/reset-password-form",
        data={
            "token": token,
            "password": "NewSecurePass123!",
            "confirm_password": "NewSecurePass123!",
        },
    )

    # Try to use it again
    response = await client.post(
        "/reset-password-form",
        data={
            "token": token,
            "password": "AnotherPass123!",
            "confirm_password": "AnotherPass123!",
        },
    )

    assert response.status_code in [400, 422]  # Should show error


# Security Tests


@pytest.mark.asyncio
async def test_old_password_invalid_after_reset(client, test_db, test_user):
    """Test that old password doesn't work after reset."""
    old_password = "testpassword"
    token = await create_password_reset_token(test_db, test_user.id)

    # Reset password
    await client.post(
        "/reset-password-form",
        data={
            "token": token,
            "password": "NewSecurePass123!",
            "confirm_password": "NewSecurePass123!",
        },
    )

    # Logout
    await client.post("/logout")

    # Try to login with old password
    response = await client.post(
        "/login-form", data={"email": test_user.email, "password": old_password}
    )

    assert response.status_code == 422  # Invalid credentials


@pytest.mark.asyncio
async def test_new_password_valid_after_reset(client, test_db, test_user):
    """Test that new password works after reset."""
    token = await create_password_reset_token(test_db, test_user.id)

    # Reset password
    await client.post(
        "/reset-password-form",
        data={
            "token": token,
            "password": "NewSecurePass123!",
            "confirm_password": "NewSecurePass123!",
        },
    )

    # Logout
    await client.post("/logout")

    # Login with new password
    response = await client.post(
        "/login-form", data={"email": test_user.email, "password": "NewSecurePass123!"}
    )

    assert response.status_code == 200
    assert "session_id" in response.cookies


@pytest.mark.asyncio
async def test_reset_token_single_use(client, test_db, test_user):
    """Test that reset tokens can only be used once."""
    token = await create_password_reset_token(test_db, test_user.id)

    # Use token
    response1 = await client.post(
        "/reset-password-form",
        data={"token": token, "password": "FirstPass123!", "confirm_password": "FirstPass123!"},
    )
    assert response1.status_code in [200, 302]

    # Try to use same token again
    response2 = await client.post(
        "/reset-password-form",
        data={"token": token, "password": "SecondPass123!", "confirm_password": "SecondPass123!"},
    )
    assert response2.status_code in [400, 422]
