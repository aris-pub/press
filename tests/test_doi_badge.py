"""Tests for DOI badge component rendering."""

from jinja2 import Environment, FileSystemLoader
import pytest


@pytest.fixture
def jinja_env():
    """Create Jinja2 environment for testing components."""
    return Environment(loader=FileSystemLoader("app/templates"))


@pytest.mark.asyncio
async def test_doi_badge_minted_production(jinja_env):
    """Test DOI badge shows minted production DOI correctly."""
    template = jinja_env.get_template("components/doi_badge.html")

    # Render the doi_badge macro
    result = template.module.doi_badge(doi="10.5281/zenodo.1234567", doi_status="minted")

    # Should show the DOI link
    assert "10.5281/zenodo.1234567" in result
    assert "https://doi.org/10.5281/zenodo.1234567" in result

    # Should NOT show sandbox indicator for production DOI
    assert "(sandbox)" not in result.lower()

    # Should show registered via Zenodo
    assert "Registered via Zenodo" in result or "zenodo" in result.lower()


@pytest.mark.asyncio
async def test_doi_badge_minted_sandbox(jinja_env):
    """Test DOI badge shows sandbox indicator for sandbox DOIs."""
    template = jinja_env.get_template("components/doi_badge.html")

    # Sandbox DOIs use 10.5072 prefix
    result = template.module.doi_badge(doi="10.5072/zenodo.7654321", doi_status="minted")

    # Should show the DOI link
    assert "10.5072/zenodo.7654321" in result

    # Should show sandbox indicator
    assert "sandbox" in result.lower()


@pytest.mark.asyncio
async def test_doi_badge_pending(jinja_env):
    """Test DOI badge shows pending state correctly."""
    template = jinja_env.get_template("components/doi_badge.html")

    result = template.module.doi_badge(doi=None, doi_status="pending")

    # Should show pending message
    assert "progress" in result.lower() or "pending" in result.lower()

    # Should not show any DOI link
    assert "https://doi.org/" not in result
    assert "10.5281" not in result and "10.5072" not in result


@pytest.mark.asyncio
async def test_doi_badge_failed(jinja_env):
    """Test DOI badge shows failed state correctly."""
    template = jinja_env.get_template("components/doi_badge.html")

    result = template.module.doi_badge(doi=None, doi_status="failed")

    # Should show failure message
    assert "failed" in result.lower()

    # Should suggest contacting support
    assert "support" in result.lower() or "contact" in result.lower()

    # Should not show any DOI link
    assert "https://doi.org/" not in result


@pytest.mark.asyncio
async def test_doi_badge_no_doi_status(jinja_env):
    """Test DOI badge returns empty when no DOI status."""
    template = jinja_env.get_template("components/doi_badge.html")

    result = template.module.doi_badge(doi=None, doi_status=None)

    # Should return empty or minimal content
    assert result.strip() == "" or len(result.strip()) < 10


@pytest.mark.asyncio
async def test_doi_badge_compact_mode(jinja_env):
    """Test DOI badge compact mode for dashboard cards."""
    template = jinja_env.get_template("components/doi_badge.html")

    result_compact = template.module.doi_badge(
        doi="10.5281/zenodo.1234567", doi_status="minted", compact=True
    )

    result_full = template.module.doi_badge(
        doi="10.5281/zenodo.1234567", doi_status="minted", compact=False
    )

    # Should show DOI in compact form
    assert "10.5281/zenodo.1234567" in result_compact

    # Compact should be shorter than full version
    assert len(result_compact) < len(result_full)


@pytest.mark.asyncio
async def test_doi_badge_compact_pending(jinja_env):
    """Test DOI badge compact mode shows pending state."""
    template = jinja_env.get_template("components/doi_badge.html")

    result = template.module.doi_badge(doi=None, doi_status="pending", compact=True)

    # Should show short pending indicator
    assert "doi" in result.lower()
    assert "..." in result or "pending" in result.lower()


@pytest.mark.asyncio
async def test_doi_badge_compact_failed(jinja_env):
    """Test DOI badge compact mode shows failed state."""
    template = jinja_env.get_template("components/doi_badge.html")

    result = template.module.doi_badge(doi=None, doi_status="failed", compact=True)

    # Should show short failure indicator
    assert "doi" in result.lower()
    assert "failed" in result.lower() or "error" in result.lower()
