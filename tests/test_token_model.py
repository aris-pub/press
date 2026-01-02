from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.token import Token


@pytest.mark.asyncio
async def test_token_model_creation(test_db, test_user):
    """Test creating a token with all fields."""
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    token = Token(
        user_id=test_user.id,
        token="hashed_token_value",
        token_type="email_verification",
        expires_at=expires_at,
    )
    test_db.add(token)
    await test_db.commit()
    await test_db.refresh(token)

    assert token.id is not None
    assert token.user_id == test_user.id
    assert token.token == "hashed_token_value"
    assert token.token_type == "email_verification"
    assert token.created_at is not None
    # Compare timestamps (may be timezone-naive from SQLite)
    assert abs((token.expires_at.replace(tzinfo=UTC) - expires_at).total_seconds()) < 1
    assert token.used_at is None


@pytest.mark.asyncio
async def test_token_has_user_relationship(test_db, test_user):
    """Test that token has a relationship to User model."""
    token = Token(
        user_id=test_user.id,
        token="hashed_token",
        token_type="password_reset",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    test_db.add(token)
    await test_db.commit()
    await test_db.refresh(token)

    # Query the token and check user relationship
    result = await test_db.execute(select(Token).where(Token.id == token.id))
    found_token = result.scalar_one()

    assert found_token.user_id == test_user.id
    # Relationship should be loaded
    await test_db.refresh(found_token, ["user"])
    assert found_token.user.email == test_user.email


@pytest.mark.asyncio
async def test_token_expires_at_in_future(test_db, test_user):
    """Test that expires_at can be set to a future time."""
    now = datetime.now(UTC)
    future_time = now + timedelta(days=1)

    token = Token(
        user_id=test_user.id,
        token="hashed_token",
        token_type="email_verification",
        expires_at=future_time,
    )
    test_db.add(token)
    await test_db.commit()
    await test_db.refresh(token)

    # Handle timezone-naive datetime from SQLite
    token_expires_aware = (
        token.expires_at.replace(tzinfo=UTC)
        if token.expires_at.tzinfo is None
        else token.expires_at
    )
    assert token_expires_aware > now
    assert abs((token_expires_aware - future_time).total_seconds()) < 1


@pytest.mark.asyncio
async def test_token_type_enum_validation(test_db, test_user):
    """Test that only valid token types are allowed."""
    # Valid types should work
    valid_types = ["email_verification", "password_reset"]

    for token_type in valid_types:
        token = Token(
            user_id=test_user.id,
            token=f"hashed_token_{token_type}",
            token_type=token_type,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        test_db.add(token)
        await test_db.commit()
        await test_db.refresh(token)
        assert token.token_type == token_type


@pytest.mark.asyncio
async def test_token_unique_constraint(test_db, test_user):
    """Test that token values must be unique."""
    token1 = Token(
        user_id=test_user.id,
        token="same_hashed_token",
        token_type="email_verification",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    test_db.add(token1)
    await test_db.commit()

    # Try to create another token with the same hashed value
    token2 = Token(
        user_id=test_user.id,
        token="same_hashed_token",
        token_type="password_reset",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    test_db.add(token2)

    with pytest.raises(IntegrityError):
        await test_db.commit()

    await test_db.rollback()


@pytest.mark.asyncio
async def test_query_unexpired_tokens(test_db, test_user):
    """Test filtering tokens by expiration date."""
    now = datetime.now(UTC)

    # Create an expired token
    expired_token = Token(
        user_id=test_user.id,
        token="expired_token",
        token_type="email_verification",
        expires_at=now - timedelta(hours=1),
    )

    # Create a valid token
    valid_token = Token(
        user_id=test_user.id,
        token="valid_token",
        token_type="email_verification",
        expires_at=now + timedelta(hours=1),
    )

    test_db.add_all([expired_token, valid_token])
    await test_db.commit()

    # Query for unexpired tokens
    result = await test_db.execute(select(Token).where(Token.expires_at > now))
    unexpired = result.scalars().all()

    assert len(unexpired) == 1
    assert unexpired[0].token == "valid_token"


@pytest.mark.asyncio
async def test_mark_token_as_used(test_db, test_user):
    """Test marking a token as used by setting used_at."""
    token = Token(
        user_id=test_user.id,
        token="hashed_token",
        token_type="password_reset",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    test_db.add(token)
    await test_db.commit()
    await test_db.refresh(token)

    assert token.used_at is None

    # Mark as used
    token.used_at = datetime.now(UTC)
    await test_db.commit()
    await test_db.refresh(token)

    assert token.used_at is not None
    assert isinstance(token.used_at, datetime)
