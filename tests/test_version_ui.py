"""Tests for reader-facing version UI elements on the scroll page.

Tests that:
- Version indicator shows correct label (e.g. 'v2 (latest)' or 'v1 of 3')
- Version selector shows links for all versions
- Old-version banner appears only when viewing a non-latest version
- Version history in info modal lists all versions with dates and links
- Canonical link tag always points to /{year}/{slug}
- Single-version scrolls do NOT show version UI
"""

from datetime import datetime, timezone
import uuid

import pytest
import pytest_asyncio

from app.models.scroll import Scroll, Subject
from app.models.user import User


@pytest_asyncio.fixture
async def subject(test_db):
    subj = Subject(name="Mathematics", description="Mathematics research")
    test_db.add(subj)
    await test_db.commit()
    await test_db.refresh(subj)
    return subj


@pytest_asyncio.fixture
async def user(test_db):
    from app.auth.utils import get_password_hash

    u = User(
        email="version-ui-test@example.com",
        password_hash=get_password_hash("testpass123"),
        display_name="Version UI Tester",
        email_verified=True,
    )
    test_db.add(u)
    await test_db.commit()
    await test_db.refresh(u)
    return u


async def _create_versioned_scrolls(test_db, user, subject, num_versions=3):
    """Create multiple versions of the same scroll."""
    series_id = uuid.uuid4()
    scrolls = []
    for v in range(1, num_versions + 1):
        scroll = Scroll(
            title="Topology of Manifolds",
            authors="A. Mathematician",
            abstract="We study topology.",
            keywords=[],
            html_content=f"<h1>Paper v{v}</h1>",
            license="cc-by-4.0",
            content_hash=uuid.uuid4().hex,
            url_hash=f"hash-v{v}-{uuid.uuid4().hex[:6]}",
            status="published",
            user_id=user.id,
            subject_id=subject.id,
            published_at=datetime(2026, v, 15, tzinfo=timezone.utc),
            slug="topology-of-manifolds",
            publication_year=2026,
            version=v,
            scroll_series_id=series_id,
        )
        test_db.add(scroll)
        scrolls.append(scroll)
    await test_db.commit()
    for s in scrolls:
        await test_db.refresh(s)
    return scrolls


async def _create_single_scroll(test_db, user, subject):
    """Create a single-version scroll (no series)."""
    scroll = Scroll(
        title="Solo Paper",
        authors="B. Researcher",
        abstract="A single version paper.",
        keywords=[],
        html_content="<h1>Solo</h1>",
        license="cc-by-4.0",
        content_hash=uuid.uuid4().hex,
        url_hash=f"solo-{uuid.uuid4().hex[:6]}",
        status="published",
        user_id=user.id,
        subject_id=subject.id,
        published_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
        slug="solo-paper",
        publication_year=2026,
        version=1,
        scroll_series_id=uuid.uuid4(),
    )
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)
    return scroll


class TestVersionIndicator:
    """Version indicator in metadata section."""

    @pytest.mark.asyncio
    async def test_latest_version_shows_label(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds")
        assert response.status_code == 200
        assert "v3 (latest)" in response.text

    @pytest.mark.asyncio
    async def test_old_version_shows_label(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds/v1")
        assert response.status_code == 200
        assert "v1 of 3" in response.text

    @pytest.mark.asyncio
    async def test_single_version_hides_indicator(self, client, test_db, user, subject):
        await _create_single_scroll(test_db, user, subject)
        response = await client.get("/2026/solo-paper")
        assert response.status_code == 200
        assert 'class="version-indicator"' not in response.text


class TestVersionSelector:
    """Version selector links in metadata."""

    @pytest.mark.asyncio
    async def test_selector_shows_all_versions(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds")
        assert response.status_code == 200
        # v1 and v2 should be links
        assert "/2026/topology-of-manifolds/v1" in response.text
        assert "/2026/topology-of-manifolds/v2" in response.text
        # v3 (current) should be a span, not a link
        assert 'class="version-current"' in response.text

    @pytest.mark.asyncio
    async def test_selector_highlights_current_version(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds/v2")
        assert response.status_code == 200
        # v2 should be the current (non-link) version
        assert 'class="version-current">v2</span>' in response.text
        # v1 and v3 should be links
        assert "/2026/topology-of-manifolds/v1" in response.text
        assert "/2026/topology-of-manifolds/v3" in response.text

    @pytest.mark.asyncio
    async def test_single_version_hides_selector(self, client, test_db, user, subject):
        await _create_single_scroll(test_db, user, subject)
        response = await client.get("/2026/solo-paper")
        assert response.status_code == 200
        assert 'class="version-selector"' not in response.text


class TestOldVersionBanner:
    """Banner shown when viewing a non-latest version."""

    @pytest.mark.asyncio
    async def test_banner_shown_on_old_version(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds/v1")
        assert response.status_code == 200
        assert 'class="old-version-banner"' in response.text
        assert "You are viewing v1 of this scroll" in response.text
        assert "View latest (v3)" in response.text
        assert 'href="/2026/topology-of-manifolds"' in response.text

    @pytest.mark.asyncio
    async def test_banner_hidden_on_latest_version(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds")
        assert response.status_code == 200
        assert 'class="old-version-banner"' not in response.text

    @pytest.mark.asyncio
    async def test_banner_hidden_on_latest_version_explicit(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds/v3")
        assert response.status_code == 200
        assert 'class="old-version-banner"' not in response.text


class TestVersionHistoryModal:
    """Version history section in the info modal."""

    @pytest.mark.asyncio
    async def test_version_history_lists_all_versions(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds")
        assert response.status_code == 200
        assert 'class="version-history"' in response.text
        assert "Version History" in response.text
        # All versions should be listed with links
        assert "/2026/topology-of-manifolds/v1" in response.text
        assert "/2026/topology-of-manifolds/v2" in response.text
        # Dates should appear (formatted)
        assert "January 15, 2026" in response.text
        assert "February 15, 2026" in response.text
        assert "March 15, 2026" in response.text

    @pytest.mark.asyncio
    async def test_version_history_marks_latest(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds")
        assert response.status_code == 200
        assert "(latest)" in response.text

    @pytest.mark.asyncio
    async def test_single_version_hides_history(self, client, test_db, user, subject):
        await _create_single_scroll(test_db, user, subject)
        response = await client.get("/2026/solo-paper")
        assert response.status_code == 200
        assert 'class="version-history"' not in response.text


class TestCanonicalLinkTag:
    """Canonical link tag always points to /{year}/{slug}."""

    @pytest.mark.asyncio
    async def test_canonical_on_latest(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds")
        assert response.status_code == 200
        assert 'rel="canonical"' in response.text
        assert "/2026/topology-of-manifolds" in response.text

    @pytest.mark.asyncio
    async def test_canonical_on_old_version(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds/v1")
        assert response.status_code == 200
        # Canonical should point to the canonical URL (no version suffix)
        # Check that the canonical link does NOT include /v1
        import re
        canonical_match = re.search(r'<link rel="canonical" href="([^"]+)"', response.text)
        assert canonical_match is not None
        canonical_url = canonical_match.group(1)
        assert canonical_url.endswith("/2026/topology-of-manifolds")
        assert "/v1" not in canonical_url
