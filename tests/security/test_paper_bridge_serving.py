# ruff: noqa: F811 (fixtures are imported from the groundwork tests)
"""Every response that serves paper HTML carries the bridge script (prs-2m6, step 3).

Non-HTML files and the raw download stay byte for byte as uploaded. HTML responses get
an ETag tied to the bridge version and never a year-long immutable cache, so a new
bridge reaches readers.
"""

import pytest

from app.paper_bridge import BRIDGE_SCRIPT, paper_etag
from tests.security.test_groundwork_headers import (  # noqa: F401
    ARCHIVE_FILES,
    CONTENT_HASH,
    inline_scroll,
    patched_storage,
    preview_archive,
    published_archive,
    raw_client,
    storage,
)

pytestmark = pytest.mark.asyncio


async def _year_slug(db, scroll):
    scroll.publication_year = 2026
    scroll.slug = "bridge-test"
    await db.commit()
    return scroll.publication_year, scroll.slug


class TestInlinePaper:
    async def test_hash_paper_url_has_bridge(self, raw_client, inline_scroll):
        response = await raw_client.get(f"/scroll/{inline_scroll.url_hash}/paper")
        assert response.content == BRIDGE_SCRIPT + inline_scroll.html_content.encode()

    async def test_hash_paper_url_with_slash_has_bridge(self, raw_client, inline_scroll):
        response = await raw_client.get(f"/scroll/{inline_scroll.url_hash}/paper/")
        assert response.content == BRIDGE_SCRIPT + inline_scroll.html_content.encode()

    async def test_year_slug_paper_urls_have_bridge(self, raw_client, inline_scroll, test_db):
        year, slug = await _year_slug(test_db, inline_scroll)
        for url in (f"/{year}/{slug}/paper", f"/{year}/{slug}/v1/paper"):
            response = await raw_client.get(url)
            assert response.status_code == 200, url
            assert response.content.count(BRIDGE_SCRIPT) == 1, url

    async def test_paper_etag_carries_bridge_version(self, raw_client, inline_scroll, test_db):
        year, slug = await _year_slug(test_db, inline_scroll)
        response = await raw_client.get(f"/{year}/{slug}/paper")
        assert response.headers["etag"] == paper_etag(inline_scroll.content_hash)

    async def test_old_etag_without_bridge_version_gets_full_response(
        self, raw_client, inline_scroll, test_db
    ):
        year, slug = await _year_slug(test_db, inline_scroll)
        response = await raw_client.get(
            f"/{year}/{slug}/paper",
            headers={"If-None-Match": f'"{inline_scroll.content_hash}"'},
        )
        assert response.status_code == 200
        assert BRIDGE_SCRIPT in response.content

    async def test_raw_download_is_the_untouched_upload(self, raw_client, inline_scroll):
        response = await raw_client.get(f"/scroll/{inline_scroll.url_hash}/raw")
        assert BRIDGE_SCRIPT not in response.content


class TestArchivePaper:
    async def test_entry_point_has_bridge_after_head(
        self, raw_client, published_archive, patched_storage
    ):
        response = await raw_client.get(f"/scroll/{CONTENT_HASH}/paper/")
        assert response.content == b"<html><head>" + BRIDGE_SCRIPT + b"</head><body>" + (
            b"<h1>Paper</h1></body></html>"
        )
        assert response.headers["etag"] == paper_etag(CONTENT_HASH)

    @pytest.mark.parametrize("prefix", ["paper/", ""])
    async def test_other_html_files_have_bridge(
        self, raw_client, published_archive, patched_storage, prefix
    ):
        response = await raw_client.get(f"/scroll/{CONTENT_HASH}/{prefix}page2.html")
        assert response.content == b"<html>" + BRIDGE_SCRIPT + b"<body>Second page</body></html>"

    @pytest.mark.parametrize("prefix", ["paper/", ""])
    async def test_html_files_are_not_cached_for_a_year(
        self, raw_client, published_archive, patched_storage, prefix
    ):
        response = await raw_client.get(f"/scroll/{CONTENT_HASH}/{prefix}page2.html")
        assert response.headers["cache-control"] == "public, max-age=3600"

    @pytest.mark.parametrize(
        "path", [p for p, (_, ctype) in ARCHIVE_FILES.items() if ctype != "text/html"]
    )
    async def test_non_html_files_are_unchanged(
        self, raw_client, published_archive, patched_storage, path
    ):
        response = await raw_client.get(f"/scroll/{CONTENT_HASH}/paper/{path}")
        assert response.content == ARCHIVE_FILES[path][0]

    async def test_preview_html_stays_private(
        self, raw_client, preview_archive, patched_storage, test_db, test_user
    ):
        from app.auth.session import create_session

        raw_client.cookies.set("session_id", await create_session(test_db, test_user.id))
        response = await raw_client.get(f"/scroll/{preview_archive.url_hash}/paper/page2.html")
        assert BRIDGE_SCRIPT in response.content
        assert response.headers["cache-control"] == "private, no-store"


class TestArchiveHtmlPolicy:
    """Every HTML page of an archive runs under the paper policy, like the entry point.

    Without it, Press's own strict policy blocked every inline script on an archive's
    second page, the bridge included.
    """

    @pytest.mark.parametrize("prefix", ["paper/", ""])
    async def test_other_html_pages_get_the_paper_policy(
        self, raw_client, published_archive, patched_storage, prefix
    ):
        from app.routes.scrolls import _PAPER_CSP

        entry = await raw_client.get(f"/scroll/{CONTENT_HASH}/paper/")
        page2 = await raw_client.get(f"/scroll/{CONTENT_HASH}/{prefix}page2.html")
        assert page2.headers["content-security-policy"] == _PAPER_CSP
        assert page2.headers["content-security-policy"] == entry.headers["content-security-policy"]

    async def test_non_html_files_keep_their_policy(
        self, raw_client, published_archive, patched_storage
    ):
        from app.routes.scrolls import _PAPER_CSP

        response = await raw_client.get(f"/scroll/{CONTENT_HASH}/paper/figure.svg")
        assert response.headers.get("content-security-policy") != _PAPER_CSP
