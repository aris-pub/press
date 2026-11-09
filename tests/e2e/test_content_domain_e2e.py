"""Papers load from the content domain, a different site from Press (prs-2m6).

The browser cannot resolve content.test, so requests to it are answered by the test
server with the original Host header. The browser still treats the paper as another
site, so what is allowed and blocked is real.

Tagged desktop and mobile so the desktop, mobile-chromium and mobile-webkit jobs all run
them. Papers are synthetic.
"""

import os
from urllib.parse import urlsplit
import uuid

import httpx
from playwright.async_api import async_playwright, expect
import pytest
import pytest_asyncio
from sqlalchemy import select

from tests.e2e.conftest import launch_browser

pytestmark = [pytest.mark.e2e, pytest.mark.desktop, pytest.mark.mobile]

DOMAIN = "content.test"
# Started by .github/workflows/ci.yml with CONTENT_DOMAIN, BASE_URL and PREVIEW_LINK_KEY set.
CI_CONTENT_SERVER = "http://127.0.0.1:8001"
# A test value, the same one ci.yml gives the content domain server.
PREVIEW_LINK_KEY = "e2e-preview-link-key-not-a-secret"

PAPER = """<!DOCTYPE html>
<html><head><title>Content domain test {marker}</title></head>
<body>
<p id="ls"></p><p id="ss"></p><p id="idb"></p>
<p id="parent"></p><p id="form"></p><p id="saved"></p>
<svg id="svg" width="20" height="20"><rect width="20" height="20" fill="teal"/></svg>
<form id="f" action="#"><button id="submit">Go</button></form>
<button id="save" onclick="localStorage.setItem('rsm-reading', 'large-{marker}')">Save</button>
<script>
  const set = (id, v) => { document.getElementById(id).textContent = v; };
  try { localStorage.setItem("k", "v"); set("ls", localStorage.getItem("k")); }
  catch (e) { set("ls", "error"); }
  try { sessionStorage.setItem("k", "v"); set("ss", sessionStorage.getItem("k")); }
  catch (e) { set("ss", "error"); }
  try {
    const r = indexedDB.open("t");
    r.onsuccess = () => set("idb", "ok");
    r.onerror = () => set("idb", "error");
  } catch (e) { set("idb", "error"); }
  try { window.parent.document.title; set("parent", "readable"); }
  catch (e) { set("parent", "blocked"); }
  document.getElementById("f").addEventListener("submit", (e) => {
    e.preventDefault();
    set("form", "submitted");
  });
  const saved = localStorage.getItem("rsm-reading");
  set("saved", saved === null ? "none" : saved);
</script>
</body></html>
"""


VALUE_STORED = """async (value) => {
  for (let i = 0; i < 100; i++) {
    const stored = Object.keys(localStorage)
      .filter(k => k.startsWith("press-paper-settings:"))
      .map(k => localStorage.getItem(k));
    if (stored.some(v => v && v.includes(value))) return true;
    await new Promise(r => setTimeout(r, 50));
  }
  return false;
}"""


@pytest_asyncio.fixture
async def content_server(test_server):
    """A Press server with CONTENT_DOMAIN set. Locally the test server runs in this
    process and reads the setting on every request, so it is switched on for this test."""
    if os.getenv("CI"):
        yield CI_CONTENT_SERVER
        return
    from app.config import get_base_url

    saved = {k: os.environ.get(k) for k in ("CONTENT_DOMAIN", "BASE_URL", "PREVIEW_LINK_KEY")}
    os.environ["CONTENT_DOMAIN"] = DOMAIN
    os.environ["BASE_URL"] = test_server
    os.environ["PREVIEW_LINK_KEY"] = PREVIEW_LINK_KEY
    get_base_url.cache_clear()
    try:
        yield test_server
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_base_url.cache_clear()


async def _preview_of_testuser(server_db):
    """A preview (never published) owned by the seeded testuser@example.com."""
    from app.models.scroll import Scroll, Subject
    from app.models.user import User
    from app.storage.content_processing import generate_permanent_url

    marker = uuid.uuid4().hex[:8]
    html = PAPER.replace("{marker}", marker)
    async with server_db() as db:
        user = (
            await db.execute(select(User).where(User.email == "testuser@example.com"))
        ).scalar_one()
        subject = (await db.execute(select(Subject).limit(1))).scalar_one()
        url_hash, content_hash, _ = await generate_permanent_url(db, html)
        db.add(
            Scroll(
                title=f"Preview test {marker}",
                authors="Test Author",
                abstract="Synthetic preview for the signed link tests.",
                keywords=[],
                html_content=html,
                license="cc-by-4.0",
                content_hash=content_hash,
                url_hash=url_hash,
                status="preview",
                user_id=user.id,
                subject_id=subject.id,
            )
        )
        await db.commit()
    return url_hash


async def _log_in(page, server):
    await page.goto(f"{server}/login")
    await page.fill('input[name="email"]', "testuser@example.com")
    await page.fill('input[name="password"]', "testpass")
    await page.click('button[type="submit"]')
    await page.wait_for_url(f"{server}/dashboard")


async def _publish(server_db):
    from app.models.scroll import Scroll, Subject
    from app.models.user import User
    from app.storage.content_processing import generate_permanent_url

    marker = uuid.uuid4().hex[:8]
    html = PAPER.replace("{marker}", marker)
    async with server_db() as db:
        user = (await db.execute(select(User).limit(1))).scalar_one()
        subject = (await db.execute(select(Subject).limit(1))).scalar_one()
        url_hash, content_hash, _ = await generate_permanent_url(db, html)
        scroll = Scroll(
            title=f"Content domain test {marker}",
            authors="Test Author",
            abstract="Synthetic paper for the content domain tests.",
            keywords=[],
            html_content=html,
            license="cc-by-4.0",
            content_hash=content_hash,
            url_hash=url_hash,
            status="published",
            user_id=user.id,
            subject_id=subject.id,
        )
        scroll.publish()
        db.add(scroll)
        await db.commit()
    return url_hash, f"large-{marker}"


async def _open(p, server):
    """A page whose requests to the content domain are answered by the test server."""
    browser = await launch_browser(p)
    context = await browser.new_context()
    content_requests = []

    async def answer(route):
        request = route.request
        parts = urlsplit(request.url)
        content_requests.append(request)
        headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
        headers["host"] = parts.netloc
        target = f"{server}{parts.path}" + (f"?{parts.query}" if parts.query else "")
        async with httpx.AsyncClient() as client:
            response = await client.request(request.method, target, headers=headers)
        dropped = {"content-encoding", "content-length", "transfer-encoding"}
        await route.fulfill(
            status=response.status_code,
            headers={k: v for k, v in response.headers.items() if k.lower() not in dropped},
            body=response.content,
        )

    await context.route(f"http://*.{DOMAIN}/**", answer)
    page = await context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    return browser, page, errors, content_requests


async def test_paper_loads_from_the_content_domain(content_server, server_db):
    url_hash, _ = await _publish(server_db)
    async with async_playwright() as p:
        browser, page, errors, _ = await _open(p, content_server)
        try:
            await page.goto(f"{content_server}/scroll/{url_hash}")
            paper = page.frame_locator("#paper-frame")
            await expect(paper.locator("#ls")).to_have_text("v")

            frame = page.frame(url=f"http://{url_hash}.{DOMAIN}/")
            assert frame is not None
            assert errors == []
        finally:
            await browser.close()


async def test_paper_features_still_work(content_server, server_db):
    """What the sandbox would have broken: storage, forms, SVG."""
    url_hash, _ = await _publish(server_db)
    async with async_playwright() as p:
        browser, page, _, _ = await _open(p, content_server)
        try:
            await page.goto(f"{content_server}/scroll/{url_hash}")
            paper = page.frame_locator("#paper-frame")
            await expect(paper.locator("#ls")).to_have_text("v")
            await expect(paper.locator("#ss")).to_have_text("v")
            await expect(paper.locator("#idb")).to_have_text("ok")
            await expect(paper.locator("#svg")).to_be_visible()

            await paper.locator("#submit").click()
            await expect(paper.locator("#form")).to_have_text("submitted")
        finally:
            await browser.close()


async def test_paper_cannot_read_the_scroll_page(content_server, server_db):
    url_hash, _ = await _publish(server_db)
    async with async_playwright() as p:
        browser, page, _, _ = await _open(p, content_server)
        try:
            await page.goto(f"{content_server}/scroll/{url_hash}")
            await expect(page.frame_locator("#paper-frame").locator("#parent")).to_have_text(
                "blocked"
            )
        finally:
            await browser.close()


async def test_paper_requests_never_carry_the_press_login(content_server, server_db):
    url_hash, _ = await _publish(server_db)
    async with async_playwright() as p:
        browser, page, _, content_requests = await _open(p, content_server)
        try:
            await page.goto(f"{content_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')
            await page.wait_for_url(f"{content_server}/dashboard")
            assert any(c["name"] == "session_id" for c in await page.context.cookies())

            await page.goto(f"{content_server}/scroll/{url_hash}")
            await expect(page.frame_locator("#paper-frame").locator("#ls")).to_have_text("v")

            assert content_requests
            for request in content_requests:
                assert "session_id" not in (await request.all_headers()).get("cookie", "")
        finally:
            await browser.close()


async def test_reading_setting_survives_reload(content_server, server_db):
    """The bridge still carries the reader's settings between the paper and Press."""
    url_hash, value = await _publish(server_db)
    async with async_playwright() as p:
        browser, page, errors, _ = await _open(p, content_server)
        try:
            await page.goto(f"{content_server}/scroll/{url_hash}")
            paper = page.frame_locator("#paper-frame")
            await expect(paper.locator("#saved")).to_have_text("none")
            await paper.locator("#save").click()
            # Reload only once the scroll page has stored this value. This paper also writes
            # "k" on load, which sends its own settings message, so waiting for any stored
            # settings (SETTINGS_SAVED in the bridge tests) would not be enough here.
            assert await page.evaluate(VALUE_STORED, value)

            await page.reload()
            await expect(page.frame_locator("#paper-frame").locator("#saved")).to_have_text(value)
            assert errors == []
        finally:
            await browser.close()


async def test_old_paper_address_redirects(content_server, server_db):
    url_hash, _ = await _publish(server_db)
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{content_server}/scroll/{url_hash}/paper")

    assert response.status_code == 301
    assert response.headers["location"] == f"http://{url_hash}.{DOMAIN}/"


async def test_owner_preview_loads_through_a_signed_link(content_server, server_db):
    """prs-2m6.1: the preview's paper comes from the content domain, not from Press."""
    url_hash = await _preview_of_testuser(server_db)
    async with async_playwright() as p:
        browser, page, errors, content_requests = await _open(p, content_server)
        try:
            await _log_in(page, content_server)
            await page.goto(f"{content_server}/preview/{url_hash}")
            paper = page.frame_locator("#paper-frame")
            await expect(paper.locator("#ls")).to_have_text("v")
            await expect(paper.locator("#parent")).to_have_text("blocked")

            hosts = {urlsplit(r.url).hostname for r in content_requests}
            assert any(h.startswith(f"{url_hash}-") for h in hosts), hosts
            for request in content_requests:
                assert "session_id" not in (await request.all_headers()).get("cookie", "")
            assert errors == []
        finally:
            await browser.close()


async def test_preview_without_a_valid_link_is_refused(content_server, server_db):
    url_hash = await _preview_of_testuser(server_db)
    async with httpx.AsyncClient() as client:
        unsigned = await client.get(f"{content_server}/", headers={"host": f"{url_hash}.{DOMAIN}"})
        forged = await client.get(
            f"{content_server}/", headers={"host": f"{url_hash}-9999999999-{'0' * 32}.{DOMAIN}"}
        )

    assert unsigned.status_code == 404
    assert forged.status_code == 404
