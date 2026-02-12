"""Tests for email verification banner component."""

from jinja2 import Environment, FileSystemLoader
import pytest


@pytest.fixture
def jinja_env():
    """Create Jinja2 environment for testing components."""
    return Environment(loader=FileSystemLoader("app/templates"))


@pytest.mark.asyncio
async def test_verification_banner_renders_with_basic_content(jinja_env):
    """Test verification banner renders with correct basic structure."""
    template = jinja_env.get_template("components/verification_banner.html")

    result = template.module.verification_banner()

    # Should contain verification-related text
    assert "verify" in result.lower() or "verification" in result.lower()
    assert "email" in result.lower()


@pytest.mark.asyncio
async def test_verification_banner_has_warning_icon(jinja_env):
    """Test verification banner includes a warning icon."""
    template = jinja_env.get_template("components/verification_banner.html")

    result = template.module.verification_banner()

    # Should have SVG icon
    assert "<svg" in result
    assert "viewBox" in result


@pytest.mark.asyncio
async def test_verification_banner_has_resend_action(jinja_env):
    """Test verification banner includes resend verification action."""
    template = jinja_env.get_template("components/verification_banner.html")

    result = template.module.verification_banner()

    # Should have link or form to resend verification
    assert "resend" in result.lower()
    assert "/resend-verification" in result


@pytest.mark.asyncio
async def test_verification_banner_uses_htmx_form(jinja_env):
    """Test verification banner uses HTMX form for resend action."""
    template = jinja_env.get_template("components/verification_banner.html")

    result = template.module.verification_banner()

    # Should use HTMX
    assert "hx-post" in result
    assert 'hx-post="/resend-verification"' in result


@pytest.mark.asyncio
async def test_verification_banner_has_proper_styling_classes(jinja_env):
    """Test verification banner has consistent styling classes."""
    template = jinja_env.get_template("components/verification_banner.html")

    result = template.module.verification_banner()

    # Should use consistent class naming
    assert "verification-banner" in result
    # Should have warning color scheme
    assert "banner" in result.lower()


@pytest.mark.asyncio
async def test_verification_banner_has_descriptive_message(jinja_env):
    """Test verification banner explains why verification is needed."""
    template = jinja_env.get_template("components/verification_banner.html")

    result = template.module.verification_banner()

    # Should explain the need to verify
    assert len(result) > 100  # Should have substantial content
    # Should mention features or access
    assert "features" in result.lower() or "access" in result.lower()


@pytest.mark.asyncio
async def test_verification_banner_has_action_button(jinja_env):
    """Test verification banner has a clear action button."""
    template = jinja_env.get_template("components/verification_banner.html")

    result = template.module.verification_banner()

    # Should have a button element
    assert "<button" in result
    assert "type=\"submit\"" in result or "type='submit'" in result


@pytest.mark.asyncio
async def test_verification_banner_accessible_markup(jinja_env):
    """Test verification banner uses accessible HTML."""
    template = jinja_env.get_template("components/verification_banner.html")

    result = template.module.verification_banner()

    # Icon should have aria-hidden or role
    assert 'aria-hidden="true"' in result or 'role=' in result
    # Should have semantic heading
    assert "<h3" in result or "<h2" in result or "<strong" in result
