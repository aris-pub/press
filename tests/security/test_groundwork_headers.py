"""Groundwork for sandboxing author papers (prs-2m6, step 2).

Once papers are sandboxed, their requests come from an opaque origin and count as
cross-site. These tests pin the protections that must already be in place then:

- sensitive requests marked cross-site or same-site by the browser are refused,
- Press pages set Cross-Origin-Opener-Policy so a popup cannot take over the scroll page,
- archive files send Access-Control-Allow-Origin: * (and never credentials), so a
  sandboxed paper can still load its own module scripts, fonts and data,
- previews and scroll pages are never stored in a shared cache,
- archive files are served with a fixed type map, unknown types as downloads.
"""

from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio

from app.auth.csrf import get_csrf_token
from app.auth.session import create_session
from app.models.scroll import Scroll
from app.storage.memory import InMemoryStorage
from main import app

pytestmark = pytest.mark.asyncio

CONTENT_HASH = "f00dfeedbeef"
PREVIEW_HASH = "0bad5eed1234"

ARCHIVE_FILES = {
    "index.html": (b"<html><head></head><body><h1>Paper</h1></body></html>", "text/html"),
    "page2.html": (b"<html><body>Second page</body></html>", "text/html"),
    "figure.svg": (b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "image/svg+xml"),
    "static/onload.js": (b"export const x = 1;", "text/javascript"),
    "static/module.mjs": (b"export const y = 2;", "text/javascript"),
    "static/style.css": (b"h1 { color: red; }", "text/css"),
    "fonts/main.woff2": (b"wOF2 fake", "font/woff2"),
    "data/points.json": (b"[1, 2, 3]", "application/json"),
    "data/table.csv": (b"a,b\n1,2\n", "text/csv"),
    "img/plot.png": (b"\x89PNG\r\n\x1a\n fake", "image/png"),
    "model/weights.onnx": (b"\x00\x01binary", "application/octet-stream"),
    "notes/readme.md": (b"# notes", "application/octet-stream"),
    "bin/tool.exe": (b"MZ fake", "application/octet-stream"),
}


@pytest_asyncio.fixture
async def storage():
    return InMemoryStorage()


async def _make_archive(db, user, subject, storage, content_hash, status):
    for path, (data, ctype) in ARCHIVE_FILES.items():
        await storage.put(f"scrolls/{content_hash}/{path}", data, ctype)
    scroll = Scroll(
        title=f"Archive {status}",
        authors="Test Author",
        abstract="Abstract",
        keywords=["test"],
        html_content="",
        license="cc-by-4.0",
        content_hash=content_hash,
        url_hash=content_hash,
        status=status,
        storage_type="archive",
        entry_point="index.html",
        user_id=user.id,
        subject_id=subject.id,
    )
    if status == "published":
        scroll.publish()
    db.add(scroll)
    await db.commit()
    await db.refresh(scroll)
    return scroll


@pytest_asyncio.fixture
async def published_archive(test_db, test_user, test_subject, storage):
    return await _make_archive(
        test_db, test_user, test_subject, storage, CONTENT_HASH, "published"
    )


@pytest_asyncio.fixture
async def preview_archive(test_db, test_user, test_subject, storage):
    return await _make_archive(test_db, test_user, test_subject, storage, PREVIEW_HASH, "preview")


@pytest_asyncio.fixture
async def inline_scroll(test_db, test_user, test_subject):
    from tests.conftest import create_content_addressable_scroll

    return await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="Inline", html_content="<h1>Inline</h1>"
    )


@pytest.fixture
def patched_storage(storage):
    with patch("app.storage.get_storage", return_value=storage):
        yield storage


@pytest_asyncio.fixture
async def raw_client(client):
    """A client that never adds CSRF tokens or Sec-Fetch headers on its own."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as ac:
        yield ac


async def _login(http_client, db, user):
    session_id = await create_session(db, user.id)
    http_client.cookies.set("session_id", session_id)
    return session_id


# Sec-Fetch-Site


REFUSED_SITES = ["cross-site", "same-site"]
ALLOWED_SITES = ["same-origin", "none", None]


def _site(value):
    return {} if value is None else {"Sec-Fetch-Site": value}


class TestSecFetchSite:
    @pytest.mark.parametrize("site", REFUSED_SITES)
    @pytest.mark.parametrize(
        "path",
        [
            "/login-form",
            "/logout",
            "/upload/html",
            "/upload-form",
            "/account/delete-request",
            "/account/delete-confirm",
            "/auth/orcid/unlink",
            "/export-data",
            "/preview/abc/confirm",
            "/preview/abc/cancel",
        ],
    )
    async def test_cross_site_writes_are_refused(self, raw_client, test_db, test_user, path, site):
        session_id = await _login(raw_client, test_db, test_user)
        response = await raw_client.post(
            path,
            data={"csrf_token": await get_csrf_token(session_id)},
            headers=_site(site),
            follow_redirects=False,
        )
        assert response.status_code == 403
        assert "cross-site" in response.text.lower()

    @pytest.mark.parametrize("site", REFUSED_SITES)
    async def test_cross_site_login_without_session_is_refused(self, raw_client, site):
        """Login CSRF: a paper could log the reader into an attacker's account."""
        response = await raw_client.post(
            "/login-form",
            data={"email": "a@b.c", "password": "x"},
            headers=_site(site),
        )
        assert response.status_code == 403

    @pytest.mark.parametrize("site", REFUSED_SITES)
    async def test_cross_site_delete_is_refused(self, raw_client, test_db, test_user, site):
        session_id = await _login(raw_client, test_db, test_user)
        response = await raw_client.delete(
            "/anything",
            headers={**_site(site), "X-CSRF-Token": await get_csrf_token(session_id)},
        )
        assert response.status_code == 403

    @pytest.mark.parametrize("site", REFUSED_SITES)
    @pytest.mark.parametrize("path", ["/csrf-token", "/user/export-data"])
    async def test_cross_site_reads_of_secrets_are_refused(
        self, raw_client, test_db, test_user, path, site
    ):
        await _login(raw_client, test_db, test_user)
        response = await raw_client.get(path, headers=_site(site))
        assert response.status_code == 403

    @pytest.mark.parametrize("site", ALLOWED_SITES)
    @pytest.mark.parametrize("path", ["/csrf-token", "/user/export-data"])
    async def test_same_origin_reads_still_work(self, raw_client, test_db, test_user, path, site):
        await _login(raw_client, test_db, test_user)
        response = await raw_client.get(path, headers=_site(site))
        assert response.status_code == 200

    @pytest.mark.parametrize("site", ALLOWED_SITES)
    async def test_same_origin_logout_still_works(self, raw_client, test_db, test_user, site):
        session_id = await _login(raw_client, test_db, test_user)
        response = await raw_client.post(
            "/logout",
            data={"csrf_token": await get_csrf_token(session_id)},
            headers=_site(site),
            follow_redirects=False,
        )
        assert response.status_code == 302

    @pytest.mark.parametrize("site", ["cross-site", "same-site", "none", "same-origin"])
    @pytest.mark.parametrize("path", ["/", "/login", "/about"])
    async def test_navigations_from_other_sites_still_work(self, raw_client, path, site):
        """Links from email, search engines and other sites arrive cross-site."""
        response = await raw_client.get(path, headers=_site(site))
        assert response.status_code == 200

    async def test_cross_site_email_link_still_opens_deletion_page(self, raw_client):
        response = await raw_client.get(
            "/account/delete-confirm?token=whatever", headers={"Sec-Fetch-Site": "cross-site"}
        )
        assert response.status_code == 200

    async def test_health_is_exempt(self, raw_client):
        response = await raw_client.get("/health", headers={"Sec-Fetch-Site": "cross-site"})
        assert response.status_code != 403


# Cross-Origin-Opener-Policy


class TestOpenerPolicy:
    @pytest.mark.parametrize("path", ["/", "/login", "/about", "/how-it-works"])
    async def test_press_pages_set_coop(self, raw_client, path):
        response = await raw_client.get(path)
        assert response.headers.get("Cross-Origin-Opener-Policy") == "same-origin"

    async def test_scroll_page_sets_coop(self, raw_client, inline_scroll):
        response = await raw_client.get(f"/scroll/{inline_scroll.url_hash}")
        assert response.status_code == 200
        assert response.headers.get("Cross-Origin-Opener-Policy") == "same-origin"

    async def test_dashboard_sets_coop(self, raw_client, test_db, test_user):
        await _login(raw_client, test_db, test_user)
        response = await raw_client.get("/dashboard")
        assert response.headers.get("Cross-Origin-Opener-Policy") == "same-origin"

    async def test_inline_paper_has_no_coop(self, raw_client, inline_scroll):
        response = await raw_client.get(f"/scroll/{inline_scroll.url_hash}/paper")
        assert response.status_code == 200
        assert "Cross-Origin-Opener-Policy" not in response.headers

    @pytest.mark.parametrize("path", ["paper/", "paper/index.html", "paper/page2.html"])
    async def test_archive_paper_files_have_no_coop(
        self, raw_client, published_archive, patched_storage, path
    ):
        response = await raw_client.get(f"/scroll/{CONTENT_HASH}/{path}")
        assert response.status_code == 200
        assert "Cross-Origin-Opener-Policy" not in response.headers


# CORS on archive files


ASSET_PATHS = [p for p in ARCHIVE_FILES if p != "index.html"]


class TestArchiveCors:
    @pytest.mark.parametrize("path", ASSET_PATHS)
    @pytest.mark.parametrize("prefix", ["paper/", ""])
    async def test_archive_files_allow_any_origin_without_credentials(
        self, raw_client, published_archive, patched_storage, path, prefix
    ):
        response = await raw_client.get(f"/scroll/{CONTENT_HASH}/{prefix}{path}")
        assert response.status_code == 200, path
        assert response.headers.get("Access-Control-Allow-Origin") == "*"
        assert "Access-Control-Allow-Credentials" not in response.headers
        assert "Origin" not in response.headers.get("Vary", "")

    async def test_archive_entry_point_allows_any_origin(
        self, raw_client, published_archive, patched_storage
    ):
        response = await raw_client.get(f"/scroll/{CONTENT_HASH}/paper/")
        assert response.headers.get("Access-Control-Allow-Origin") == "*"
        assert "Access-Control-Allow-Credentials" not in response.headers

    @pytest.mark.parametrize("path", ["/", "/csrf-token", "/user/export-data", "/api/v1/scrolls"])
    async def test_press_routes_send_no_cors(self, raw_client, test_db, test_user, path):
        await _login(raw_client, test_db, test_user)
        response = await raw_client.get(path, headers={"Origin": "null"})
        assert "Access-Control-Allow-Origin" not in response.headers
        assert "Access-Control-Allow-Credentials" not in response.headers


# Caching


class TestCaching:
    @pytest.mark.parametrize("path", ["paper/", "paper/static/onload.js", "static/style.css"])
    async def test_preview_files_are_never_stored(
        self, raw_client, test_db, test_user, preview_archive, patched_storage, path
    ):
        await _login(raw_client, test_db, test_user)
        response = await raw_client.get(f"/scroll/{PREVIEW_HASH}/{path}")
        assert response.status_code == 200, path
        assert response.headers.get("Cache-Control") == "private, no-store"

    async def test_preview_page_is_never_stored(
        self, raw_client, test_db, test_user, preview_archive, patched_storage
    ):
        await _login(raw_client, test_db, test_user)
        response = await raw_client.get(f"/preview/{PREVIEW_HASH}")
        assert response.status_code == 200
        assert response.headers.get("Cache-Control") == "private, no-store"

    async def test_scroll_page_is_not_shared_cached(self, raw_client, inline_scroll):
        """The page carries a per-request nonce and an owner flag."""
        response = await raw_client.get(f"/scroll/{inline_scroll.url_hash}")
        assert response.headers.get("Cache-Control") == "private, max-age=0"

    async def test_published_archive_files_stay_cacheable(
        self, raw_client, published_archive, patched_storage
    ):
        response = await raw_client.get(f"/scroll/{CONTENT_HASH}/paper/static/onload.js")
        assert response.headers.get("Cache-Control") == "public, max-age=31536000, immutable"


# File types


EXPECTED_TYPES = {
    "page2.html": "text/html",
    "figure.svg": "image/svg+xml",
    "static/onload.js": "text/javascript",
    "static/module.mjs": "text/javascript",
    "static/style.css": "text/css",
    "fonts/main.woff2": "font/woff2",
    "data/points.json": "application/json",
    "data/table.csv": "text/csv",
    "img/plot.png": "image/png",
}

DOWNLOADS = ["model/weights.onnx", "notes/readme.md", "bin/tool.exe"]


class TestArchiveFileTypes:
    @pytest.mark.parametrize("path,expected", sorted(EXPECTED_TYPES.items()))
    @pytest.mark.parametrize("prefix", ["paper/", ""])
    async def test_known_types_are_served_with_fixed_type(
        self, raw_client, published_archive, patched_storage, path, expected, prefix
    ):
        response = await raw_client.get(f"/scroll/{CONTENT_HASH}/{prefix}{path}")
        assert response.headers["content-type"].split(";")[0] == expected
        assert "attachment" not in response.headers.get("Content-Disposition", "")

    @pytest.mark.parametrize("path", DOWNLOADS)
    @pytest.mark.parametrize("prefix", ["paper/", ""])
    async def test_unknown_types_are_downloads(
        self, raw_client, published_archive, patched_storage, path, prefix
    ):
        response = await raw_client.get(f"/scroll/{CONTENT_HASH}/{prefix}{path}")
        assert response.status_code == 200
        assert response.headers["content-type"].split(";")[0] == "application/octet-stream"
        assert response.headers.get("Content-Disposition", "").startswith("attachment")
        assert response.content == ARCHIVE_FILES[path][0]
