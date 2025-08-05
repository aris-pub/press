"""Security tests for HTTPS redirect and security headers."""

import httpx
import pytest

pytestmark = pytest.mark.e2e


async def test_security_headers_present(test_server):
    """Test that security headers are present in E2E test responses."""
    # E2E tests disable HTTPS redirect, so we get normal responses with security headers
    async with httpx.AsyncClient(follow_redirects=False) as client:
        response = await client.get(test_server)

        # Should get normal response (E2E testing disables HTTPS redirect)
        assert response.status_code == 200

        # Check for important security headers
        headers = response.headers

        # X-Frame-Options prevents clickjacking
        assert headers.get("x-frame-options") is not None

        # X-Content-Type-Options prevents MIME sniffing
        assert headers.get("x-content-type-options") is not None

        # X-XSS-Protection (legacy but still good to have)
        x_xss_protection = headers.get("x-xss-protection")
        if x_xss_protection:  # Optional header
            assert x_xss_protection in ["1; mode=block", "0"]


async def test_hsts_header_present_on_simulated_https(test_server):
    """Test that HSTS header is present when simulating HTTPS via proxy header."""
    # This test simulates an HTTPS request by setting x-forwarded-proto header
    # In production with a reverse proxy, this header would be set automatically
    async with httpx.AsyncClient(follow_redirects=False) as client:
        # Simulate request through HTTPS proxy
        headers = {"x-forwarded-proto": "https"}
        response = await client.get(test_server, headers=headers)

        # Should get normal response with HSTS (E2E testing still allows proxy HTTPS detection)
        assert response.status_code == 200

        # Check for HSTS header
        hsts = response.headers.get("strict-transport-security")
        assert hsts is not None
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts


async def test_hsts_header_not_present_on_http(test_server):
    """Test that HSTS header is NOT present on HTTP responses."""
    async with httpx.AsyncClient(follow_redirects=False) as client:
        response = await client.get(test_server)

        # Should get normal response (E2E testing, no redirect)
        assert response.status_code == 200

        # HSTS header should NOT be present on HTTP responses
        hsts = response.headers.get("strict-transport-security")
        assert hsts is None
