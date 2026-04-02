"""Tests for ORCID buttons on login and register pages."""

from unittest.mock import patch

from httpx import AsyncClient


async def test_login_page_shows_orcid_button_when_configured(client: AsyncClient):
    """ORCID button appears on login page when ORCID_CLIENT_ID is set."""
    with patch("app.routes.auth.ORCID_ENABLED", True):
        response = await client.get("/login")
    assert response.status_code == 200
    assert "Sign in with ORCID" in response.text
    assert "/auth/orcid" in response.text


async def test_login_page_hides_orcid_button_when_not_configured(client: AsyncClient):
    """ORCID button is hidden on login page when ORCID_CLIENT_ID is not set."""
    with patch("app.routes.auth.ORCID_ENABLED", False):
        response = await client.get("/login")
    assert response.status_code == 200
    assert "Sign in with ORCID" not in response.text


async def test_register_page_shows_orcid_button_when_configured(client: AsyncClient):
    """ORCID button appears on register page when ORCID_CLIENT_ID is set."""
    with patch("app.routes.auth.ORCID_ENABLED", True):
        response = await client.get("/register")
    assert response.status_code == 200
    assert "Register with ORCID" in response.text
    assert "/auth/orcid" in response.text


async def test_register_page_hides_orcid_button_when_not_configured(client: AsyncClient):
    """ORCID button is hidden on register page when ORCID_CLIENT_ID is not set."""
    with patch("app.routes.auth.ORCID_ENABLED", False):
        response = await client.get("/register")
    assert response.status_code == 200
    assert "Register with ORCID" not in response.text


async def test_orcid_button_has_correct_brand_color(client: AsyncClient):
    """ORCID button uses the official brand color #a6ce39."""
    with patch("app.routes.auth.ORCID_ENABLED", True):
        response = await client.get("/login")
    assert "a6ce39" in response.text


async def test_orcid_button_contains_orcid_logo_svg(client: AsyncClient):
    """ORCID button includes the ORCID iD SVG logo."""
    with patch("app.routes.auth.ORCID_ENABLED", True):
        response = await client.get("/login")
    assert "<svg" in response.text
    assert "orcid-logo" in response.text


async def test_login_page_has_email_separator(client: AsyncClient):
    """Login page shows 'or sign in with email' separator when ORCID is configured."""
    with patch("app.routes.auth.ORCID_ENABLED", True):
        response = await client.get("/login")
    assert "or sign in with email" in response.text.lower()


async def test_register_page_has_email_separator(client: AsyncClient):
    """Register page shows 'or register with email' separator when ORCID is configured."""
    with patch("app.routes.auth.ORCID_ENABLED", True):
        response = await client.get("/register")
    assert "or register with email" in response.text.lower()
