from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import Token
from app.models.user import User


def generate_token() -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token using SHA-256 for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token_hash(token: str, hashed: str) -> bool:
    """Verify a plain token against its hash."""
    return hash_token(token) == hashed


async def create_verification_token(db: AsyncSession, user_id: str) -> str:
    """Create an email verification token for a user.

    Args:
        db: Database session
        user_id: User's UUID

    Returns:
        Plain (unhashed) token string to be sent in email
    """
    plain_token = generate_token()
    hashed = hash_token(plain_token)

    token = Token(
        user_id=user_id,
        token=hashed,
        token_type="email_verification",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )

    db.add(token)
    await db.commit()

    return plain_token


async def create_password_reset_token(db: AsyncSession, user_id: str) -> str:
    """Create a password reset token for a user with 1-hour expiry.

    Args:
        db: Database session
        user_id: User's UUID

    Returns:
        Plain (unhashed) token string to be sent in email
    """
    plain_token = generate_token()
    hashed = hash_token(plain_token)

    token = Token(
        user_id=user_id,
        token=hashed,
        token_type="password_reset",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    db.add(token)
    await db.commit()

    return plain_token


async def validate_token(db: AsyncSession, plain_token: str, token_type: str) -> Optional[User]:
    """Validate a token and return the associated user if valid.

    Args:
        db: Database session
        plain_token: Unhashed token from email link
        token_type: Expected token type ("email_verification" or "password_reset")

    Returns:
        User object if token is valid, None otherwise
    """
    hashed = hash_token(plain_token)
    now = datetime.now(UTC)

    # Find token by hash, type, and ensure it's not expired or used
    result = await db.execute(
        select(Token)
        .where(Token.token == hashed)
        .where(Token.token_type == token_type)
        .where(Token.expires_at > now)
        .where(Token.used_at.is_(None))
    )
    token = result.scalar_one_or_none()

    if token is None:
        return None

    # Fetch and return the associated user
    user_result = await db.execute(select(User).where(User.id == token.user_id))
    return user_result.scalar_one_or_none()


async def invalidate_user_tokens(db: AsyncSession, user_id: str, token_type: str) -> None:
    """Invalidate all tokens of a specific type for a user by setting used_at.

    Args:
        db: Database session
        user_id: User's UUID
        token_type: Token type to invalidate
    """
    now = datetime.now(UTC)

    await db.execute(
        update(Token)
        .where(Token.user_id == user_id)
        .where(Token.token_type == token_type)
        .where(Token.used_at.is_(None))
        .values(used_at=now)
    )
    await db.commit()
