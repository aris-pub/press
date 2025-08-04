"""Tests for the nonce-based CSP system."""

import pytest

from app.security.nonce import (
    generate_nonce,
    get_nonce_from_request,
    is_valid_nonce,
    store_nonce_in_request,
)


def test_generate_nonce():
    """Test nonce generation produces unique, valid nonces."""
    nonce1 = generate_nonce()
    nonce2 = generate_nonce()

    # Nonces should be unique
    assert nonce1 != nonce2

    # Nonces should be valid format (44 chars, base64)
    assert len(nonce1) == 44
    assert len(nonce2) == 44

    # Should be valid according to our validator
    assert is_valid_nonce(nonce1)
    assert is_valid_nonce(nonce2)


def test_is_valid_nonce():
    """Test nonce validation."""
    # Valid nonce
    valid_nonce = generate_nonce()
    assert is_valid_nonce(valid_nonce)

    # Invalid nonces
    assert not is_valid_nonce("too_short")
    assert not is_valid_nonce("this_is_way_too_long_to_be_a_valid_nonce_string")
    assert not is_valid_nonce("invalid!@#$%characters")
    assert not is_valid_nonce("")
    assert not is_valid_nonce(None)
    assert not is_valid_nonce(123)


def test_nonce_request_storage():
    """Test storing and retrieving nonces from request state."""

    # Create a mock request object
    class MockRequest:
        def __init__(self):
            self.state = type("State", (), {})()

    request = MockRequest()
    nonce = generate_nonce()

    # Initially no nonce
    assert get_nonce_from_request(request) is None

    # Store nonce
    store_nonce_in_request(request, nonce)

    # Should be able to retrieve it
    retrieved_nonce = get_nonce_from_request(request)
    assert retrieved_nonce == nonce


@pytest.mark.asyncio
async def test_nonce_middleware_integration(client):
    """Test that nonce middleware only adds nonces to scroll pages."""
    # Make a request to homepage - should NOT have nonce
    response = await client.get("/")

    # Response should have CSP header but WITHOUT nonce
    csp_header = response.headers.get("Content-Security-Policy")
    assert csp_header is not None
    assert "nonce-" not in csp_header
    # Homepage should NOT have strict-dynamic (only scroll pages do)
    assert "strict-dynamic" not in csp_header
    # Should allow external scripts like HTMX
    assert "https://unpkg.com" in csp_header


@pytest.mark.asyncio
async def test_scroll_page_has_nonce_csp(client):
    """Test that scroll pages get nonces and strict-dynamic CSP."""
    # Try to access a scroll page (will 404 but should still get proper CSP)
    response = await client.get("/scroll/test-id")

    # Should have CSP header with nonce and strict-dynamic
    csp_header = response.headers.get("Content-Security-Policy")
    assert csp_header is not None
    assert "nonce-" in csp_header
    assert "strict-dynamic" in csp_header
    # Should NOT allow external scripts like HTMX on scroll pages
    assert "https://unpkg.com" not in csp_header


@pytest.mark.asyncio
async def test_scroll_template_has_nonce_script(client):
    """Test that scroll template includes nonce'd script for user content."""
    # This test requires that we have a test scroll in the database
    # For now, just test that the endpoint exists and returns HTML

    # Try to access a scroll (this will 404 if no test scroll exists)
    response = await client.get("/scroll/test-id")

    # Should be HTML response (even if 404, the template system should work)
    assert "text/html" in response.headers.get("Content-Type", "")

    # If we get a successful response, check for our strict-dynamic script
    if response.status_code == 200:
        html_content = response.text
        assert "user-content-data" in html_content
        assert (
            "strict-dynamic" in html_content or "User content will be loaded here" in html_content
        )
