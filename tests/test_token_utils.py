from datetime import UTC, datetime, timedelta

import pytest

from app.auth.tokens import (
    create_password_reset_token,
    create_verification_token,
    generate_token,
    hash_token,
    invalidate_user_tokens,
    validate_token,
    verify_token_hash,
)
from app.models.token import Token


def test_generate_token_length():
    """Test that generated token is URL-safe and has correct length."""
    token = generate_token()
    assert isinstance(token, str)
    # token_urlsafe(32) produces 43 characters (base64 encoded 32 bytes)
    assert len(token) == 43
    # Check it's URL-safe (alphanumeric, -, _)
    assert all(c.isalnum() or c in "-_" for c in token)


def test_generate_token_uniqueness():
    """Test that each call produces a unique token."""
    tokens = [generate_token() for _ in range(100)]
    # All tokens should be unique
    assert len(tokens) == len(set(tokens))


def test_hash_token_deterministic():
    """Test that hashing the same token produces the same hash."""
    token = "test_token_123"
    hash1 = hash_token(token)
    hash2 = hash_token(token)
    assert hash1 == hash2
    assert isinstance(hash1, str)


def test_hash_token_different_for_different_tokens():
    """Test that different tokens produce different hashes."""
    token1 = "test_token_1"
    token2 = "test_token_2"
    hash1 = hash_token(token1)
    hash2 = hash_token(token2)
    assert hash1 != hash2


def test_verify_token_hash_correct_token():
    """Test verifying a token against its correct hash."""
    token = "test_token_123"
    token_hash = hash_token(token)
    assert verify_token_hash(token, token_hash) is True


def test_verify_token_hash_wrong_token():
    """Test verifying a token against an incorrect hash."""
    token = "test_token_123"
    wrong_token = "wrong_token_456"
    token_hash = hash_token(token)
    assert verify_token_hash(wrong_token, token_hash) is False


@pytest.mark.asyncio
async def test_create_verification_token(test_db, test_user):
    """Test creating an email verification token."""
    plain_token = await create_verification_token(test_db, test_user.id)

    assert isinstance(plain_token, str)
    assert len(plain_token) == 43

    # Verify token was stored in database with hashed value
    from sqlalchemy import select

    result = await test_db.execute(select(Token).where(Token.user_id == test_user.id))
    db_token = result.scalar_one()

    assert db_token.token_type == "email_verification"
    assert db_token.user_id == test_user.id
    assert verify_token_hash(plain_token, db_token.token)
    # Expiry should be in the future (default 24 hours)
    assert db_token.expires_at.replace(tzinfo=UTC) > datetime.now(UTC)
    assert db_token.used_at is None


@pytest.mark.asyncio
async def test_create_password_reset_token(test_db, test_user):
    """Test creating a password reset token with 1-hour expiry."""
    now = datetime.now(UTC)
    plain_token = await create_password_reset_token(test_db, test_user.id)

    assert isinstance(plain_token, str)
    assert len(plain_token) == 43

    # Verify token was stored in database
    from sqlalchemy import select

    result = await test_db.execute(select(Token).where(Token.user_id == test_user.id))
    db_token = result.scalar_one()

    assert db_token.token_type == "password_reset"
    assert db_token.user_id == test_user.id
    assert verify_token_hash(plain_token, db_token.token)

    # Expiry should be approximately 1 hour from now
    token_expires_aware = db_token.expires_at.replace(tzinfo=UTC)
    time_until_expiry = (token_expires_aware - now).total_seconds()
    assert 3590 < time_until_expiry < 3610  # 1 hour ± 10 seconds
    assert db_token.used_at is None


@pytest.mark.asyncio
async def test_validate_token_valid(test_db, test_user):
    """Test validating a valid unexpired token."""
    plain_token = await create_verification_token(test_db, test_user.id)

    # Validate the token
    user = await validate_token(test_db, plain_token, "email_verification")

    assert user is not None
    assert user.id == test_user.id
    assert user.email == test_user.email


@pytest.mark.asyncio
async def test_validate_token_expired(test_db, test_user):
    """Test that expired tokens are rejected."""
    # Create a token that's already expired
    from app.models.token import Token

    plain_token = generate_token()
    hashed = hash_token(plain_token)

    expired_token = Token(
        user_id=test_user.id,
        token=hashed,
        token_type="email_verification",
        expires_at=datetime.now(UTC) - timedelta(hours=1),  # Expired 1 hour ago
    )
    test_db.add(expired_token)
    await test_db.commit()

    # Validation should fail
    user = await validate_token(test_db, plain_token, "email_verification")
    assert user is None


@pytest.mark.asyncio
async def test_validate_token_wrong_type(test_db, test_user):
    """Test that tokens are rejected if type doesn't match."""
    # Create a verification token
    plain_token = await create_verification_token(test_db, test_user.id)

    # Try to validate it as a password_reset token
    user = await validate_token(test_db, plain_token, "password_reset")
    assert user is None


@pytest.mark.asyncio
async def test_validate_token_already_used(test_db, test_user):
    """Test that already-used tokens are rejected."""
    plain_token = await create_verification_token(test_db, test_user.id)

    # Mark the token as used
    from sqlalchemy import select

    result = await test_db.execute(select(Token).where(Token.user_id == test_user.id))
    db_token = result.scalar_one()

    db_token.used_at = datetime.now(UTC)
    await test_db.commit()

    # Validation should fail
    user = await validate_token(test_db, plain_token, "email_verification")
    assert user is None


@pytest.mark.asyncio
async def test_invalidate_user_tokens(test_db, test_user):
    """Test invalidating all tokens of a specific type for a user."""
    # Create multiple tokens
    token1 = await create_password_reset_token(test_db, test_user.id)
    token2 = await create_password_reset_token(test_db, test_user.id)
    verification_token = await create_verification_token(test_db, test_user.id)

    # Invalidate password_reset tokens
    await invalidate_user_tokens(test_db, test_user.id, "password_reset")

    # Password reset tokens should be invalidated
    user1 = await validate_token(test_db, token1, "password_reset")
    user2 = await validate_token(test_db, token2, "password_reset")
    assert user1 is None
    assert user2 is None

    # Verification token should still be valid
    user3 = await validate_token(test_db, verification_token, "email_verification")
    assert user3 is not None
    assert user3.id == test_user.id
