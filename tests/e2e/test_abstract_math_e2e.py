"""MathJax typesets the math in abstracts, and only that (prs-58a).

Checks the real thing in a browser: the loader runs under each page's CSP, MathJax and
its fonts load from Press, formulas become MathJax output, money stays text, and pages
without math never fetch MathJax.
"""

import uuid

from playwright.async_api import async_playwright, expect
import pytest
from sqlalchemy import select

from tests.e2e.conftest import launch_browser

pytestmark = [pytest.mark.e2e, pytest.mark.desktop, pytest.mark.mobile]

ABSTRACT = r"Every metric space embeds with distortion $O(\log n)$. Runs cost between $5 and $10."
MATHJAX = "/static/vendor/mathjax-3.2.2/tex-chtml-full.js"


async def _publish(server_db):
    from app.models.scroll import Scroll, Subject
    from app.models.user import User
    from app.storage.content_processing import generate_permanent_url

    marker = uuid.uuid4().hex[:8]
    html = f"<!DOCTYPE html><html><body><h1>Math {marker}</h1></body></html>"
    async with server_db() as db:
        user = (await db.execute(select(User).limit(1))).scalar_one()
        subject = (
            await db.execute(select(Subject).where(Subject.name == "Mathematics"))
        ).scalar_one()
        url_hash, content_hash, _ = await generate_permanent_url(db, html)
        scroll = Scroll(
            title=f"Abstract math {marker}",
            authors="Test Author",
            abstract=ABSTRACT,
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
    return f"Abstract math {marker}", url_hash


async def _open(p):
    browser = await launch_browser(p)
    page = await browser.new_page()
    problems = []
    page.on("pageerror", lambda e: problems.append(str(e)))
    page.on(
        "console",
        lambda m: problems.append(m.text)
        if m.type == "error" and "Content Security Policy" in m.text
        else None,
    )
    return browser, page, problems


async def _typeset(card):
    abstract = card.locator(".scroll-abstract")
    await expect(abstract.locator("mjx-container")).to_have_count(1, timeout=15000)
    await expect(abstract).to_contain_text("between $5 and $10")
    assert "\\(" not in await abstract.inner_text()


async def test_homepage_card(test_server, server_db):
    title, _ = await _publish(server_db)
    async with async_playwright() as p:
        browser, page, problems = await _open(p)
        try:
            await page.goto(test_server)
            await _typeset(page.locator(".scroll.preview", has_text=title))
            assert problems == []
        finally:
            await browser.close()


async def test_after_subject_filtering(test_server, server_db):
    """The filtered list is swapped in by htmx, without a page load."""
    title, _ = await _publish(server_db)
    async with async_playwright() as p:
        browser, page, problems = await _open(p)
        try:
            await page.goto(test_server)
            await page.locator(".subject-card", has_text="Mathematics").click()
            await expect(page.locator("#recent-submissions-heading")).to_have_text(
                "Recent Mathematics Scrolls"
            )
            await _typeset(page.locator(".scroll.preview", has_text=title))
            assert problems == []
        finally:
            await browser.close()


async def test_scroll_details_modal(test_server, server_db):
    title, url_hash = await _publish(server_db)
    async with async_playwright() as p:
        browser, page, problems = await _open(p)
        try:
            await page.goto(f"{test_server}/scroll/{url_hash}")
            await page.locator("#info-fab").click()
            await _typeset(page.locator("#info-modal .scroll.preview"))
            assert problems == []
        finally:
            await browser.close()


async def test_pages_without_math_never_fetch_mathjax(test_server):
    async with async_playwright() as p:
        browser, page, _ = await _open(p)
        requests = []
        page.on("request", lambda r: requests.append(r.url))
        try:
            await page.goto(f"{test_server}/about")
            await page.wait_for_load_state("load")
            assert not [u for u in requests if MATHJAX in u]
        finally:
            await browser.close()
