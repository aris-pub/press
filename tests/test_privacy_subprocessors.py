"""Tests for privacy policy subprocessor disclosures."""

from httpx import AsyncClient


async def test_privacy_page_loads(client: AsyncClient):
    """Test GET /privacy returns 200."""
    response = await client.get("/privacy")
    assert response.status_code == 200
    assert "Privacy Policy" in response.text


async def test_privacy_names_subprocessors(client: AsyncClient):
    """GDPR requires naming data processors. Verify each subprocessor is listed."""
    response = await client.get("/privacy")
    html = response.text

    assert "Supabase" in html
    assert "Fly.io" in html
    assert "Resend" in html
    assert "Sentry" in html


async def test_privacy_subprocessor_purposes(client: AsyncClient):
    """Each subprocessor listing should include its purpose."""
    response = await client.get("/privacy")
    html = response.text

    assert "database" in html.lower() or "data storage" in html.lower()
    assert "hosting" in html.lower() or "application hosting" in html.lower()
    assert "email" in html.lower()
    assert "error monitoring" in html.lower() or "error tracking" in html.lower()


async def test_privacy_subprocessor_section_exists(client: AsyncClient):
    """There should be a dedicated subprocessors/data processors section."""
    response = await client.get("/privacy")
    html = response.text

    assert "Subprocessors" in html or "Data Processors" in html
