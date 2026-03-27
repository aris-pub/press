"""Tests for version-aware URL routing.

Tests that:
- /{year}/{slug} resolves to the latest published version
- /{year}/{slug}/v{N} resolves to a specific version
- 404s are returned for non-existent versions
- Index/listing pages show only the latest version per series
- /scroll/{url_hash} still resolves to the exact version (unchanged)
- Version metadata is passed to the template context
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
        email="version-test@example.com",
        password_hash=get_password_hash("testpass123"),
        display_name="Version Tester",
        email_verified=True,
    )
    test_db.add(u)
    await test_db.commit()
    await test_db.refresh(u)
    return u


def _make_scroll(user, subject, version=1, **overrides):
    series_id = overrides.pop("scroll_series_id", uuid.uuid4())
    defaults = dict(
        title="Topology of Manifolds",
        authors="A. Mathematician",
        abstract="We study topology.",
        keywords=[],
        html_content="<h1>Paper</h1>",
        license="cc-by-4.0",
        content_hash=uuid.uuid4().hex,
        url_hash=uuid.uuid4().hex[:12],
        status="published",
        user_id=user.id,
        subject_id=subject.id,
        published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        slug="topology-of-manifolds",
        publication_year=2026,
        version=version,
        scroll_series_id=series_id,
    )
    defaults.update(overrides)
    return Scroll(**defaults)


async def _create_versioned_scrolls(test_db, user, subject, num_versions=3):
    """Create multiple versions of the same scroll (same series_id, slug, year)."""
    series_id = uuid.uuid4()
    scrolls = []
    for v in range(1, num_versions + 1):
        scroll = _make_scroll(
            user,
            subject,
            version=v,
            scroll_series_id=series_id,
            content_hash=uuid.uuid4().hex,
            url_hash=f"hash-v{v}-{uuid.uuid4().hex[:6]}",
            html_content=f"<h1>Paper v{v}</h1>",
        )
        test_db.add(scroll)
        scrolls.append(scroll)
    await test_db.commit()
    for s in scrolls:
        await test_db.refresh(s)
    return scrolls


class TestYearSlugResolvesLatest:
    """/{year}/{slug} should resolve to the latest published version."""

    @pytest.mark.asyncio
    async def test_returns_latest_version(self, client, test_db, user, subject):
        scrolls = await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds")
        assert response.status_code == 200
        # The latest version (v3) content should be rendered
        assert "hash-v3" in response.text or scrolls[2].url_hash in response.text

    @pytest.mark.asyncio
    async def test_returns_404_when_no_published_versions(self, client, test_db, user, subject):
        response = await client.get("/2026/nonexistent-scroll")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_single_version_works(self, client, test_db, user, subject):
        series_id = uuid.uuid4()
        scroll = _make_scroll(
            user, subject, version=1, scroll_series_id=series_id,
            url_hash="single-ver-hash",
        )
        test_db.add(scroll)
        await test_db.commit()
        response = await client.get("/2026/topology-of-manifolds")
        assert response.status_code == 200


class TestVersionSpecificRoute:
    """/{year}/{slug}/v{N} should resolve to a specific version."""

    @pytest.mark.asyncio
    async def test_specific_version_v1(self, client, test_db, user, subject):
        scrolls = await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds/v1")
        assert response.status_code == 200
        assert scrolls[0].url_hash in response.text

    @pytest.mark.asyncio
    async def test_specific_version_v2(self, client, test_db, user, subject):
        scrolls = await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds/v2")
        assert response.status_code == 200
        assert scrolls[1].url_hash in response.text

    @pytest.mark.asyncio
    async def test_specific_version_v3(self, client, test_db, user, subject):
        scrolls = await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds/v3")
        assert response.status_code == 200
        assert scrolls[2].url_hash in response.text

    @pytest.mark.asyncio
    async def test_nonexistent_version_returns_404(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=2)
        response = await client.get("/2026/topology-of-manifolds/v99")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_nonexistent_slug_returns_404(self, client, test_db, user, subject):
        response = await client.get("/2026/no-such-scroll/v1")
        assert response.status_code == 404


class TestUrlHashRouteUnchanged:
    """/scroll/{url_hash} should still resolve to the exact version."""

    @pytest.mark.asyncio
    async def test_url_hash_returns_exact_version(self, client, test_db, user, subject):
        scrolls = await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        # Request v1 by its url_hash
        response = await client.get(f"/scroll/{scrolls[0].url_hash}")
        assert response.status_code == 200
        assert scrolls[0].url_hash in response.text


class TestVersionsPassedToTemplate:
    """Version metadata should be passed to the template context."""

    @pytest.mark.asyncio
    async def test_versions_list_in_context(self, client, test_db, user, subject):
        scrolls = await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/2026/topology-of-manifolds")
        assert response.status_code == 200
        # The hidden version-data div should contain all version url_hashes
        assert 'id="version-data"' in response.text
        for s in scrolls:
            assert s.url_hash in response.text
        assert 'data-latest-version="3"' in response.text
        assert 'data-is-latest="true"' in response.text

    @pytest.mark.asyncio
    async def test_version_specific_also_gets_versions_list(self, client, test_db, user, subject):
        scrolls = await _create_versioned_scrolls(test_db, user, subject, num_versions=2)
        response = await client.get("/2026/topology-of-manifolds/v1")
        assert response.status_code == 200
        assert 'id="version-data"' in response.text
        for s in scrolls:
            assert s.url_hash in response.text
        assert 'data-is-latest="false"' in response.text


class TestIndexShowsLatestOnly:
    """Index/listing pages should show only the latest version per series."""

    @pytest.mark.asyncio
    async def test_landing_page_no_duplicates(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/")
        assert response.status_code == 200
        # Only one scroll card should appear (the latest), not three
        assert response.text.count("Topology of Manifolds") == 1
        # The version shown should be v3
        assert ">v3<" in response.text
        assert ">v1<" not in response.text
        assert ">v2<" not in response.text

    @pytest.mark.asyncio
    async def test_partials_scrolls_no_duplicates(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/partials/scrolls")
        assert response.status_code == 200
        assert response.text.count("Topology of Manifolds") == 1

    @pytest.mark.asyncio
    async def test_api_scrolls_no_duplicates(self, client, test_db, user, subject):
        scrolls = await _create_versioned_scrolls(test_db, user, subject, num_versions=3)
        response = await client.get("/api/scrolls")
        assert response.status_code == 200
        data = response.json()
        url_hashes = [s["url_hash"] for s in data["scrolls"]]
        assert scrolls[2].url_hash in url_hashes
        assert scrolls[0].url_hash not in url_hashes
        assert scrolls[1].url_hash not in url_hashes

    @pytest.mark.asyncio
    async def test_search_no_duplicates(self, client, test_db, user, subject):
        await _create_versioned_scrolls(test_db, user, subject, num_versions=2)
        response = await client.get("/search?q=Mathematician")
        assert response.status_code == 200
        # Only one result should appear (search highlights terms with <mark>)
        assert response.text.count("A. Mathematician") == 1


class TestCanonicalUrlLinks:
    """Scroll cards on listing pages should link to /{year}/{slug}, not /scroll/{hash}."""

    @pytest.mark.asyncio
    async def test_landing_page_links_use_canonical_url(self, client, test_db, user, subject):
        scrolls = await _create_versioned_scrolls(test_db, user, subject, num_versions=2)
        response = await client.get("/")
        assert response.status_code == 200
        assert "/2026/topology-of-manifolds" in response.text
        # The card link should NOT use /scroll/<hash>
        for s in scrolls:
            assert f"/scroll/{s.url_hash}" not in response.text

    @pytest.mark.asyncio
    async def test_search_results_link_use_canonical_url(self, client, test_db, user, subject):
        scrolls = await _create_versioned_scrolls(test_db, user, subject, num_versions=1)
        response = await client.get("/search?q=Topology")
        assert response.status_code == 200
        assert "/2026/topology-of-manifolds" in response.text
        for s in scrolls:
            assert f"/scroll/{s.url_hash}" not in response.text
