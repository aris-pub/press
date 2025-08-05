"""Unit tests for security headers middleware."""

from httpx import AsyncClient
import pytest


@pytest.mark.asyncio
async def test_hsts_header_on_https_unit_test(client: AsyncClient):
    """Test that HSTS header is present on HTTPS unit test responses."""
    # Unit tests use https://test base URL, so HTTPS scheme is detected
    response = await client.get("/health")

    assert response.status_code == 200

    # Should have HSTS header since unit tests use HTTPS base URL
    hsts = response.headers.get("strict-transport-security")
    assert hsts is not None
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts


@pytest.mark.asyncio
async def test_security_headers_present_unit_test(client: AsyncClient):
    """Test that all security headers are present on unit test responses."""
    response = await client.get("/health")

    assert response.status_code == 200

    # Check all security headers
    headers = response.headers
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-xss-protection") == "1; mode=block"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert headers.get("strict-transport-security") is not None
