"""Regression tests to ensure /partials endpoints are never blocked by middleware.

This test suite prevents the nightmare scenario where middleware redirects
partial endpoints, causing the entire page to nest inside itself during
HTMX swaps.
"""

from httpx import AsyncClient
import pytest


@pytest.mark.asyncio
async def test_partials_scrolls_not_redirected(client: AsyncClient):
    """CRITICAL: /partials/scrolls must return 200, never 302 redirect."""
    response = await client.get("/partials/scrolls")

    assert response.status_code == 200, (
        f"REGRESSION: /partials/scrolls returned {response.status_code}! "
        "This endpoint must NEVER redirect (302). Check EmailVerificationMiddleware."
    )


@pytest.mark.asyncio
async def test_partials_scrolls_returns_partial_not_full_page(client: AsyncClient):
    """CRITICAL: /partials/scrolls must return partial HTML, not full page.

    If this fails, middleware is redirecting to homepage and returning full HTML,
    which causes the entire page to nest inside #scrolls-section during HTMX swap.
    """
    response = await client.get("/partials/scrolls?subject=Physics")
    html = response.text

    # Must NOT contain full page elements
    assert "<!DOCTYPE" not in html, (
        "REGRESSION: Partial contains DOCTYPE! "
        "This means it's returning the full page, not a partial."
    )
    assert "<html" not in html.lower(), (
        "REGRESSION: Partial contains <html> tag! This will cause page nesting during HTMX swap."
    )
    assert 'class="navbar"' not in html, (
        "REGRESSION: Partial contains navbar! "
        "The entire page is being returned instead of just the partial."
    )
    assert "<head>" not in html.lower(), (
        "REGRESSION: Partial contains <head> section! Full page is being returned."
    )

    # Must contain expected partial content
    assert 'id="recent-submissions-heading"' in html, "Partial missing expected heading element"
    assert 'id="scrolls-grid"' in html, "Partial missing expected scrolls grid element"


@pytest.mark.asyncio
async def test_partials_scrolls_with_subject_filter(client: AsyncClient):
    """Test that subject filtering works and returns correct partial."""
    response = await client.get("/partials/scrolls?subject=Physics")

    assert response.status_code == 200
    html = response.text

    # Check heading updates with subject
    assert "Recent Physics Scrolls" in html or "Recent Scrolls" in html

    # Must be partial, not full page
    assert "<!DOCTYPE" not in html
    assert "<html" not in html.lower()


@pytest.mark.asyncio
async def test_partials_scrolls_returns_small_response(client: AsyncClient):
    """Partial responses should be small (< 10KB), full pages are much larger.

    This catches the bug where a 302 redirect causes fetch() to follow the
    redirect and return the full page HTML (~30KB+) instead of partial (~2KB).
    """
    response = await client.get("/partials/scrolls")

    # Partial should be small - if it's > 10KB, it's likely the full page
    size = len(response.text)
    assert size < 10_000, (
        f"REGRESSION: Partial response is {size} bytes (> 10KB)! "
        f"This indicates the full page is being returned instead of a partial. "
        f"Check for middleware redirects (302 status codes)."
    )


@pytest.mark.asyncio
async def test_api_scrolls_not_blocked(client: AsyncClient):
    """CRITICAL: /api/scrolls must also not be blocked by middleware."""
    response = await client.get("/api/scrolls")

    assert response.status_code == 200, (
        f"REGRESSION: /api/scrolls returned {response.status_code}! "
        "API endpoints must not be blocked by EmailVerificationMiddleware."
    )

    # Should return JSON, not HTML
    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.asyncio
async def test_partials_no_redirect_headers(client: AsyncClient):
    """Ensure partial endpoints don't set redirect headers."""
    response = await client.get("/partials/scrolls", follow_redirects=False)

    assert response.status_code == 200, (
        f"Got {response.status_code} instead of 200. Partial endpoint is redirecting!"
    )
    assert "Location" not in response.headers, (
        "REGRESSION: Partial endpoint is setting Location header! This will cause a redirect."
    )


@pytest.mark.asyncio
async def test_partials_content_type_is_html(client: AsyncClient):
    """Partial should return HTML content type."""
    response = await client.get("/partials/scrolls")

    assert "text/html" in response.headers["content-type"], (
        f"Expected text/html, got {response.headers['content-type']}"
    )


@pytest.mark.asyncio
async def test_partials_accessible_without_auth(client: AsyncClient):
    """Partials must be accessible without authentication.

    Subject filtering on the homepage should work for anonymous users.
    """
    # client fixture has no authentication
    response = await client.get("/partials/scrolls")

    assert response.status_code == 200, (
        "REGRESSION: Partials require authentication! "
        "Anonymous users must be able to filter subjects on homepage."
    )

    # Must not redirect to login
    assert "/login" not in response.text.lower() or "login" in response.text.lower(), (
        "Partial is redirecting to login page!"
    )
