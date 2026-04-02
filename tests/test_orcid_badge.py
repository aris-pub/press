"""Tests for ORCID badge display on scroll pages."""

import json

import pytest
import pytest_asyncio

from tests.conftest import create_content_addressable_scroll


@pytest_asyncio.fixture
async def user_with_orcid(test_db):
    """Create a test user with an ORCID iD."""
    from app.auth.utils import get_password_hash
    from app.models.user import User

    user = User(
        email="orcid-author@example.com",
        password_hash=get_password_hash("password123"),
        display_name="ORCID Author",
        email_verified=True,
        orcid_id="0000-0002-1234-5678",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def user_without_orcid(test_db):
    """Create a test user without an ORCID iD."""
    from app.auth.utils import get_password_hash
    from app.models.user import User

    user = User(
        email="no-orcid@example.com",
        password_hash=get_password_hash("password123"),
        display_name="No ORCID Author",
        email_verified=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def scroll_with_orcid_user(test_db, user_with_orcid, test_subject):
    """Create a published scroll owned by a user with ORCID."""
    return await create_content_addressable_scroll(
        test_db,
        user_with_orcid,
        test_subject,
        title="ORCID Test Paper",
        authors="ORCID Author",
    )


@pytest_asyncio.fixture
async def scroll_without_orcid_user(test_db, user_without_orcid, test_subject):
    """Create a published scroll owned by a user without ORCID."""
    return await create_content_addressable_scroll(
        test_db,
        user_without_orcid,
        test_subject,
        title="No ORCID Test Paper",
        authors="No ORCID Author",
    )


@pytest.mark.asyncio
class TestOrcidBadgeOnScrollPage:
    """Test ORCID badge visibility in the metadata-authors section."""

    async def test_shows_orcid_badge_when_user_has_orcid(self, client, scroll_with_orcid_user):
        resp = await client.get(f"/scroll/{scroll_with_orcid_user.url_hash}")
        assert resp.status_code == 200
        html = resp.text
        assert "https://orcid.org/0000-0002-1234-5678" in html

    async def test_no_orcid_badge_when_user_has_no_orcid(self, client, scroll_without_orcid_user):
        resp = await client.get(f"/scroll/{scroll_without_orcid_user.url_hash}")
        assert resp.status_code == 200
        html = resp.text
        assert "orcid.org" not in html

    async def test_orcid_badge_links_to_correct_profile(self, client, scroll_with_orcid_user):
        resp = await client.get(f"/scroll/{scroll_with_orcid_user.url_hash}")
        html = resp.text
        assert 'href="https://orcid.org/0000-0002-1234-5678"' in html


@pytest.mark.asyncio
class TestOrcidScholarMeta:
    """Test citation_author_orcid meta tag in Google Scholar metadata."""

    async def test_scholar_meta_includes_orcid(self, client, scroll_with_orcid_user):
        resp = await client.get(f"/scroll/{scroll_with_orcid_user.url_hash}")
        html = resp.text
        assert 'name="citation_author_orcid"' in html
        assert 'content="https://orcid.org/0000-0002-1234-5678"' in html

    async def test_scholar_meta_no_orcid_when_absent(self, client, scroll_without_orcid_user):
        resp = await client.get(f"/scroll/{scroll_without_orcid_user.url_hash}")
        html = resp.text
        assert "citation_author_orcid" not in html


@pytest.mark.asyncio
class TestOrcidJsonLd:
    """Test sameAs in JSON-LD structured data for ORCID."""

    async def test_jsonld_includes_sameas_for_orcid(self, client, scroll_with_orcid_user):
        resp = await client.get(f"/scroll/{scroll_with_orcid_user.url_hash}")
        html = resp.text
        # Extract JSON-LD block
        start = html.index('type="application/ld+json">')
        start = html.index("{", start)
        end = html.index("</script>", start)
        ld = json.loads(html[start:end])

        # The first author should have sameAs with ORCID URL
        author = ld["author"][0]
        assert author["sameAs"] == "https://orcid.org/0000-0002-1234-5678"

    async def test_jsonld_no_sameas_when_no_orcid(self, client, scroll_without_orcid_user):
        resp = await client.get(f"/scroll/{scroll_without_orcid_user.url_hash}")
        html = resp.text
        start = html.index('type="application/ld+json">')
        start = html.index("{", start)
        end = html.index("</script>", start)
        ld = json.loads(html[start:end])

        author = ld["author"][0]
        assert "sameAs" not in author
