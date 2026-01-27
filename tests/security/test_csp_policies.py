"""Tests for Content Security Policy configurations across different page types."""

from httpx import AsyncClient
import pytest

from app.models.scroll import Subject
from tests.conftest import create_content_addressable_scroll


@pytest.mark.asyncio
async def test_homepage_csp_allows_htmx(client: AsyncClient):
    """Test that homepage CSP allows HTMX and inline scripts without strict-dynamic."""
    response = await client.get("/")
    assert response.status_code == 200

    csp_header = response.headers.get("Content-Security-Policy")
    assert csp_header is not None

    # Homepage should NOT use strict-dynamic
    assert "strict-dynamic" not in csp_header

    # Should allow external scripts like HTMX
    assert "https://unpkg.com" in csp_header

    # Should allow unsafe-inline for backward compatibility
    assert "unsafe-inline" in csp_header

    # Static pages should NOT have nonces (only scroll pages need them)
    assert "nonce-" not in csp_header


@pytest.mark.asyncio
async def test_scroll_page_csp_uses_strict_dynamic(client: AsyncClient, test_db, test_user):
    """Test that scroll pages use strict-dynamic CSP for user content security."""
    # Create a test scroll
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Test Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Content</h1><script>console.log('user script');</script>",
        license="cc-by-4.0",
    )
    scroll.publish()
    await test_db.commit()

    response = await client.get(f"/scroll/{scroll.url_hash}")
    assert response.status_code == 200

    csp_header = response.headers.get("Content-Security-Policy")
    assert csp_header is not None

    # Scroll pages SHOULD use strict-dynamic
    assert "strict-dynamic" in csp_header

    # Should have nonce for trusted scripts
    assert "nonce-" in csp_header

    # Should allow unsafe-inline (ignored when nonce present, but good for fallback)
    assert "unsafe-inline" in csp_header

    # Should allow CDN domains for visualization libraries
    # With strict-dynamic, these domains are allowed but scripts still need to be loaded by trusted scripts
    assert "https://unpkg.com" in csp_header
    assert "https://cdn.jsdelivr.net" in csp_header
    assert "https://cdnjs.cloudflare.com" in csp_header


@pytest.mark.asyncio
async def test_upload_page_csp_allows_htmx(authenticated_client: AsyncClient):
    """Test that upload page CSP allows HTMX for form functionality."""
    response = await authenticated_client.get("/upload")
    assert response.status_code == 200

    csp_header = response.headers.get("Content-Security-Policy")
    assert csp_header is not None

    # Upload page should NOT use strict-dynamic
    assert "strict-dynamic" not in csp_header

    # Should allow external scripts like HTMX
    assert "https://unpkg.com" in csp_header

    # Should allow unsafe-inline for HTMX and other inline scripts
    assert "unsafe-inline" in csp_header


@pytest.mark.asyncio
async def test_login_page_csp_allows_htmx(client: AsyncClient):
    """Test that login page CSP allows HTMX for form functionality."""
    response = await client.get("/login")
    assert response.status_code == 200

    csp_header = response.headers.get("Content-Security-Policy")
    assert csp_header is not None

    # Login page should NOT use strict-dynamic
    assert "strict-dynamic" not in csp_header

    # Should allow external scripts like HTMX
    assert "https://unpkg.com" in csp_header

    # Should allow unsafe-inline for HTMX and other inline scripts
    assert "unsafe-inline" in csp_header


@pytest.mark.asyncio
async def test_static_pages_have_consistent_csp(client: AsyncClient):
    """Test that static pages have consistent CSP policies."""
    static_pages = ["/", "/about", "/how-it-works", "/login", "/register"]

    csp_policies = []
    for page in static_pages:
        response = await client.get(page)
        # Skip pages that might redirect or require auth
        if response.status_code in [200, 302]:
            csp_header = response.headers.get("Content-Security-Policy")
            if csp_header:
                csp_policies.append((page, csp_header))

    # Should have at least some pages to test
    assert len(csp_policies) > 0

    for page, csp_header in csp_policies:
        # All static pages should allow HTMX
        assert "https://unpkg.com" in csp_header, f"Page {page} doesn't allow HTMX"

        # All static pages should NOT use strict-dynamic
        assert "strict-dynamic" not in csp_header, f"Page {page} incorrectly uses strict-dynamic"

        # All should allow unsafe-inline for backward compatibility
        assert "unsafe-inline" in csp_header, f"Page {page} doesn't allow unsafe-inline"


@pytest.mark.asyncio
async def test_scroll_raw_endpoint_csp(client: AsyncClient, test_db, test_user):
    """Test that scroll raw endpoint has appropriate CSP."""
    # Create a test scroll
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Test Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Content</h1>",
        license="cc-by-4.0",
    )
    scroll.publish()
    await test_db.commit()

    response = await client.get(f"/scroll/{scroll.url_hash}/raw")
    assert response.status_code == 200

    csp_header = response.headers.get("Content-Security-Policy")
    assert csp_header is not None

    # Raw endpoint should NOT use strict-dynamic (it serves raw content)
    assert "strict-dynamic" not in csp_header


@pytest.mark.asyncio
async def test_csp_always_includes_required_directives(client: AsyncClient):
    """Test that all CSP policies include required security directives."""
    response = await client.get("/")
    assert response.status_code == 200

    csp_header = response.headers.get("Content-Security-Policy")
    assert csp_header is not None

    # Check required directives are present
    assert "default-src" in csp_header
    assert "script-src" in csp_header
    assert "style-src" in csp_header
    assert "img-src" in csp_header
    assert "font-src" in csp_header
    assert "connect-src" in csp_header

    # Check security values
    assert "'self'" in csp_header
    assert "data:" in csp_header  # For images
    assert "https://fonts.googleapis.com" in csp_header  # For Google Fonts
    assert "https://fonts.gstatic.com" in csp_header  # For Google Fonts


@pytest.mark.asyncio
async def test_nonce_only_on_scroll_pages(client: AsyncClient):
    """Test that nonces are only generated for scroll pages, not static pages."""
    # Static pages should NOT have nonces
    static_pages = ["/", "/about", "/login"]

    for page in static_pages:
        response = await client.get(page)
        if response.status_code == 200:
            csp_header = response.headers.get("Content-Security-Policy")
            assert csp_header is not None
            assert "nonce-" not in csp_header, f"Static page {page} incorrectly has nonce in CSP"

    # Scroll pages SHOULD have nonces (test with a 404 scroll page)
    response = await client.get("/scroll/nonexistent")
    csp_header = response.headers.get("Content-Security-Policy")
    assert csp_header is not None
    assert "nonce-" in csp_header, "Scroll page should have nonce in CSP"


@pytest.mark.asyncio
async def test_paper_endpoint_csp_allows_unsafe_eval(client: AsyncClient, test_db, test_user):
    """Test that /paper endpoint CSP includes unsafe-eval for Bokeh/Plotly support.

    Security rationale: unsafe-eval is required for interactive academic visualizations
    (Bokeh, Plotly, Observable) that use new Function() for dynamic callbacks. This
    does not meaningfully increase risk vs unsafe-inline since entire HTML document
    is untrusted user content served in isolated iframe.
    """
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Test Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Content</h1>",
        license="cc-by-4.0",
    )
    scroll.publish()
    await test_db.commit()

    response = await client.get(f"/scroll/{scroll.url_hash}/paper")
    assert response.status_code == 200

    csp_header = response.headers.get("Content-Security-Policy")
    assert csp_header is not None
    assert "unsafe-eval" in csp_header, "CSP should include unsafe-eval for Bokeh/Plotly support"
    assert "unsafe-inline" in csp_header, "CSP should include unsafe-inline for user scripts"
