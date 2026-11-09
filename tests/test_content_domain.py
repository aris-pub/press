"""Paper files served from {url_hash}.<CONTENT_DOMAIN>, a different site from Press.

A paper's scripts then run on another site, so they cannot act as a logged-in reader.
See docs/THREAT_MODEL.md and bead prs-2m6.
"""

from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
import pytest_asyncio

from app.config import get_base_url
from app.models.scroll import Scroll
from app.storage.memory import InMemoryStorage

DOMAIN = "content.test"


@pytest.fixture(autouse=True)
def content_domain(monkeypatch):
    monkeypatch.setenv("CONTENT_DOMAIN", DOMAIN)


@pytest_asyncio.fixture
async def storage():
    return InMemoryStorage()


@pytest_asyncio.fixture
async def inline_scroll(test_db, test_user, test_subject):
    from tests.conftest import create_content_addressable_scroll

    return await create_content_addressable_scroll(
        test_db, test_user, test_subject, html_content="<h1>Inline content</h1>"
    )


async def _archive(test_db, test_user, test_subject, storage, status="published"):
    content_hash = "c0ffee000001" if status == "published" else "c0ffee000002"
    await storage.put(
        f"scrolls/{content_hash}/index.html",
        b"<html><head></head><body><h1>Archive</h1></body></html>",
        "text/html",
    )
    await storage.put(f"scrolls/{content_hash}/styles/main.css", b"h1{}", "text/css")
    scroll = Scroll(
        title="Archive",
        authors="Author",
        abstract="Abstract",
        keywords=[],
        html_content="",
        license="cc-by-4.0",
        content_hash=content_hash,
        url_hash=content_hash,
        status="preview",
        storage_type="archive",
        entry_point="index.html",
        user_id=test_user.id,
        subject_id=test_subject.id,
    )
    if status == "published":
        scroll.publish()
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)
    return scroll


@pytest_asyncio.fixture
async def archive_scroll(test_db, test_user, test_subject, storage):
    return await _archive(test_db, test_user, test_subject, storage)


@pytest_asyncio.fixture
async def preview_archive(test_db, test_user, test_subject, storage):
    return await _archive(test_db, test_user, test_subject, storage, status="preview")


def _url(url_hash: str, path: str = "/") -> str:
    return f"https://{url_hash}.{DOMAIN}{path}"


def _press_origin() -> str:
    parts = urlsplit(get_base_url())
    return f"{parts.scheme}://{parts.netloc}"


class TestServesPapers:
    async def test_inline_paper_at_root(self, client, inline_scroll):
        response = await client.get(_url(inline_scroll.url_hash))

        assert response.status_code == 200
        assert b"<h1>Inline content</h1>" in response.content

    async def test_archive_entry_point_at_root(self, client, archive_scroll, storage):
        with patch("app.storage.get_storage", return_value=storage):
            response = await client.get(_url(archive_scroll.url_hash))

        assert response.status_code == 200
        assert b"<h1>Archive</h1>" in response.content

    async def test_archive_file_by_its_path(self, client, archive_scroll, storage):
        with patch("app.storage.get_storage", return_value=storage):
            response = await client.get(_url(archive_scroll.url_hash, "/styles/main.css"))

        assert response.status_code == 200
        assert response.content == b"h1{}"

    async def test_host_with_port(self, client, inline_scroll):
        url = f"https://{inline_scroll.url_hash}.{DOMAIN}:8443/"
        response = await client.get(url)

        assert response.status_code == 200


class TestOnlyScrollPressMayFrameIt:
    async def test_frame_ancestors_is_press_not_self(self, client, inline_scroll):
        response = await client.get(_url(inline_scroll.url_hash))

        csp = response.headers["content-security-policy"]
        assert f"frame-ancestors {_press_origin()}" in csp
        assert "frame-ancestors 'self'" not in csp

    async def test_no_sameorigin_frame_option(self, client, inline_scroll, storage):
        """X-Frame-Options SAMEORIGIN would stop scroll.press from framing the paper."""
        with patch("app.storage.get_storage", return_value=storage):
            responses = [await client.get(_url(inline_scroll.url_hash))]

        for response in responses:
            assert "x-frame-options" not in response.headers


class TestNothingElseIsServed:
    async def test_press_pages_are_not_reachable(self, client, inline_scroll):
        for path in ("/login", "/register", "/dashboard", "/health", "/static/css/main.css"):
            response = await client.get(_url(inline_scroll.url_hash, path))
            assert response.status_code == 404, path
            assert b"Sign in" not in response.content

    async def test_only_get_and_head(self, client, inline_scroll):
        response = await client.post(
            _url(inline_scroll.url_hash, "/login-form"), data={"email": "a", "password": "b"}
        )

        assert response.status_code == 404

    async def test_bare_domain_is_not_served(self, client):
        response = await client.get(f"https://{DOMAIN}/")

        assert response.status_code == 404

    async def test_unknown_hash(self, client):
        response = await client.get(_url("ffffffffffff"))

        assert response.status_code == 404

    async def test_nested_subdomain_is_not_served(self, client, inline_scroll):
        response = await client.get(f"https://a.{inline_scroll.url_hash}.{DOMAIN}/")

        assert response.status_code == 404

    async def test_previews_are_not_served(self, client, preview_archive, storage):
        """Previews stay on scroll.press until signed links exist (prs-2m6.1)."""
        with patch("app.storage.get_storage", return_value=storage):
            response = await client.get(_url(preview_archive.url_hash))

        assert response.status_code == 404

    async def test_no_cookie_is_ever_set(self, client, inline_scroll):
        for path in ("/", "/login", "/nope"):
            response = await client.get(_url(inline_scroll.url_hash, path))
            assert "set-cookie" not in response.headers, path


async def test_unset_content_domain_changes_nothing(client, inline_scroll, monkeypatch):
    monkeypatch.delenv("CONTENT_DOMAIN")

    response = await client.get(f"/scroll/{inline_scroll.url_hash}/paper")

    assert response.status_code == 200
    assert "frame-ancestors 'self'" in response.headers["content-security-policy"]


class TestScrollPressRedirectsPublishedPapers:
    async def test_inline_paper_paths(self, client, inline_scroll):
        h = inline_scroll.url_hash
        for path in (f"/scroll/{h}/paper", f"/scroll/{h}/paper/"):
            response = await client.get(path, follow_redirects=False)
            assert response.status_code == 301, path
            assert response.headers["location"] == _url(h), path

    async def test_archive_paths(self, client, archive_scroll, storage):
        h = archive_scroll.url_hash
        cases = {
            f"/scroll/{h}/paper": _url(h),
            f"/scroll/{h}/paper/": _url(h),
            f"/scroll/{h}/paper/styles/main.css": _url(h, "/styles/main.css"),
            f"/scroll/{h}/styles/main.css": _url(h, "/styles/main.css"),
        }
        with patch("app.storage.get_storage", return_value=storage):
            for path, location in cases.items():
                response = await client.get(path, follow_redirects=False)
                assert response.status_code == 301, path
                assert response.headers["location"] == location, path

    async def test_manuscript_only_links(self, client, test_db, inline_scroll):
        inline_scroll.publication_year, inline_scroll.slug = 2026, "a-paper"
        await test_db.commit()
        year, slug = 2026, "a-paper"
        for path in (f"/{year}/{slug}/paper", f"/{year}/{slug}/v1/paper"):
            response = await client.get(path, follow_redirects=False)
            assert response.status_code == 301, path
            assert response.headers["location"] == _url(inline_scroll.url_hash), path

    async def test_query_string_is_kept(self, client, inline_scroll):
        h = inline_scroll.url_hash
        response = await client.get(f"/scroll/{h}/paper/?x=1", follow_redirects=False)

        assert response.headers["location"] == _url(h, "/?x=1")

    async def test_previews_stay_on_press(self, client, test_db, preview_archive, storage):
        from app.auth.session import create_session

        session_id = await create_session(test_db, preview_archive.user_id)
        client.cookies.set("session_id", session_id)
        with patch("app.storage.get_storage", return_value=storage):
            response = await client.get(
                f"/scroll/{preview_archive.url_hash}/paper/", follow_redirects=False
            )

        assert response.status_code == 200

    async def test_download_stays_on_press(self, client, inline_scroll):
        response = await client.get(
            f"/scroll/{inline_scroll.url_hash}/download", follow_redirects=False
        )

        assert response.status_code == 200


class TestScrollPageFramesTheContentDomain:
    async def _page(self, client, test_db, scroll):
        scroll.publication_year, scroll.slug = 2026, "a-paper"
        await test_db.commit()
        return await client.get("/2026/a-paper")

    async def test_iframe_loads_from_content_domain(self, client, test_db, inline_scroll):
        response = await self._page(client, test_db, inline_scroll)

        assert response.status_code == 200
        assert f'data-src="{_url(inline_scroll.url_hash)}"' in response.text

    async def test_iframe_allows_fullscreen_and_clipboard(self, client, test_db, inline_scroll):
        response = await self._page(client, test_db, inline_scroll)

        assert 'allow="fullscreen; clipboard-write"' in response.text

    async def test_csp_allows_framing_the_content_domain(self, client, test_db, inline_scroll):
        response = await self._page(client, test_db, inline_scroll)

        csp = response.headers["content-security-policy"]
        frame_src = next(d for d in csp.split(";") if d.strip().startswith("frame-src"))
        assert f"https://*.{DOMAIN}" in frame_src

    async def test_unset_keeps_press_paths(self, client, test_db, inline_scroll, monkeypatch):
        monkeypatch.delenv("CONTENT_DOMAIN")
        response = await self._page(client, test_db, inline_scroll)

        assert f'data-src="/scroll/{inline_scroll.url_hash}/paper"' in response.text
        assert DOMAIN not in response.headers["content-security-policy"]
