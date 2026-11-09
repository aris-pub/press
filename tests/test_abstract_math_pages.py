"""Every page that shows an abstract marks its math for MathJax (prs-58a)."""

import pytest_asyncio

from tests.conftest import create_content_addressable_scroll

ABSTRACT = r"Bourgain shows $O(\log n)$ distortion. Runs cost between $5 and $10. <b>bold</b>"
MATH = '<span class="math-tex">\\(O(\\log n)\\)</span>'
LOADER = "/static/js/abstract-math.js"


@pytest_asyncio.fixture
async def scroll(test_db, test_user, test_subject):
    scroll = await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="Embedding paper", abstract=ABSTRACT
    )
    scroll.publication_year, scroll.slug = 2026, "embedding-paper"
    await test_db.commit()
    return scroll


def _check(html: str):
    assert MATH in html
    assert "between $5 and $10" in html
    assert "&lt;b&gt;bold&lt;/b&gt;" in html
    assert "<b>bold</b>" not in html
    assert LOADER in html


async def test_homepage_card(client, scroll):
    _check((await client.get("/")).text)


async def test_subject_filter_list(client, scroll):
    html = (await client.get("/partials/scrolls?subject=Computer%20Science")).text
    assert MATH in html
    assert "between $5 and $10" in html


async def test_scroll_details_modal(client, scroll):
    _check((await client.get("/2026/embedding-paper")).text)


async def test_scroll_page_loader_carries_the_nonce(client, scroll):
    """Where the scroll page CSP uses a nonce, it only runs scripts that carry it."""
    for path in ("/2026/embedding-paper", f"/scroll/{scroll.url_hash}"):
        response = await client.get(path, follow_redirects=True)
        csp = response.headers["content-security-policy"]
        if "'nonce-" in csp:
            nonce = csp.split("'nonce-", 1)[1].split("'", 1)[0]
            tag = f'<script src="{LOADER}" nonce="{nonce}" defer></script>'
        else:
            tag = f'<script src="{LOADER}" defer></script>'
        assert tag in response.text, path


async def test_search_results(client, scroll):
    html = (await client.get("/search?q=distortion")).text
    _check(html)
    assert "<mark>distortion</mark>" in html


async def test_dashboard(authenticated_client, scroll):
    _check((await authenticated_client.get("/dashboard")).text)


async def test_preview_page(authenticated_client, test_db, test_user, test_subject):
    preview = await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="Preview paper", abstract=ABSTRACT
    )
    preview.status = "preview"
    preview.published_at = None
    await test_db.commit()

    _check((await authenticated_client.get(f"/preview/{preview.url_hash}")).text)
