"""The scroll page talks to its paper only through the bridge script (prs-2m6, step 3).

These pass with or without the sandbox, so they must stay green when step 5 turns it on.
Papers are synthetic: each test writes its own paper bytes into the server's database.
"""

import uuid

from playwright.async_api import async_playwright, expect
import pytest
from sqlalchemy import select

from tests.e2e.conftest import launch_browser

pytestmark = pytest.mark.e2e

# Reads its setting at parse time, as RSM's reading settings do, and saves on a button.
PAPER = """<!DOCTYPE html>
<html><head><title>Bridge test {marker}</title>
<script>
  var saved = localStorage.getItem("rsm-reading");
  document.documentElement.setAttribute("data-saved", saved === null ? "none" : saved);
</script>
</head>
<body>
<p id="saved"></p>
<button id="save" onclick="localStorage.setItem('rsm-reading', this.dataset.value)"
        data-value="large-{marker}">Save</button>
<div style="height: 5000px">tall</div>
<p id="end">end</p>
<script>
  document.getElementById("saved").textContent =
    document.documentElement.getAttribute("data-saved");
</script>
</body></html>
"""


async def _publish_paper(server_db):
    from app.models.scroll import Scroll, Subject
    from app.models.user import User
    from app.storage.content_processing import generate_permanent_url

    marker = uuid.uuid4().hex[:8]
    html = PAPER.format(marker=marker)
    async with server_db() as db:
        user = (await db.execute(select(User).limit(1))).scalar_one()
        subject = (await db.execute(select(Subject).limit(1))).scalar_one()
        url_hash, content_hash, _ = await generate_permanent_url(db, html)
        scroll = Scroll(
            title=f"Bridge test {marker}",
            authors="Test Author",
            abstract="Synthetic paper for the bridge tests.",
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


async def _open(p):
    browser = await launch_browser(p)
    page = await browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    return browser, page, errors


async def test_reading_setting_survives_reload_on_scroll_page(test_server, server_db):
    url_hash, value = await _publish_paper(server_db)
    async with async_playwright() as p:
        browser, page, errors = await _open(p)
        try:
            await page.goto(f"{test_server}/scroll/{url_hash}")
            paper = page.frame_locator("#paper-frame")
            await expect(paper.locator("#saved")).to_have_text("none")
            await paper.locator("#save").click()
            await page.wait_for_function(
                "Object.keys(localStorage).some(k => k.startsWith('press-paper-settings:'))"
            )

            await page.reload()
            await expect(paper.locator("#saved")).to_have_text(value)

            # The paper never writes to Press's own storage, only through the scroll page.
            assert await page.evaluate("localStorage.getItem('rsm-reading')") is None
            assert errors == []
        finally:
            await browser.close()


async def test_each_paper_keeps_its_own_settings(test_server, server_db):
    first, _ = await _publish_paper(server_db)
    second, _ = await _publish_paper(server_db)
    async with async_playwright() as p:
        browser, page, _ = await _open(p)
        try:
            await page.goto(f"{test_server}/scroll/{first}")
            await page.frame_locator("#paper-frame").locator("#save").click()

            await page.goto(f"{test_server}/scroll/{second}")
            paper = page.frame_locator("#paper-frame")
            await expect(paper.locator("#saved")).to_have_text("none")
        finally:
            await browser.close()


async def test_back_to_top_follows_the_paper_scroll(test_server, server_db):
    url_hash, _ = await _publish_paper(server_db)
    async with async_playwright() as p:
        browser, page, errors = await _open(p)
        try:
            await page.goto(f"{test_server}/scroll/{url_hash}")
            top = page.locator("#top-fab")
            paper = page.frame_locator("#paper-frame")
            await expect(paper.locator("#saved")).to_have_text("none")
            await expect(top).not_to_have_class("fab-group-btn visible")

            await paper.locator("#end").scroll_into_view_if_needed()
            await expect(top).to_have_class("fab-group-btn visible")

            await top.click()
            frame = page.frame(url=f"{test_server}/scroll/{url_hash}/paper")
            await frame.wait_for_function("window.scrollY === 0")
            await expect(top).not_to_have_class("fab-group-btn visible")
            assert errors == []
        finally:
            await browser.close()


async def test_paper_url_opened_directly_still_works(test_server, server_db):
    """Not a reading surface, only a working URL: settings last until a reload."""
    url_hash, value = await _publish_paper(server_db)
    async with async_playwright() as p:
        browser, page, errors = await _open(p)
        try:
            await page.goto(f"{test_server}/scroll/{url_hash}/paper")
            await expect(page.locator("#saved")).to_have_text("none")
            await page.click("#save")
            assert await page.evaluate("localStorage.getItem('rsm-reading')") == value
            assert errors == []
        finally:
            await browser.close()


WORDS = " ".join(["Filler words so the content check sees a real document."] * 15)

ARCHIVE_INDEX = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Two page paper</title></head>
<body>
<h1>Page one</h1>
<p>{WORDS}</p>
<button id="save">Save</button>
<a id="next" href="page2.html">Next page</a>
<script>
  document.getElementById("save").addEventListener("click", function () {{
    localStorage.setItem("rsm-reading", "carried");
  }});
</script>
</body></html>"""

ARCHIVE_PAGE2 = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Page two</title></head>
<body>
<h1>Page two</h1>
<p>{WORDS}</p>
<p id="saved"></p>
<script>
  document.getElementById("saved").textContent = localStorage.getItem("rsm-reading");
</script>
</body></html>"""


async def test_setting_follows_the_paper_to_its_next_page(test_server):
    """An archive paper that links to its own second page keeps the reader's setting."""
    import os
    import tempfile
    import zipfile

    fd, zip_path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("index.html", ARCHIVE_INDEX)
        zf.writestr("page2.html", ARCHIVE_PAGE2)

    async with async_playwright() as p:
        browser, page, errors = await _open(p)
        try:
            await page.goto(f"{test_server}/login")
            await page.fill('input[name="email"]', "testuser@example.com")
            await page.fill('input[name="password"]', "testpass")
            await page.click('button[type="submit"]')
            await page.wait_for_url(f"{test_server}/dashboard", timeout=5000)

            await page.goto(f"{test_server}/upload")
            await page.fill('input[name="title"]', f"Two page paper {uuid.uuid4().hex[:8]}")
            await page.fill('input[name="authors"]', "E2E Author")
            await page.select_option('select[name="subject_id"]', label="Computer Science")
            await page.fill('textarea[name="abstract"]', "A paper with two pages.")
            await page.fill('input[name="keywords"]', "bridge")
            await page.set_input_files('input[type="file"]', zip_path)
            await page.check('input[value="cc-by-4.0"]')
            await page.check('input[name="confirm_rights"]')
            await page.click('form button[name="action"][value="publish"]')
            await expect(page.locator("body")).to_contain_text("Select Entry Point", timeout=10000)
            await page.locator('input[value="index.html"]').check()
            await page.click('#entry-point-form button[type="submit"]')
            await expect(page.locator("body")).to_contain_text("PREVIEW MODE", timeout=10000)

            paper = page.frame_locator("#paper-frame")
            await paper.locator("#save").click()
            await paper.locator("#next").click()
            await expect(paper.locator("#saved")).to_have_text("carried")
            assert errors == []
        finally:
            await browser.close()
            os.unlink(zip_path)
