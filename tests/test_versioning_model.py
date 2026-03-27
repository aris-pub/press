"""Tests for scroll versioning data model: scroll_series_id and version_url."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError

from app.models.scroll import Scroll


@pytest_asyncio.fixture
async def published_scroll(test_db, test_user, test_subject):
    """Create a published scroll with slug and publication_year."""
    from app.storage.content_processing import generate_permanent_url

    url_hash, content_hash, _ = await generate_permanent_url(test_db, "<h1>Version 1</h1>")
    scroll = Scroll(
        title="My Research Paper",
        authors="Jane Doe",
        abstract="A groundbreaking study.",
        keywords=["science"],
        html_content="<h1>Version 1</h1>",
        license="cc-by-4.0",
        content_hash=content_hash,
        url_hash=url_hash,
        status="published",
        user_id=test_user.id,
        subject_id=test_subject.id,
        slug="my-research-paper",
        publication_year=2026,
        version=1,
    )
    scroll.publish()
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)
    return scroll


class TestScrollSeriesId:
    """Tests for the scroll_series_id column."""

    @pytest.mark.asyncio
    async def test_scroll_series_id_defaults_to_none(self, test_db, test_user, test_subject):
        """New scrolls should have scroll_series_id=None by default."""
        from app.storage.content_processing import generate_permanent_url

        url_hash, content_hash, _ = await generate_permanent_url(test_db, "<h1>Test</h1>")
        scroll = Scroll(
            title="Test",
            authors="Author",
            abstract="Abstract",
            html_content="<h1>Test</h1>",
            license="cc-by-4.0",
            content_hash=content_hash,
            url_hash=url_hash,
            status="published",
            user_id=test_user.id,
            subject_id=test_subject.id,
        )
        scroll.publish()
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)

        assert scroll.scroll_series_id is None

    @pytest.mark.asyncio
    async def test_two_scrolls_same_series_different_versions(
        self, test_db, test_user, test_subject
    ):
        """Two scrolls can share the same scroll_series_id with different versions."""
        from app.storage.content_processing import generate_permanent_url

        series_id = uuid.uuid4()

        url_hash1, content_hash1, _ = await generate_permanent_url(test_db, "<h1>V1</h1>")
        v1 = Scroll(
            title="Paper",
            authors="Author",
            abstract="Abstract",
            html_content="<h1>V1</h1>",
            license="cc-by-4.0",
            content_hash=content_hash1,
            url_hash=url_hash1,
            status="published",
            user_id=test_user.id,
            subject_id=test_subject.id,
            slug="paper",
            publication_year=2026,
            version=1,
            scroll_series_id=series_id,
        )
        v1.publish()
        test_db.add(v1)
        await test_db.commit()

        url_hash2, content_hash2, _ = await generate_permanent_url(test_db, "<h1>V2</h1>")
        v2 = Scroll(
            title="Paper",
            authors="Author",
            abstract="Abstract v2",
            html_content="<h1>V2</h1>",
            license="cc-by-4.0",
            content_hash=content_hash2,
            url_hash=url_hash2,
            status="published",
            user_id=test_user.id,
            subject_id=test_subject.id,
            slug="paper",
            publication_year=2026,
            version=2,
            scroll_series_id=series_id,
        )
        v2.publish()
        test_db.add(v2)
        await test_db.commit()
        await test_db.refresh(v1)
        await test_db.refresh(v2)

        assert v1.scroll_series_id == v2.scroll_series_id == series_id
        assert v1.version == 1
        assert v2.version == 2

    @pytest.mark.asyncio
    async def test_scroll_series_id_accepts_uuid(self, test_db, test_user, test_subject):
        """scroll_series_id should accept and store a UUID."""
        from app.storage.content_processing import generate_permanent_url

        series_id = uuid.uuid4()
        url_hash, content_hash, _ = await generate_permanent_url(test_db, "<h1>With Series</h1>")
        scroll = Scroll(
            title="Test",
            authors="Author",
            abstract="Abstract",
            html_content="<h1>With Series</h1>",
            license="cc-by-4.0",
            content_hash=content_hash,
            url_hash=url_hash,
            status="published",
            user_id=test_user.id,
            subject_id=test_subject.id,
            scroll_series_id=series_id,
        )
        scroll.publish()
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)

        assert scroll.scroll_series_id == series_id


class TestUniqueConstraintYearSlugVersion:
    """Tests for the unique constraint on (publication_year, slug, version)."""

    @pytest.mark.asyncio
    async def test_duplicate_year_slug_version_rejected(
        self, test_db, test_user, test_subject, published_scroll
    ):
        """Two published scrolls with same (year, slug, version) should fail."""
        from app.storage.content_processing import generate_permanent_url

        url_hash, content_hash, _ = await generate_permanent_url(test_db, "<h1>Duplicate</h1>")
        duplicate = Scroll(
            title="Duplicate",
            authors="Author",
            abstract="Abstract",
            html_content="<h1>Duplicate</h1>",
            license="cc-by-4.0",
            content_hash=content_hash,
            url_hash=url_hash,
            status="published",
            user_id=test_user.id,
            subject_id=test_subject.id,
            slug=published_scroll.slug,
            publication_year=published_scroll.publication_year,
            version=published_scroll.version,
        )
        duplicate.publish()
        test_db.add(duplicate)

        with pytest.raises(IntegrityError):
            await test_db.commit()

    @pytest.mark.asyncio
    async def test_same_year_slug_different_version_allowed(
        self, test_db, test_user, test_subject, published_scroll
    ):
        """Same (year, slug) with different version should succeed."""
        from app.storage.content_processing import generate_permanent_url

        url_hash, content_hash, _ = await generate_permanent_url(test_db, "<h1>Version 2</h1>")
        v2 = Scroll(
            title="My Research Paper v2",
            authors="Jane Doe",
            abstract="Updated study.",
            html_content="<h1>Version 2</h1>",
            license="cc-by-4.0",
            content_hash=content_hash,
            url_hash=url_hash,
            status="published",
            user_id=test_user.id,
            subject_id=test_subject.id,
            slug=published_scroll.slug,
            publication_year=published_scroll.publication_year,
            version=2,
        )
        v2.publish()
        test_db.add(v2)
        await test_db.commit()
        await test_db.refresh(v2)

        assert v2.version == 2
        assert v2.slug == published_scroll.slug


class TestVersionUrl:
    """Tests for the version_url property."""

    @pytest.mark.asyncio
    async def test_version_url_with_year_and_slug(self, published_scroll):
        """version_url should return /{year}/{slug}/v{version}."""
        assert published_scroll.version_url == "/2026/my-research-paper/v1"

    @pytest.mark.asyncio
    async def test_version_url_falls_back_to_permanent_url(self, test_db, test_user, test_subject):
        """version_url should fall back to permanent_url if no year/slug."""
        from app.storage.content_processing import generate_permanent_url

        url_hash, content_hash, _ = await generate_permanent_url(test_db, "<h1>No Slug</h1>")
        scroll = Scroll(
            title="No Slug Paper",
            authors="Author",
            abstract="Abstract",
            html_content="<h1>No Slug</h1>",
            license="cc-by-4.0",
            content_hash=content_hash,
            url_hash=url_hash,
            status="published",
            user_id=test_user.id,
            subject_id=test_subject.id,
        )
        scroll.publish()
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)

        assert scroll.version_url == scroll.permanent_url


class TestCanonicalUrlUnchanged:
    """Verify canonical_url property is not affected by versioning changes."""

    @pytest.mark.asyncio
    async def test_canonical_url_still_returns_year_slug(self, published_scroll):
        """canonical_url should still return /{year}/{slug} (no version)."""
        assert published_scroll.canonical_url == "/2026/my-research-paper"

    @pytest.mark.asyncio
    async def test_canonical_url_falls_back_to_permanent_url(
        self, test_db, test_user, test_subject
    ):
        """canonical_url should still fall back to permanent_url without year/slug."""
        from app.storage.content_processing import generate_permanent_url

        url_hash, content_hash, _ = await generate_permanent_url(test_db, "<h1>Fallback</h1>")
        scroll = Scroll(
            title="Fallback",
            authors="Author",
            abstract="Abstract",
            html_content="<h1>Fallback</h1>",
            license="cc-by-4.0",
            content_hash=content_hash,
            url_hash=url_hash,
            status="published",
            user_id=test_user.id,
            subject_id=test_subject.id,
        )
        scroll.publish()
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)

        assert scroll.canonical_url == scroll.permanent_url
