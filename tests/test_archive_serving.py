"""Tests for serving archive (multi-file) scroll content from Tigris storage."""


from unittest.mock import patch

import pytest
import pytest_asyncio

from app.models.scroll import Scroll
from app.storage.memory import InMemoryStorage


@pytest_asyncio.fixture
async def storage():
    """Create an InMemoryStorage backend for tests."""
    return InMemoryStorage()


@pytest_asyncio.fixture
async def archive_scroll(test_db, test_user, test_subject, storage):
    """Create an archive-type scroll with files in storage."""
    content_hash = "abc123def456"
    url_hash = "abc123def456"

    # Store files in the in-memory storage
    await storage.put(
        f"scrolls/{content_hash}/index.html",
        b"<html><head><link href='./styles/main.css'></head><body><h1>Hello</h1></body></html>",
        "text/html",
    )
    await storage.put(
        f"scrolls/{content_hash}/styles/main.css",
        b"h1 { color: red; }",
        "text/css",
    )
    await storage.put(
        f"scrolls/{content_hash}/data/results.json",
        b'{"results": [1, 2, 3]}',
        "application/json",
    )
    await storage.put(
        f"scrolls/{content_hash}/images/figure1.png",
        b"\x89PNG\r\n\x1a\n fake png data",
        "image/png",
    )

    scroll = Scroll(
        title="Archive Test Scroll",
        authors="Test Author",
        abstract="Test abstract for archive scroll",
        keywords=["test"],
        html_content="",
        license="cc-by-4.0",
        content_hash=content_hash,
        url_hash=url_hash,
        status="published",
        storage_type="archive",
        entry_point="index.html",
        user_id=test_user.id,
        subject_id=test_subject.id,
    )
    scroll.publish()
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)
    return scroll


@pytest_asyncio.fixture
async def inline_scroll(test_db, test_user, test_subject):
    """Create a standard inline scroll."""
    from tests.conftest import create_content_addressable_scroll

    return await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Inline Scroll",
        html_content="<h1>Inline content</h1>",
    )


def _patch_storage(storage):
    """Return a context manager that patches get_storage to return the given storage."""
    return patch("app.storage.get_storage", return_value=storage)


@pytest.mark.asyncio
class TestArchiveEntryPoint:
    """Tests for GET /scroll/{url_hash}/paper/ (trailing slash, archive scrolls)."""

    async def test_serves_entry_point_html(self, client, archive_scroll, storage):
        with _patch_storage(storage):
            response = await client.get(f"/scroll/{archive_scroll.url_hash}/paper/")
        assert response.status_code == 200
        assert b"<h1>Hello</h1>" in response.content
        assert response.headers["content-type"].startswith("text/html")

    async def test_csp_headers_on_entry_point(self, client, archive_scroll, storage):
        with _patch_storage(storage):
            response = await client.get(f"/scroll/{archive_scroll.url_hash}/paper/")
        assert response.status_code == 200
        csp = response.headers["content-security-policy"]
        assert "'unsafe-inline'" in csp
        assert "'unsafe-eval'" in csp
        assert "frame-ancestors 'self'" in csp
        assert response.headers["x-frame-options"] == "SAMEORIGIN"

    async def test_cache_control_on_entry_point(self, client, archive_scroll, storage):
        with _patch_storage(storage):
            response = await client.get(f"/scroll/{archive_scroll.url_hash}/paper/")
        cache = response.headers["cache-control"]
        assert "max-age=3600" in cache

    async def test_404_for_missing_scroll(self, client, storage):
        with _patch_storage(storage):
            response = await client.get("/scroll/nonexistent123/paper/")
        assert response.status_code == 404

    async def test_404_for_missing_entry_point_in_storage(
        self, client, test_db, test_user, test_subject, storage
    ):
        """If the entry point file is missing from storage, return 404."""
        scroll = Scroll(
            title="Broken Archive",
            authors="Author",
            abstract="Abstract",
            keywords=[],
            html_content="",
            license="cc-by-4.0",
            content_hash="missing_hash_xyz",
            url_hash="missing_hash_x",
            status="published",
            storage_type="archive",
            entry_point="index.html",
            user_id=test_user.id,
            subject_id=test_subject.id,
        )
        scroll.publish()
        test_db.add(scroll)
        await test_db.commit()

        with _patch_storage(storage):
            response = await client.get(f"/scroll/{scroll.url_hash}/paper/")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestArchiveAssetServing:
    """Tests for GET /scroll/{url_hash}/paper/{path:path} (asset serving)."""

    async def test_serves_css_asset(self, client, archive_scroll, storage):
        with _patch_storage(storage):
            response = await client.get(
                f"/scroll/{archive_scroll.url_hash}/paper/styles/main.css"
            )
        assert response.status_code == 200
        assert b"h1 { color: red; }" in response.content
        assert response.headers["content-type"].startswith("text/css")

    async def test_serves_json_asset(self, client, archive_scroll, storage):
        with _patch_storage(storage):
            response = await client.get(
                f"/scroll/{archive_scroll.url_hash}/paper/data/results.json"
            )
        assert response.status_code == 200
        assert b'"results"' in response.content
        assert "application/json" in response.headers["content-type"]

    async def test_serves_image_asset(self, client, archive_scroll, storage):
        with _patch_storage(storage):
            response = await client.get(
                f"/scroll/{archive_scroll.url_hash}/paper/images/figure1.png"
            )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    async def test_immutable_cache_on_assets(self, client, archive_scroll, storage):
        with _patch_storage(storage):
            response = await client.get(
                f"/scroll/{archive_scroll.url_hash}/paper/styles/main.css"
            )
        cache = response.headers["cache-control"]
        assert "max-age=31536000" in cache
        assert "immutable" in cache

    async def test_frame_headers_on_assets(self, client, archive_scroll, storage):
        with _patch_storage(storage):
            response = await client.get(
                f"/scroll/{archive_scroll.url_hash}/paper/styles/main.css"
            )
        assert response.headers["x-frame-options"] == "SAMEORIGIN"

    async def test_404_for_missing_asset(self, client, archive_scroll, storage):
        with _patch_storage(storage):
            response = await client.get(
                f"/scroll/{archive_scroll.url_hash}/paper/nonexistent.js"
            )
        assert response.status_code == 404

    async def test_404_for_nonexistent_scroll(self, client, storage):
        with _patch_storage(storage):
            response = await client.get("/scroll/nonexistent123/paper/foo.css")
        assert response.status_code == 404

    async def test_path_traversal_blocked(self, client, archive_scroll, storage):
        """Path traversal attempts should be blocked."""
        with _patch_storage(storage):
            response = await client.get(
                f"/scroll/{archive_scroll.url_hash}/paper/../../../etc/passwd"
            )
        assert response.status_code in (400, 404)

    async def test_fallback_content_type(self, client, archive_scroll, storage):
        """Unknown file extensions get application/octet-stream."""
        await storage.put(
            f"scrolls/{archive_scroll.content_hash}/data.qzx",
            b"some binary data",
        )
        with _patch_storage(storage):
            response = await client.get(
                f"/scroll/{archive_scroll.url_hash}/paper/data.qzx"
            )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"


@pytest.mark.asyncio
class TestPaperRedirect:
    """Tests for redirect behavior on /scroll/{url_hash}/paper (no trailing slash)."""

    async def test_archive_scroll_redirects_to_trailing_slash(
        self, client, archive_scroll, storage
    ):
        with _patch_storage(storage):
            response = await client.get(
                f"/scroll/{archive_scroll.url_hash}/paper", follow_redirects=False
            )
        assert response.status_code == 301
        assert response.headers["location"].endswith(
            f"/scroll/{archive_scroll.url_hash}/paper/"
        )

    async def test_inline_scroll_serves_directly(self, client, inline_scroll):
        """Inline scrolls should still serve HTML directly without redirect."""
        response = await client.get(
            f"/scroll/{inline_scroll.url_hash}/paper", follow_redirects=False
        )
        assert response.status_code == 200
        assert b"Inline content" in response.content


@pytest.mark.asyncio
class TestArchivePreviewAuth:
    """Tests for preview (unpublished) archive scroll auth checks."""

    async def test_preview_archive_requires_auth(
        self, client, test_db, test_user, test_subject, storage
    ):
        """Preview archive scrolls should require the owner to be authenticated."""
        scroll = Scroll(
            title="Preview Archive",
            authors="Author",
            abstract="Abstract",
            keywords=[],
            html_content="",
            license="cc-by-4.0",
            content_hash="preview_hash_abc",
            url_hash="preview_hash",
            status="preview",
            storage_type="archive",
            entry_point="index.html",
            user_id=test_user.id,
            subject_id=test_subject.id,
        )
        test_db.add(scroll)
        await test_db.commit()

        await storage.put(
            f"scrolls/{scroll.content_hash}/index.html",
            b"<h1>Preview</h1>",
        )

        with _patch_storage(storage):
            response = await client.get(f"/scroll/{scroll.url_hash}/paper/")
        assert response.status_code == 404

    async def test_preview_archive_owner_can_view(
        self, authenticated_client, test_db, test_user, test_subject, storage
    ):
        scroll = Scroll(
            title="Preview Archive",
            authors="Author",
            abstract="Abstract",
            keywords=[],
            html_content="",
            license="cc-by-4.0",
            content_hash="preview_own_abc",
            url_hash="preview_own_a",
            status="preview",
            storage_type="archive",
            entry_point="index.html",
            user_id=test_user.id,
            subject_id=test_subject.id,
        )
        test_db.add(scroll)
        await test_db.commit()

        await storage.put(
            f"scrolls/{scroll.content_hash}/index.html",
            b"<h1>Owner Preview</h1>",
        )

        with _patch_storage(storage):
            response = await authenticated_client.get(
                f"/scroll/{scroll.url_hash}/paper/"
            )
        assert response.status_code == 200
        assert b"Owner Preview" in response.content


@pytest.mark.asyncio
class TestIframeSrcForArchive:
    """Test that scroll.html template uses trailing-slash src for archive scrolls."""

    async def test_archive_scroll_iframe_has_trailing_slash(
        self, client, archive_scroll, storage
    ):
        response = await client.get(f"/scroll/{archive_scroll.url_hash}")
        assert response.status_code == 200
        assert f'/scroll/{archive_scroll.url_hash}/paper/' in response.text

    async def test_inline_scroll_iframe_no_trailing_slash(self, client, inline_scroll):
        response = await client.get(f"/scroll/{inline_scroll.url_hash}")
        assert response.status_code == 200
        src = f'/scroll/{inline_scroll.url_hash}/paper"'
        assert src in response.text
