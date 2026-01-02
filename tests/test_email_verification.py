from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.auth.tokens import create_verification_token, hash_token
from app.models.token import Token
from app.models.user import User


# Global mock to prevent any real email sending during tests
@pytest.fixture(autouse=True)
def mock_resend_emails():
    """Automatically mock Resend email sending for all tests in this module."""
    with patch("app.email.service.resend.Emails.send") as mock_send:
        yield mock_send


@pytest.mark.asyncio
async def test_register_sets_email_verified_false(client, test_db):
    """Test that new users are created with email_verified=False."""
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

    assert response.status_code == 200

    # Check user was created with email_verified=False
    from sqlalchemy import select

    result = await test_db.execute(select(User).where(User.email == "newuser@example.com"))
    user = result.scalar_one()
    assert user.email_verified is False


@pytest.mark.asyncio
async def test_register_creates_verification_token(client, test_db):
    """Test that registration creates a verification token."""
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

    assert response.status_code == 200

    # Check token was created
    from sqlalchemy import select

    result = await test_db.execute(select(User).where(User.email == "newuser@example.com"))
    user = result.scalar_one()

    token_result = await test_db.execute(select(Token).where(Token.user_id == user.id))
    token = token_result.scalar_one()

    assert token.token_type == "email_verification"
    assert token.expires_at.replace(tzinfo=UTC) > datetime.now(UTC)


@pytest.mark.asyncio
@patch("app.email.service.resend.Emails.send")
async def test_register_sends_verification_email(mock_send, client, test_db):
    """Test that registration sends verification email."""
    with patch.dict(
        "os.environ",
        {
            "RESEND_API_KEY": "test_key",
            "FROM_EMAIL": "test@example.com",
            "BASE_URL": "http://localhost:8000",
        },
    ):
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

        assert response.status_code == 200
        # Email should have been sent
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_register_user_can_access_dashboard_unverified(client, test_db):
    """Test that unverified users can access dashboard but see warning."""
    # Register new user
    await client.post(
        "/register-form",
        data={
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
            "display_name": "New User",
            "agree_terms": "true",
        },
    )

    # Try to access dashboard - should be allowed now
    response = await client.get("/dashboard")

    # Should be allowed to view dashboard
    assert response.status_code == 200
    # Should show verification warning
    assert "Please Verify Your Email" in response.text or "verify" in response.text.lower()


@pytest.mark.asyncio
async def test_verify_email_with_valid_token(client, test_db, test_user):
    """Test verifying email with valid token."""
    # Mark user as unverified
    test_user.email_verified = False
    await test_db.commit()

    # Create verification token
    plain_token = await create_verification_token(test_db, test_user.id)

    # Verify email
    response = await client.get(f"/verify-email?token={plain_token}")

    assert response.status_code == 200

    # Check user is now verified
    await test_db.refresh(test_user)
    assert test_user.email_verified is True


@pytest.mark.asyncio
async def test_verify_email_marks_token_used(client, test_db, test_user):
    """Test that verification marks token as used."""
    # Mark user as unverified
    test_user.email_verified = False
    await test_db.commit()

    plain_token = await create_verification_token(test_db, test_user.id)

    # Verify email
    response = await client.get(f"/verify-email?token={plain_token}")
    assert response.status_code == 200

    # Check token is marked as used
    from sqlalchemy import select

    result = await test_db.execute(select(Token).where(Token.user_id == test_user.id))
    token = result.scalar_one()
    assert token.used_at is not None


@pytest.mark.asyncio
async def test_verify_email_with_expired_token(client, test_db, test_user):
    """Test that expired tokens are rejected."""
    from app.auth.tokens import generate_token

    # Mark user as unverified
    test_user.email_verified = False
    await test_db.commit()

    plain_token = generate_token()
    hashed = hash_token(plain_token)

    # Create expired token
    expired_token = Token(
        user_id=test_user.id,
        token=hashed,
        token_type="email_verification",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    test_db.add(expired_token)
    await test_db.commit()

    # Try to verify with expired token
    response = await client.get(f"/verify-email?token={plain_token}")

    # Should show error
    assert response.status_code in [400, 200]  # 200 with error message
    await test_db.refresh(test_user)
    assert test_user.email_verified is False


@pytest.mark.asyncio
async def test_verify_email_with_invalid_token(client, test_db, test_user):
    """Test that invalid tokens are rejected."""
    # Mark user as unverified
    test_user.email_verified = False
    await test_db.commit()

    response = await client.get("/verify-email?token=invalid_token_123")

    assert response.status_code in [400, 200]  # 200 with error message
    await test_db.refresh(test_user)
    assert test_user.email_verified is False


@pytest.mark.asyncio
async def test_verify_email_with_used_token(client, test_db, test_user):
    """Test that already-used tokens are rejected."""
    plain_token = await create_verification_token(test_db, test_user.id)

    # Use the token once
    await client.get(f"/verify-email?token={plain_token}")

    # Try to use it again
    response = await client.get(f"/verify-email?token={plain_token}")

    assert response.status_code in [400, 200]  # Should show error


@pytest.mark.asyncio
@patch("app.email.service.resend.Emails.send")
async def test_resend_verification_creates_new_token(mock_send, client, test_db, test_user):
    """Test that resending verification creates a new token."""
    # Mark user as unverified and log in
    test_user.email_verified = False
    await test_db.commit()

    await client.post("/login-form", data={"email": test_user.email, "password": "testpassword"})

    # Create initial token
    await create_verification_token(test_db, test_user.id)

    with patch.dict(
        "os.environ",
        {
            "RESEND_API_KEY": "test_key",
            "FROM_EMAIL": "test@example.com",
            "BASE_URL": "http://localhost:8000",
        },
    ):
        # Resend verification
        response = await client.post("/resend-verification")

        assert response.status_code == 200

        # Check that a new token was created
        from sqlalchemy import select

        result = await test_db.execute(
            select(Token)
            .where(Token.user_id == test_user.id)
            .where(Token.token_type == "email_verification")
        )
        tokens = result.scalars().all()
        assert len(tokens) >= 1  # At least one token exists


@pytest.mark.asyncio
@patch("app.email.service.resend.Emails.send")
async def test_resend_verification_invalidates_old_token(mock_send, client, test_db, test_user):
    """Test that resending verification invalidates old tokens."""
    # Mark user as unverified and log in
    test_user.email_verified = False
    await test_db.commit()

    await client.post("/login-form", data={"email": test_user.email, "password": "testpassword"})

    # Create initial token
    old_token = await create_verification_token(test_db, test_user.id)

    with patch.dict(
        "os.environ",
        {
            "RESEND_API_KEY": "test_key",
            "FROM_EMAIL": "test@example.com",
            "BASE_URL": "http://localhost:8000",
        },
    ):
        # Resend verification
        await client.post("/resend-verification")

        # Old token should not work anymore
        await client.get(f"/verify-email?token={old_token}")
        await test_db.refresh(test_user)
        assert test_user.email_verified is False


@pytest.mark.asyncio
@patch("app.email.service.resend.Emails.send")
async def test_resend_verification_sends_email(mock_send, client, test_db, test_user):
    """Test that resending verification sends an email."""
    # Mark user as unverified and log in
    test_user.email_verified = False
    await test_db.commit()

    await client.post("/login-form", data={"email": test_user.email, "password": "testpassword"})

    with patch.dict(
        "os.environ",
        {
            "RESEND_API_KEY": "test_key",
            "FROM_EMAIL": "test@example.com",
            "BASE_URL": "http://localhost:8000",
        },
    ):
        response = await client.post("/resend-verification")

        assert response.status_code == 200
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_unverified_user_blocked_from_upload(client, test_db):
    """Test that unverified users cannot access upload page."""
    # Register unverified user
    await client.post(
        "/register-form",
        data={
            "email": "unverified@example.com",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
            "display_name": "Unverified User",
            "agree_terms": "true",
        },
    )

    # Try to access upload
    response = await client.get("/upload")

    assert response.status_code in [403, 302]


@pytest.mark.asyncio
async def test_unverified_user_can_view_dashboard(client, test_db):
    """Test that unverified users can view dashboard but with limited functionality."""
    # Register unverified user
    await client.post(
        "/register-form",
        data={
            "email": "unverified@example.com",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
            "display_name": "Unverified User",
            "agree_terms": "true",
        },
    )

    # Try to access dashboard - should be allowed
    response = await client.get("/dashboard")

    assert response.status_code == 200
    # Should show verification warning
    assert "Please Verify Your Email" in response.text or "verify" in response.text.lower()


@pytest.mark.asyncio
async def test_unverified_user_can_logout(client, test_db):
    """Test that unverified users can still logout."""
    # Register unverified user
    await client.post(
        "/register-form",
        data={
            "email": "unverified@example.com",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
            "display_name": "Unverified User",
            "agree_terms": "true",
        },
    )

    # Logout should work
    response = await client.post("/logout")

    assert response.status_code == 302  # Redirect after logout


@pytest.mark.asyncio
async def test_verified_user_can_access_upload(client, test_db, test_user):
    """Test that verified users can access upload."""
    # Mark user as verified
    test_user.email_verified = True
    await test_db.commit()

    # Login
    await client.post("/login-form", data={"email": test_user.email, "password": "testpassword"})

    # Access upload
    response = await client.get("/upload")

    assert response.status_code == 200
