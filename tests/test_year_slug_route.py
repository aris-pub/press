"""Tests for GET /{year}/{slug} route."""

from datetime import datetime, timezone
import uuid

import pytest
import pytest_asyncio

from app.auth.utils import get_password_hash
from app.models.scroll import Scroll, Subject
from app.models.user import User


@pytest_asyncio.fixture
async def subject(test_db):
    subj = Subject(name="Physics", description="Physics research")
    test_db.add(subj)
    await test_db.commit()
    await test_db.refresh(subj)
    return subj


@pytest_asyncio.fixture
async def user(test_db):
    u = User(
        email="yearslug-test@example.com",
        password_hash=get_password_hash("testpass123"),
        display_name="Year Slug Tester",
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
        slug="quantum-entanglement-many-body",
        publication_year=2026,
    )
    defaults.update(overrides)
    return Scroll(**defaults)


class TestYearSlugRoute:
    """Test GET /{year}/{slug} route."""

    @pytest.mark.asyncio
    async def test_returns_published_scroll(self, client, test_db, user, subject):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)

        response = await client.get("/2026/quantum-entanglement-many-body")
        assert response.status_code == 200
        assert scroll.title in response.text

    @pytest.mark.asyncio
    async def test_404_when_not_found(self, client, test_db, user, subject):
        response = await client.get("/2026/nonexistent-slug")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_404_for_unpublished_scroll(self, client, test_db, user, subject):
        scroll = _make_scroll(user, subject, status="preview")
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get("/2026/quantum-entanglement-many-body")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_404_wrong_year(self, client, test_db, user, subject):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get("/2025/quantum-entanglement-many-body")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_404_wrong_slug(self, client, test_db, user, subject):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get("/2026/wrong-slug")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_iframe_src_uses_url_hash(self, client, test_db, user, subject):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)

        response = await client.get("/2026/quantum-entanglement-many-body")
        assert response.status_code == 200
        assert f"/scroll/{scroll.url_hash}/paper" in response.text
