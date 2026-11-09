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


async def test_privacy_names_every_service_that_handles_personal_data(client: AsyncClient):
    """Cloudflare carries all traffic, Tigris stores uploaded files, Zenodo receives
    author metadata on publish, ORCID provides the iD and name at login."""
    html = (await client.get("/privacy")).text

    for name in ("Cloudflare", "Tigris", "Zenodo", "ORCID"):
        assert name in html, name


async def test_privacy_does_not_describe_comments(client: AsyncClient):
    """Press has no comments, so the policy must not say it collects them."""
    html = (await client.get("/privacy")).text.lower()

    assert "comment" not in html
