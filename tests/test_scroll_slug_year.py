"""Tests for slug and publication_year fields on Scroll model."""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.models.scroll import Scroll, Subject
from app.models.user import User
from app.utils.slug import slugify_title


@pytest_asyncio.fixture
async def subject(test_db):
    subj = Subject(name="Physics", description="Physics research")
    test_db.add(subj)
    await test_db.commit()
    await test_db.refresh(subj)
    return subj


@pytest_asyncio.fixture
async def user(test_db):
    from app.auth.utils import get_password_hash

    u = User(
        email="slug-test@example.com",
        password_hash=get_password_hash("testpass123"),
        display_name="Slug Tester",
        email_verified=True,
    )
    test_db.add(u)
    await test_db.commit()
    await test_db.refresh(u)
    return u


def _make_scroll(user, subject, **overrides):
    defaults = dict(
        title="Quantum Entanglement in Many-Body Systems",
        authors="A. Physicist",
        abstract="We study entanglement.",
        keywords=[],
        html_content="<h1>Paper</h1>",
        license="cc-by-4.0",
        content_hash=uuid.uuid4().hex,
        url_hash=uuid.uuid4().hex[:12],
        status="published",
        user_id=user.id,
        subject_id=subject.id,
        published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Scroll(**defaults)


class TestSlugAndYearColumns:
    """Test that slug and publication_year columns work correctly."""

    @pytest.mark.asyncio
    async def test_slug_nullable(self, test_db, user, subject):
        scroll = _make_scroll(user, subject, slug=None, publication_year=None)
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)
        assert scroll.slug is None
        assert scroll.publication_year is None

    @pytest.mark.asyncio
    async def test_slug_and_year_stored(self, test_db, user, subject):
        scroll = _make_scroll(
            user, subject, slug="quantum-entanglement-many-body", publication_year=2026
        )
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)
        assert scroll.slug == "quantum-entanglement-many-body"
        assert scroll.publication_year == 2026

    @pytest.mark.asyncio
    async def test_slug_max_length_60(self, test_db, user, subject):
        long_slug = "a" * 60
        scroll = _make_scroll(user, subject, slug=long_slug, publication_year=2026)
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)
        assert scroll.slug == long_slug


class TestCanonicalUrl:
    """Test the canonical_url property."""

    @pytest.mark.asyncio
    async def test_canonical_url_with_both(self, test_db, user, subject):
        scroll = _make_scroll(
            user, subject, slug="quantum-entanglement", publication_year=2026
        )
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)
        assert scroll.canonical_url == "/2026/quantum-entanglement"

    @pytest.mark.asyncio
    async def test_canonical_url_falls_back_without_slug(self, test_db, user, subject):
        scroll = _make_scroll(user, subject, slug=None, publication_year=2026)
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)
        assert scroll.canonical_url == scroll.permanent_url

    @pytest.mark.asyncio
    async def test_canonical_url_falls_back_without_year(self, test_db, user, subject):
        scroll = _make_scroll(user, subject, slug="some-slug", publication_year=None)
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)
        assert scroll.canonical_url == scroll.permanent_url

    @pytest.mark.asyncio
    async def test_canonical_url_falls_back_without_both(self, test_db, user, subject):
        scroll = _make_scroll(user, subject, slug=None, publication_year=None)
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)
        assert scroll.canonical_url == scroll.permanent_url
