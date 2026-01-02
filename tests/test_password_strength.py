"""Tests for password strength validation."""

from httpx import AsyncClient
import pytest


@pytest.mark.asyncio
async def test_register_password_too_short(client: AsyncClient):
    """Test that passwords shorter than 8 characters are rejected."""
    response = await client.post(
        "/register-form",
        data={
            "email": "newuser@example.com",
            "password": "Short1",  # Only 6 characters
            "confirm_password": "Short1",
            "display_name": "New User",
            "agree_terms": "true",
        },
    )

    assert response.status_code == 422
    assert b"8 characters" in response.content or b"too short" in response.content.lower()


@pytest.mark.asyncio
async def test_register_password_no_number(client: AsyncClient):
    """Test that passwords without numbers are rejected."""
    response = await client.post(
        "/register-form",
        data={
            "email": "newuser@example.com",
            "password": "NoNumbersHere",  # No digits
            "confirm_password": "NoNumbersHere",
            "display_name": "New User",
            "agree_terms": "true",
        },
    )

    assert response.status_code == 422
    assert b"number" in response.content.lower() or b"digit" in response.content.lower()


@pytest.mark.asyncio
async def test_register_valid_password(client: AsyncClient):
    """Test that valid passwords (8+ chars with number) are accepted."""
    response = await client.post(
        "/register-form",
        data={
            "email": "newuser@example.com",
            "password": "ValidPass123",  # 12 chars with numbers
            "confirm_password": "ValidPass123",
            "display_name": "New User",
            "agree_terms": "true",
        },
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_register_minimal_valid_password(client: AsyncClient):
    """Test that minimal valid password (8 chars with 1 number) works."""
    response = await client.post(
        "/register-form",
        data={
            "email": "minimal@example.com",
            "password": "abcdefg1",  # Exactly 8 chars with 1 number
            "confirm_password": "abcdefg1",
            "display_name": "Minimal User",
            "agree_terms": "true",
        },
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_validates_strength(client: AsyncClient, test_user, test_db):
    """Test that password reset also validates password strength."""
    from app.auth.tokens import create_password_reset_token

    token = await create_password_reset_token(test_db, test_user.id)

    # Try to reset with weak password
    response = await client.post(
        "/reset-password-form",
        data={
            "token": token,
            "password": "weak",  # Too short, no number
            "confirm_password": "weak",
        },
    )

    assert response.status_code == 422
