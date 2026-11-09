"""Previews load from the content domain through a signed link (prs-2m6.1).

The owner's Press login never reaches the content domain, so the preview page gives its
iframe {url_hash}-{expires}-{signature}.<CONTENT_DOMAIN>. The content domain serves a
preview only for a valid, unexpired signature over that url_hash.
"""

import re
import time
from unittest.mock import patch

import pytest
import pytest_asyncio

from app import content_domain
from app.models.scroll import Scroll
from app.storage.memory import InMemoryStorage

DOMAIN = "content.test"
KEY = "k" * 64
SIGNED_HOST = re.compile(r"^https://([0-9a-f]+)-(\d+)-([0-9a-f]{32})\.content\.test/$")


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setenv("CONTENT_DOMAIN", DOMAIN)
    monkeypatch.setenv("PREVIEW_LINK_KEY", KEY)


@pytest_asyncio.fixture
async def storage():
    return InMemoryStorage()


async def _scroll(test_db, test_user, test_subject, storage, status, storage_type="archive"):
    content_hash = {"preview": "abcdef000001", "published": "abcdef000002"}[status]
    if storage_type == "archive":
        await storage.put(
            f"scrolls/{content_hash}/index.html",
            b"<html><head></head><body><h1>Preview body</h1></body></html>",
            "text/html",
        )
        await storage.put(f"scrolls/{content_hash}/fig/a.svg", b"<svg/>", "image/svg+xml")
    scroll = Scroll(
        title="Preview scroll",
        authors="Author",
        abstract="Abstract",
        keywords=[],
        html_content="" if storage_type == "archive" else "<h1>Inline preview</h1>",
        license="cc-by-4.0",
        content_hash=content_hash,
        url_hash=content_hash,
        status="preview",
        storage_type=storage_type,
        entry_point="index.html" if storage_type == "archive" else None,
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
async def preview(test_db, test_user, test_subject, storage):
    return await _scroll(test_db, test_user, test_subject, storage, "preview")


@pytest_asyncio.fixture
async def inline_preview(test_db, test_user, test_subject, storage):
    return await _scroll(test_db, test_user, test_subject, storage, "preview", "inline")


def _signed(url_hash, expires=None, key=KEY):
    expires = expires if expires is not None else int(time.time()) + 3600
    return f"https://{url_hash}-{expires}-{content_domain.sign(url_hash, expires, key)}.{DOMAIN}"


async def _get(client, storage, url):
    with patch("app.storage.get_storage", return_value=storage):
        return await client.get(url)


class TestPreviewPageUsesASignedLink:
    async def test_iframe_loads_a_signed_content_domain_link(self, authenticated_client, preview):
        response = await authenticated_client.get(f"/preview/{preview.url_hash}")

        src = re.search(r'data-src="([^"]+)"', response.text).group(1)
        match = SIGNED_HOST.match(src)
        assert match, src
        assert match.group(1) == preview.url_hash

    async def test_link_expires_in_one_hour(self, authenticated_client, preview):
        before = int(time.time())
        response = await authenticated_client.get(f"/preview/{preview.url_hash}")

        src = re.search(r'data-src="([^"]+)"', response.text).group(1)
        expires = int(SIGNED_HOST.match(src).group(2))
        assert before + 3600 <= expires <= int(time.time()) + 3600

    async def test_label_fits_in_one_dns_label(self, authenticated_client, preview):
        response = await authenticated_client.get(f"/preview/{preview.url_hash}")

        src = re.search(r'data-src="([^"]+)"', response.text).group(1)
        label = src.removeprefix("https://").split(".", 1)[0]
        assert len(label) <= 63

    async def test_without_a_key_previews_stay_on_press(
        self, authenticated_client, preview, monkeypatch
    ):
        monkeypatch.delenv("PREVIEW_LINK_KEY")
        response = await authenticated_client.get(f"/preview/{preview.url_hash}")

        assert f'data-src="/scroll/{preview.url_hash}/paper/"' in response.text

    async def test_without_a_content_domain_previews_stay_on_press(
        self, authenticated_client, preview, monkeypatch
    ):
        monkeypatch.delenv("CONTENT_DOMAIN")
        response = await authenticated_client.get(f"/preview/{preview.url_hash}")

        assert f'data-src="/scroll/{preview.url_hash}/paper/"' in response.text

    async def test_iframe_allows_fullscreen_and_clipboard(self, authenticated_client, preview):
        """Same as the scroll page, so a preview behaves like the published paper."""
        response = await authenticated_client.get(f"/preview/{preview.url_hash}")

        assert 'allow="fullscreen; clipboard-write"' in response.text

    async def test_preview_page_csp_allows_the_content_domain(self, authenticated_client, preview):
        response = await authenticated_client.get(f"/preview/{preview.url_hash}")

        csp = response.headers["content-security-policy"]
        frame_src = next(d for d in csp.split(";") if d.strip().startswith("frame-src"))
        assert f"https://*.{DOMAIN}" in frame_src


class TestValidSignatureServesThePreview:
    async def test_archive_entry_point(self, client, preview, storage):
        response = await _get(client, storage, _signed(preview.url_hash) + "/")

        assert response.status_code == 200
        assert b"<h1>Preview body</h1>" in response.content

    async def test_archive_file(self, client, preview, storage):
        response = await _get(client, storage, _signed(preview.url_hash) + "/fig/a.svg")

        assert response.status_code == 200
        assert response.content == b"<svg/>"

    async def test_inline_preview(self, client, inline_preview, storage):
        response = await _get(client, storage, _signed(inline_preview.url_hash) + "/")

        assert response.status_code == 200
        assert b"<h1>Inline preview</h1>" in response.content

    async def test_never_cached_and_never_leaks_the_link(self, client, preview, storage):
        """The link is a credential for an hour: no shared cache may keep the answer, and
        no Referer may carry the signed host to a CDN the paper loads from."""
        response = await _get(client, storage, _signed(preview.url_hash) + "/")

        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "set-cookie" not in response.headers

    async def test_only_press_may_frame_it(self, client, preview, storage):
        response = await _get(client, storage, _signed(preview.url_hash) + "/")

        assert "frame-ancestors 'self'" not in response.headers["content-security-policy"]
        assert "x-frame-options" not in response.headers


class TestEveryBadLinkIsRefused:
    async def test_expired(self, client, preview, storage):
        url = _signed(preview.url_hash, expires=int(time.time()) - 1) + "/"

        assert (await _get(client, storage, url)).status_code == 404

    async def test_link_stops_working_after_the_hour(self, client, preview, storage):
        url = _signed(preview.url_hash) + "/"
        later = time.time() + 3601

        with patch("app.content_domain.time.time", return_value=later):
            response = await _get(client, storage, url)

        assert response.status_code == 404

    async def test_tampered_signature(self, client, preview, storage):
        url = _signed(preview.url_hash)
        last = url[-len(f".{DOMAIN}") - 1]
        tampered = url.replace(f"{last}.{DOMAIN}", f"{'0' if last != '0' else '1'}.{DOMAIN}")

        assert (await _get(client, storage, tampered + "/")).status_code == 404

    async def test_later_expiry_with_the_old_signature(self, client, preview, storage):
        expires = int(time.time()) + 3600
        sig = content_domain.sign(preview.url_hash, expires, KEY)
        url = f"https://{preview.url_hash}-{expires + 86400}-{sig}.{DOMAIN}/"

        assert (await _get(client, storage, url)).status_code == 404

    async def test_signature_for_another_scroll(
        self, client, test_db, test_user, test_subject, preview, storage
    ):
        other = await _scroll(test_db, test_user, test_subject, storage, "published")
        expires = int(time.time()) + 3600
        sig = content_domain.sign(other.url_hash, expires, KEY)
        url = f"https://{preview.url_hash}-{expires}-{sig}.{DOMAIN}/"

        assert (await _get(client, storage, url)).status_code == 404

    async def test_signed_with_another_key(self, client, preview, storage):
        url = _signed(preview.url_hash, key="x" * 64) + "/"

        assert (await _get(client, storage, url)).status_code == 404

    async def test_no_key_configured_refuses_every_signed_link(
        self, client, preview, storage, monkeypatch
    ):
        url = _signed(preview.url_hash) + "/"
        monkeypatch.delenv("PREVIEW_LINK_KEY")

        assert (await _get(client, storage, url)).status_code == 404

    async def test_unsigned_preview_is_still_refused(self, client, preview, storage):
        response = await _get(client, storage, f"https://{preview.url_hash}.{DOMAIN}/")

        assert response.status_code == 404

    async def test_malformed_labels(self, client, preview, storage):
        h = preview.url_hash
        for label in (f"{h}-", f"{h}-123", f"{h}-abc-{'0' * 32}", f"{h}-123-{'0' * 31}"):
            response = await _get(client, storage, f"https://{label}.{DOMAIN}/")
            assert response.status_code == 404, label

    async def test_signed_link_cannot_reach_press_pages(self, client, preview, storage):
        for path in ("/login", "/dashboard", "/upload"):
            response = await _get(client, storage, _signed(preview.url_hash) + path)
            assert response.status_code == 404, path


async def test_published_papers_also_send_no_referrer(client, test_db, test_user, test_subject):
    from tests.conftest import create_content_addressable_scroll

    scroll = await create_content_addressable_scroll(test_db, test_user, test_subject)
    response = await client.get(f"https://{scroll.url_hash}.{DOMAIN}/")

    assert response.status_code == 200
    assert response.headers["referrer-policy"] == "no-referrer"
