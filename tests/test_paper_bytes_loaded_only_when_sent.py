"""Paper HTML is read from the database only by requests that send it.

Inline papers live in the html_content column, and some are over 10 MB. Every read of
that column is Supabase egress, so the scroll page, archive files and "not modified"
answers must not select it.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import event

from app.models.scroll import Scroll
from app.paper_bridge import paper_etag
from app.storage.memory import InMemoryStorage
from tests.conftest import create_content_addressable_scroll

MARKER = "paper-body-marker-7f3a"
PAPER = f"<!DOCTYPE html><html><head><title>t</title></head><body><p>{MARKER}</p></body></html>"


@contextmanager
def html_content_reads(test_db):
    """Collect every SQL statement that reads the html_content column."""
    engine = test_db.bind.sync_engine
    reads = []

    def record(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT") and "html_content" in statement:
            reads.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield reads
    finally:
        event.remove(engine, "before_cursor_execute", record)


@pytest_asyncio.fixture
async def inline_scroll(test_db, test_user, test_subject):
    scroll = await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="Egress Test", html_content=PAPER
    )
    scroll.publication_year = 2026
    scroll.slug = "egress-test"
    await test_db.commit()
    # Requests must find nothing already loaded, as in production, so a missed load fails.
    test_db.expunge_all()
    return scroll


@pytest_asyncio.fixture
async def archive_scroll(test_db, test_user, test_subject):
    storage = InMemoryStorage()
    await storage.put("scrolls/eg0000000001/index.html", PAPER.encode(), "text/html")
    await storage.put("scrolls/eg0000000001/style.css", b"p { color: red }", "text/css")
    scroll = Scroll(
        title="Egress Archive",
        authors="Test Author",
        abstract="Archive",
        keywords=[],
        html_content=PAPER,
        license="cc-by-4.0",
        content_hash="eg0000000001",
        url_hash="eg0000000001",
        status="published",
        storage_type="archive",
        entry_point="index.html",
        user_id=test_user.id,
        subject_id=test_subject.id,
    )
    scroll.publish()
    test_db.add(scroll)
    await test_db.commit()
    test_db.expunge_all()
    with patch("app.storage.get_storage", return_value=storage):
        yield scroll


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/scroll/{hash}", "/2026/egress-test", "/2026/egress-test/v1"])
async def test_scroll_page_does_not_read_or_send_the_paper(client, test_db, inline_scroll, path):
    with html_content_reads(test_db) as reads:
        resp = await client.get(path.format(hash=inline_scroll.url_hash))

    assert resp.status_code == 200
    assert MARKER not in resp.text
    assert reads == []


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/scroll/{hash}/paper", "/2026/egress-test/paper"])
async def test_not_modified_answer_does_not_read_the_paper(client, test_db, inline_scroll, path):
    etag = paper_etag(inline_scroll.content_hash)
    with html_content_reads(test_db) as reads:
        resp = await client.get(
            path.format(hash=inline_scroll.url_hash), headers={"If-None-Match": etag}
        )

    assert resp.status_code == 304
    assert reads == []


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/scroll/{hash}/paper", "/2026/egress-test/paper"])
async def test_paper_is_still_sent_in_full(client, test_db, inline_scroll, path):
    resp = await client.get(path.format(hash=inline_scroll.url_hash))

    assert resp.status_code == 200
    assert MARKER in resp.text


CLOUDFLARE_KEEPS_A_DAY = "public, max-age=0, must-revalidate, s-maxage=86400"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/scroll/{hash}/paper", "/scroll/{hash}/paper/"])
@pytest.mark.parametrize("etag_sent", [False, True])
async def test_paper_by_hash_may_be_kept_by_cloudflare(client, inline_scroll, path, etag_sent):
    etag = paper_etag(inline_scroll.content_hash)
    headers = {"If-None-Match": etag} if etag_sent else {}
    resp = await client.get(path.format(hash=inline_scroll.url_hash), headers=headers)

    assert resp.status_code == (304 if etag_sent else 200)
    assert resp.headers["cache-control"] == CLOUDFLARE_KEEPS_A_DAY
    assert resp.headers["etag"] == etag


@pytest.mark.asyncio
async def test_latest_version_url_is_not_kept_by_shared_caches(client, inline_scroll):
    """/{year}/{slug}/paper changes when a new version is published."""
    resp = await client.get("/2026/egress-test/paper")

    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["etag"] == paper_etag(inline_scroll.content_hash)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/scroll/{hash}/paper", "/scroll/{hash}/paper/"])
async def test_preview_paper_is_never_kept_by_a_shared_cache(
    client, test_db, test_user, inline_scroll, path
):
    from app.auth.session import create_session

    scroll = await test_db.get(Scroll, inline_scroll.id)
    scroll.status = "preview"
    await test_db.commit()
    client.cookies.set("session_id", await create_session(test_db, test_user.id))

    resp = await client.get(path.format(hash=inline_scroll.url_hash))

    assert resp.status_code == 200
    assert MARKER in resp.text
    assert resp.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/scroll/000000000000/paper", "/scroll/000000000000/paper/"])
async def test_missing_paper_answer_carries_no_cache_mark(client, path):
    """Cloudflare's rule passes answers without a mark straight through, so a paper
    requested before it is published is not stuck as "not found"."""
    resp = await client.get(path)

    assert resp.status_code == 404
    assert "cache-control" not in resp.headers


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["paper/", "paper/style.css"])
async def test_archive_files_do_not_read_the_paper_column(client, test_db, archive_scroll, path):
    with html_content_reads(test_db) as reads:
        resp = await client.get(f"/scroll/{archive_scroll.url_hash}/{path}")

    assert resp.status_code == 200
    assert reads == []


@pytest.mark.asyncio
async def test_download_link_serves_the_original_file(client, inline_scroll):
    page = await client.get(f"/scroll/{inline_scroll.url_hash}")
    assert f'href="/scroll/{inline_scroll.url_hash}/download"' in page.text

    resp = await client.get(f"/scroll/{inline_scroll.url_hash}/download")

    assert resp.status_code == 200
    assert resp.text == PAPER
    assert resp.headers["content-disposition"] == 'attachment; filename="Egress_Test.html"'


@pytest.mark.asyncio
async def test_download_name_keeps_non_ascii_titles(client, test_db, inline_scroll):
    scroll = await test_db.get(Scroll, inline_scroll.id)
    scroll.title = "Über die Hypergraphen\r\nX"
    await test_db.commit()

    resp = await client.get(f"/scroll/{inline_scroll.url_hash}/download")

    assert resp.status_code == 200
    assert resp.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''%C3%9Cber_die_Hypergraphen__X.html"
    )


@pytest.mark.asyncio
async def test_preview_download_is_only_for_its_owner(client, test_db, inline_scroll):
    scroll = await test_db.get(Scroll, inline_scroll.id)
    scroll.status = "preview"
    await test_db.commit()

    resp = await client.get(f"/scroll/{inline_scroll.url_hash}/download")

    assert resp.status_code == 404
    assert MARKER not in resp.text
