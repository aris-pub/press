"""Tests for the publish flow for new versions (v2+) of scrolls."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import create_session, get_session
from app.models.scroll import Scroll, Subject
from app.models.user import User
from app.storage.content_processing import generate_permanent_url
from app.utils.slug import generate_unique_slug


async def _create_published_v1(
    db: AsyncSession,
    user: User,
    subject: Subject,
    title: str = "Neural Networks in Practice",
    html_content: str = "<h1>Version 1</h1><p>Original content</p>",
) -> Scroll:
    """Helper: create a fully published v1 scroll with series fields set."""
    url_hash, content_hash, _ = await generate_permanent_url(db, html_content)
    scroll = Scroll(
        user_id=user.id,
        subject_id=subject.id,
        title=title,
        authors="Jane Doe",
        abstract="An abstract about neural networks.",
        keywords=["neural", "networks"],
        html_content=html_content,
        license="cc-by-4.0",
        content_hash=content_hash,
        url_hash=url_hash,
        status="preview",
    )
    db.add(scroll)
    await db.commit()
    await db.refresh(scroll)

    scroll.publish()
    scroll.publication_year = scroll.published_at.year
    scroll.slug = await generate_unique_slug(db, scroll.title, scroll.publication_year)
    scroll.version = 1
    scroll.scroll_series_id = uuid.uuid4()
    await db.commit()
    await db.refresh(scroll)
    return scroll


@pytest.mark.asyncio
class TestUploadPageRevises:
    """GET /upload?revises={url_hash} -- pre-fill metadata from parent scroll."""

    async def test_revises_stores_session_and_prefills(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """When ?revises=<hash> is valid, session stores revises_scroll and form pre-fills."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)

        resp = await authenticated_client.get(
            f"/upload?revises={v1.url_hash}", follow_redirects=False
        )
        assert resp.status_code == 200

        # Session should have revises_scroll set
        session_id = authenticated_client.cookies.get("session_id")
        session = get_session(session_id)
        assert session.get("revises_scroll") == v1.url_hash

        # Template should contain pre-filled values from v1
        body = resp.text
        assert v1.title in body
        assert v1.authors in body
        assert v1.abstract in body

    async def test_revises_nonexistent_scroll_ignored(
        self, authenticated_client, test_user, test_db
    ):
        """If revises points to a nonexistent scroll, treat as normal upload."""
        resp = await authenticated_client.get(
            "/upload?revises=nonexistent123", follow_redirects=False
        )
        assert resp.status_code == 200

        session_id = authenticated_client.cookies.get("session_id")
        session = get_session(session_id)
        assert "revises_scroll" not in session

    async def test_revises_not_owner_rejected(
        self, authenticated_client, test_subject, test_db
    ):
        """Cannot revise a scroll owned by someone else."""
        from app.auth.utils import get_password_hash

        other_user = User(
            email="other@example.com",
            password_hash=get_password_hash("password123"),
            display_name="Other User",
            email_verified=True,
        )
        test_db.add(other_user)
        await test_db.commit()
        await test_db.refresh(other_user)

        v1 = await _create_published_v1(test_db, other_user, test_subject)

        resp = await authenticated_client.get(
            f"/upload?revises={v1.url_hash}", follow_redirects=False
        )
        assert resp.status_code == 200

        session_id = authenticated_client.cookies.get("session_id")
        session = get_session(session_id)
        assert "revises_scroll" not in session

    async def test_revises_unpublished_scroll_ignored(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """Cannot revise a scroll that is still in preview status."""
        url_hash, content_hash, _ = await generate_permanent_url(
            test_db, "<h1>Draft</h1>"
        )
        draft = Scroll(
            user_id=test_user.id,
            subject_id=test_subject.id,
            title="Draft Scroll",
            authors="Jane Doe",
            abstract="Abstract",
            keywords=[],
            html_content="<h1>Draft</h1>",
            license="cc-by-4.0",
            content_hash=content_hash,
            url_hash=url_hash,
            status="preview",
        )
        test_db.add(draft)
        await test_db.commit()
        await test_db.refresh(draft)

        resp = await authenticated_client.get(
            f"/upload?revises={draft.url_hash}", follow_redirects=False
        )
        assert resp.status_code == 200

        session_id = authenticated_client.cookies.get("session_id")
        session = get_session(session_id)
        assert "revises_scroll" not in session


@pytest.mark.asyncio
class TestPreviewVersionIndicator:
    """GET /preview/{url_hash} -- shows upcoming version number."""

    async def test_preview_shows_v2_indicator(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """Preview page should indicate this will be v2 when revises_scroll is in session."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)

        # Create a preview scroll (different content)
        url_hash, content_hash, _ = await generate_permanent_url(
            test_db, "<h1>Version 2</h1><p>Updated content</p>"
        )
        preview = Scroll(
            user_id=test_user.id,
            subject_id=test_subject.id,
            title="Neural Networks v2",
            authors="Jane Doe",
            abstract="Updated abstract",
            keywords=["neural"],
            html_content="<h1>Version 2</h1><p>Updated content</p>",
            license="cc-by-4.0",
            content_hash=content_hash,
            url_hash=url_hash,
            status="preview",
        )
        test_db.add(preview)
        await test_db.commit()
        await test_db.refresh(preview)

        # Set revises_scroll in session
        session_id = authenticated_client.cookies.get("session_id")
        session = get_session(session_id)
        session["revises_scroll"] = v1.url_hash

        resp = await authenticated_client.get(
            f"/preview/{preview.url_hash}", follow_redirects=False
        )
        assert resp.status_code == 200
        assert "v2" in resp.text

    async def test_preview_no_version_for_v1(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """Preview page should NOT show version indicator for normal v1 uploads."""
        url_hash, content_hash, _ = await generate_permanent_url(
            test_db, "<h1>Brand New</h1><p>First version</p>"
        )
        preview = Scroll(
            user_id=test_user.id,
            subject_id=test_subject.id,
            title="Brand New Paper",
            authors="Jane Doe",
            abstract="Abstract",
            keywords=[],
            html_content="<h1>Brand New</h1><p>First version</p>",
            license="cc-by-4.0",
            content_hash=content_hash,
            url_hash=url_hash,
            status="preview",
        )
        test_db.add(preview)
        await test_db.commit()
        await test_db.refresh(preview)

        resp = await authenticated_client.get(
            f"/preview/{preview.url_hash}", follow_redirects=False
        )
        assert resp.status_code == 200
        assert "will be published as v" not in resp.text


@pytest.mark.asyncio
class TestPublishVersioning:
    """POST /preview/{url_hash}/confirm -- version assignment for v2+."""

    async def _create_preview(
        self,
        db: AsyncSession,
        user: User,
        subject: Subject,
        html_content: str = "<h1>Version 2</h1><p>Updated content</p>",
    ) -> Scroll:
        url_hash, content_hash, _ = await generate_permanent_url(db, html_content)
        scroll = Scroll(
            user_id=user.id,
            subject_id=subject.id,
            title="Neural Networks v2",
            authors="Jane Doe",
            abstract="Updated abstract",
            keywords=["neural"],
            html_content=html_content,
            license="cc-by-4.0",
            content_hash=content_hash,
            url_hash=url_hash,
            status="preview",
        )
        db.add(scroll)
        await db.commit()
        await db.refresh(scroll)
        return scroll

    async def test_publish_v2_inherits_series(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """Publishing with revises_scroll in session sets correct version, series, slug."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)
        preview = await self._create_preview(test_db, test_user, test_subject)

        # Set revises_scroll in session
        session_id = authenticated_client.cookies.get("session_id")
        session = get_session(session_id)
        session["revises_scroll"] = v1.url_hash

        resp = await authenticated_client.post(
            f"/preview/{preview.url_hash}/confirm", follow_redirects=False
        )
        assert resp.status_code == 303

        await test_db.refresh(preview)
        assert preview.status == "published"
        assert preview.version == 2
        assert preview.scroll_series_id == v1.scroll_series_id
        assert preview.slug == v1.slug
        assert preview.publication_year == v1.publication_year

    async def test_publish_v1_normal_flow(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """Publishing without revises_scroll uses normal v1 flow."""
        preview = await self._create_preview(
            test_db, test_user, test_subject,
            html_content="<h1>Brand New</h1><p>First version</p>",
        )

        resp = await authenticated_client.post(
            f"/preview/{preview.url_hash}/confirm", follow_redirects=False
        )
        assert resp.status_code == 303

        await test_db.refresh(preview)
        assert preview.status == "published"
        assert preview.version == 1
        assert preview.scroll_series_id is not None
        assert preview.slug is not None
        assert preview.publication_year is not None

    async def test_publish_v3_increments_correctly(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """v3 after v2 should have version=3."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)

        # Create and publish v2
        v2_hash, v2_content_hash, _ = await generate_permanent_url(
            test_db, "<h1>V2 Content</h1><p>Version two</p>"
        )
        v2 = Scroll(
            user_id=test_user.id,
            subject_id=test_subject.id,
            title="Neural Networks v2",
            authors="Jane Doe",
            abstract="v2 abstract",
            keywords=[],
            html_content="<h1>V2 Content</h1><p>Version two</p>",
            license="cc-by-4.0",
            content_hash=v2_content_hash,
            url_hash=v2_hash,
            status="preview",
        )
        db = test_db
        db.add(v2)
        await db.commit()
        await db.refresh(v2)

        # Publish v2
        v2.publish()
        v2.version = 2
        v2.scroll_series_id = v1.scroll_series_id
        v2.slug = v1.slug
        v2.publication_year = v1.publication_year
        await db.commit()

        # Now create v3 preview
        v3_preview = await self._create_preview(
            test_db, test_user, test_subject,
            html_content="<h1>V3 Content</h1><p>Version three</p>",
        )

        session_id = authenticated_client.cookies.get("session_id")
        session = get_session(session_id)
        session["revises_scroll"] = v1.url_hash

        resp = await authenticated_client.post(
            f"/preview/{v3_preview.url_hash}/confirm", follow_redirects=False
        )
        assert resp.status_code == 303

        await test_db.refresh(v3_preview)
        assert v3_preview.version == 3
        assert v3_preview.scroll_series_id == v1.scroll_series_id

    async def test_publish_clears_revises_session(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """Session's revises_scroll is cleared after publishing."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)
        preview = await self._create_preview(test_db, test_user, test_subject)

        session_id = authenticated_client.cookies.get("session_id")
        session = get_session(session_id)
        session["revises_scroll"] = v1.url_hash

        await authenticated_client.post(
            f"/preview/{preview.url_hash}/confirm", follow_redirects=False
        )

        assert "revises_scroll" not in session

    async def test_publish_v2_own_url_hash(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """v2 gets its own unique url_hash and content_hash."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)
        preview = await self._create_preview(test_db, test_user, test_subject)

        session_id = authenticated_client.cookies.get("session_id")
        session = get_session(session_id)
        session["revises_scroll"] = v1.url_hash

        await authenticated_client.post(
            f"/preview/{preview.url_hash}/confirm", follow_redirects=False
        )

        await test_db.refresh(preview)
        assert preview.url_hash != v1.url_hash
        assert preview.content_hash != v1.content_hash


@pytest.mark.asyncio
class TestDuplicateContentHandling:
    """Duplicate content detection with version awareness."""

    async def test_same_content_same_series_allowed(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """Same content_hash within the same series should warn but allow (metadata-only update)."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)

        session_id = authenticated_client.cookies.get("session_id")
        session = get_session(session_id)
        session["revises_scroll"] = v1.url_hash

        # Upload same content as v1
        resp = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Updated Title Only",
                "authors": "Jane Doe",
                "subject_id": str(test_subject.id),
                "abstract": "Updated abstract only",
                "keywords": "neural,networks",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("paper.html", v1.html_content.encode(), "text/html")},
            follow_redirects=False,
        )
        # Should succeed (redirect to preview) rather than 422 error
        assert resp.status_code == 303 or resp.status_code == 200

    async def test_same_content_same_series_publish_succeeds(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """Full flow: upload same content as v1, then publish as v2 -- should succeed."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)

        session_id = authenticated_client.cookies.get("session_id")
        session = get_session(session_id)
        session["revises_scroll"] = v1.url_hash

        # Upload same content as v1
        resp = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Updated Title Only",
                "authors": "Jane Doe",
                "subject_id": str(test_subject.id),
                "abstract": "Updated abstract only",
                "keywords": "neural,networks",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("paper.html", v1.html_content.encode(), "text/html")},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        preview_url = resp.headers["location"]
        preview_url_hash = preview_url.split("/preview/")[1]

        # Now publish the preview
        resp = await authenticated_client.post(
            f"/preview/{preview_url_hash}/confirm", follow_redirects=False
        )
        assert resp.status_code == 303, f"Publish failed with {resp.status_code}: {resp.text[:500]}"

        # Verify v2 was published correctly
        result = await test_db.execute(
            select(Scroll).where(Scroll.url_hash == preview_url_hash)
        )
        v2 = result.scalar_one()
        assert v2.status == "published"
        assert v2.version == 2
        assert v2.scroll_series_id == v1.scroll_series_id
        assert v2.slug == v1.slug

    async def test_same_content_different_series_rejected(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """Same content_hash from a DIFFERENT series should still be rejected."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)

        # No revises_scroll in session -- normal upload
        resp = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Totally Different Paper",
                "authors": "John Smith",
                "subject_id": str(test_subject.id),
                "abstract": "Different abstract",
                "keywords": "",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("paper.html", v1.html_content.encode(), "text/html")},
            follow_redirects=False,
        )
        # Should be rejected (422 with error message)
        assert resp.status_code == 422
        assert "already been published" in resp.text


@pytest.mark.asyncio
class TestOwnershipValidation:
    """Only scroll owners can upload new versions."""

    async def test_non_owner_cannot_revise(
        self, client, test_subject, test_db
    ):
        """A different user cannot use revises for someone else's scroll."""
        from app.auth.utils import get_password_hash

        # Create owner and their scroll
        owner = User(
            email="owner@example.com",
            password_hash=get_password_hash("password123"),
            display_name="Owner",
            email_verified=True,
        )
        test_db.add(owner)
        await test_db.commit()
        await test_db.refresh(owner)

        v1 = await _create_published_v1(test_db, owner, test_subject)

        # Create a different user and authenticate as them
        other_user = User(
            email="other2@example.com",
            password_hash=get_password_hash("password123"),
            display_name="Other",
            email_verified=True,
        )
        test_db.add(other_user)
        await test_db.commit()
        await test_db.refresh(other_user)

        other_session_id = await create_session(test_db, other_user.id)
        client.cookies.set("session_id", other_session_id)

        resp = await client.get(
            f"/upload?revises={v1.url_hash}", follow_redirects=False
        )
        assert resp.status_code == 200

        session = get_session(other_session_id)
        assert "revises_scroll" not in session


@pytest.mark.asyncio
class TestNewVersionLink:
    """Published scroll page shows 'New Version' link to the scroll owner."""

    async def test_owner_sees_new_version_link(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """The scroll owner should see a 'New Version' link on the published scroll page."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)

        resp = await authenticated_client.get(
            f"/{v1.publication_year}/{v1.slug}", follow_redirects=False
        )
        assert resp.status_code == 200
        assert f"/upload?revises={v1.url_hash}" in resp.text
        assert "New Version" in resp.text

    async def test_non_owner_does_not_see_new_version_link(
        self, client, test_subject, test_db
    ):
        """A different user should NOT see the 'New Version' link."""
        from app.auth.utils import get_password_hash

        owner = User(
            email="owner3@example.com",
            password_hash=get_password_hash("password123"),
            display_name="Owner",
            email_verified=True,
        )
        test_db.add(owner)
        await test_db.commit()
        await test_db.refresh(owner)

        v1 = await _create_published_v1(test_db, owner, test_subject)

        other_user = User(
            email="viewer@example.com",
            password_hash=get_password_hash("password123"),
            display_name="Viewer",
            email_verified=True,
        )
        test_db.add(other_user)
        await test_db.commit()
        await test_db.refresh(other_user)

        other_session_id = await create_session(test_db, other_user.id)
        client.cookies.set("session_id", other_session_id)

        resp = await client.get(
            f"/{v1.publication_year}/{v1.slug}", follow_redirects=False
        )
        assert resp.status_code == 200
        assert f"/upload?revises={v1.url_hash}" not in resp.text

    async def test_anonymous_does_not_see_new_version_link(
        self, client, test_user, test_subject, test_db
    ):
        """An unauthenticated user should NOT see the 'New Version' link."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)

        resp = await client.get(
            f"/{v1.publication_year}/{v1.slug}", follow_redirects=False
        )
        assert resp.status_code == 200
        assert f"/upload?revises={v1.url_hash}" not in resp.text
        assert "New Version" not in resp.text

    async def test_owner_sees_link_on_hash_route(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """The 'New Version' link also appears on the /scroll/{url_hash} route."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)

        resp = await authenticated_client.get(
            f"/scroll/{v1.url_hash}", follow_redirects=False
        )
        assert resp.status_code == 200
        assert f"/upload?revises={v1.url_hash}" in resp.text


@pytest.mark.asyncio
class TestYearSlugWithMultipleVersions:
    """GET /{year}/{slug} should return the latest version when multiple exist."""

    async def test_year_slug_returns_latest_version(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """When v1 and v2 share the same year/slug, the route should return the latest."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)

        # Create v2 with the same year/slug/series
        url_hash2, content_hash2, _ = await generate_permanent_url(
            test_db, "<h1>Version 2</h1><p>Updated content for v2</p>"
        )
        v2 = Scroll(
            user_id=test_user.id,
            subject_id=test_subject.id,
            title="Neural Networks v2",
            authors="Jane Doe",
            abstract="Updated abstract",
            keywords=["neural"],
            html_content="<h1>Version 2</h1><p>Updated content for v2</p>",
            license="cc-by-4.0",
            content_hash=content_hash2,
            url_hash=url_hash2,
            status="preview",
        )
        test_db.add(v2)
        await test_db.commit()
        await test_db.refresh(v2)

        v2.publish()
        v2.version = 2
        v2.scroll_series_id = v1.scroll_series_id
        v2.slug = v1.slug
        v2.publication_year = v1.publication_year
        await test_db.commit()
        await test_db.refresh(v2)

        resp = await authenticated_client.get(
            f"/{v1.publication_year}/{v1.slug}", follow_redirects=False
        )
        assert resp.status_code == 200
        assert "Neural Networks v2" in resp.text

    async def test_publish_v2_redirects_to_year_slug_without_500(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """Publishing v2 should redirect to year/slug URL without a 500 error."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)

        # Create a preview for v2
        url_hash2, content_hash2, _ = await generate_permanent_url(
            test_db, "<h1>Version 2</h1><p>New content for publish test</p>"
        )
        preview = Scroll(
            user_id=test_user.id,
            subject_id=test_subject.id,
            title="Neural Networks v2",
            authors="Jane Doe",
            abstract="Updated abstract",
            keywords=["neural"],
            html_content="<h1>Version 2</h1><p>New content for publish test</p>",
            license="cc-by-4.0",
            content_hash=content_hash2,
            url_hash=url_hash2,
            status="preview",
        )
        test_db.add(preview)
        await test_db.commit()
        await test_db.refresh(preview)

        # Set revises_scroll in session
        session_id = authenticated_client.cookies.get("session_id")
        session = get_session(session_id)
        session["revises_scroll"] = v1.url_hash

        # Publish v2
        resp = await authenticated_client.post(
            f"/preview/{preview.url_hash}/confirm", follow_redirects=False
        )
        assert resp.status_code == 303

        # Follow the redirect to year/slug -- should NOT 500
        redirect_url = resp.headers["location"]
        resp2 = await authenticated_client.get(redirect_url, follow_redirects=False)
        assert resp2.status_code == 200


@pytest.mark.asyncio
class TestMetadataOnlyRevision:
    """Revision upload without re-uploading HTML file (metadata-only version update)."""

    async def test_revision_without_file_uses_parent_content(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """Submitting revision form without a file should use the parent scroll's HTML."""
        v1 = await _create_published_v1(test_db, test_user, test_subject)

        session_id = authenticated_client.cookies.get("session_id")
        session = get_session(session_id)
        session["revises_scroll"] = v1.url_hash

        # Submit form WITHOUT a file
        resp = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Updated Title Only",
                "authors": "Jane Doe",
                "subject_id": str(test_subject.id),
                "abstract": "Updated abstract only",
                "keywords": "neural,networks",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            follow_redirects=False,
        )
        # Should succeed (redirect to preview) -- not 422 "HTML file is required"
        assert resp.status_code == 303

    async def test_revision_without_file_and_no_revises_still_requires_file(
        self, authenticated_client, test_user, test_subject, test_db
    ):
        """Without revises_scroll in session, no file should still fail."""
        resp = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Some Title",
                "authors": "Jane Doe",
                "subject_id": str(test_subject.id),
                "abstract": "Some abstract",
                "keywords": "",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 422
        assert "HTML file is required" in resp.text
