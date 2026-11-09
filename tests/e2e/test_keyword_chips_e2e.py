"""Each keyword chip on a scroll card stays on one line (prs-a21).

Long keywords like "finite metric spaces" used to wrap inside their chip, giving two
and three line chips. Chips should wrap as whole units instead.
"""

import uuid

from playwright.async_api import async_playwright
import pytest
from sqlalchemy import select

from tests.e2e.conftest import launch_browser

pytestmark = [pytest.mark.e2e, pytest.mark.desktop, pytest.mark.mobile]

KEYWORDS = [
    "metric embeddings",
    "Lipschitz embedding",
    "finite metric spaces",
    "low-distortion embeddings of finite metric spaces",
    "distortion",
    "random graphs",
]


async def _publish(server_db):
    from app.models.scroll import Scroll, Subject
    from app.models.user import User
    from app.storage.content_processing import generate_permanent_url

    marker = uuid.uuid4().hex[:8]
    html = f"<!DOCTYPE html><html><body><h1>Chips {marker}</h1></body></html>"
    async with server_db() as db:
        user = (await db.execute(select(User).limit(1))).scalar_one()
        subject = (await db.execute(select(Subject).limit(1))).scalar_one()
        url_hash, content_hash, _ = await generate_permanent_url(db, html)
        scroll = Scroll(
            title=f"Keyword chips {marker}",
            authors="Test Author",
            abstract="Synthetic scroll with long keywords.",
            keywords=KEYWORDS,
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
    return f"Keyword chips {marker}"


@pytest.mark.parametrize("width", [1280, 375])
async def test_each_chip_stays_on_one_line(test_server, server_db, width):
    title = await _publish(server_db)
    async with async_playwright() as p:
        browser = await launch_browser(p)
        page = await browser.new_page(viewport={"width": width, "height": 900})
        try:
            await page.goto(test_server)
            card = page.locator(".scroll.preview", has_text=title)
            chips = card.locator(".tag")
            assert await chips.count() == len(KEYWORDS)

            # Count the text's line boxes. Chip heights alone cannot show it, because the
            # row stretches every chip to the height of the tallest one.
            lines = await chips.evaluate_all(
                """els => els.map(el => {
                    const range = document.createRange();
                    range.selectNodeContents(el);
                    return new Set([...range.getClientRects()].map(r => Math.round(r.top))).size;
                })"""
            )
            assert lines == [1] * len(KEYWORDS), list(zip(KEYWORDS, lines))

            card_box = await card.bounding_box()
            for i in range(len(KEYWORDS)):
                box = await chips.nth(i).bounding_box()
                assert box["x"] + box["width"] <= card_box["x"] + card_box["width"] + 1, i
        finally:
            await browser.close()
