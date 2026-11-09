"""Seeded example scrolls live at the addresses the homepage's example band links to.

Before, the seed built each address from the title, so on PR previews every example link
returned 404 (the band links to production's /2026/example-... addresses).
"""

from sqlalchemy import select

from app.models.scroll import Scroll
from app.routes.main import EXAMPLE_SCROLLS
from scripts.seed import seed_scrolls, seed_subjects, seed_users

# The preview deploy's limit (.github/workflows/preview.yml).
PREVIEW_MAX_HTML_BYTES = 5_000_000


async def _seeded(test_db, max_html_bytes=None):
    await seed_subjects(test_db)
    await seed_users(test_db)
    await seed_scrolls(test_db, max_html_bytes=max_html_bytes)
    rows = await test_db.execute(select(Scroll.title, Scroll.slug, Scroll.version))
    return rows.all()


def _example_slugs():
    return {e["title"]: e["href"].rsplit("/", 1)[-1] for e in EXAMPLE_SCROLLS}


async def test_examples_get_the_band_addresses(test_db):
    seeded = {(title, version): slug for title, slug, version in await _seeded(test_db)}

    for title, slug in _example_slugs().items():
        assert seeded.get((title, 1)) == slug, title


async def test_preview_limit_keeps_all_but_the_largest_example(test_db):
    titles = {title for title, _, _ in await _seeded(test_db, PREVIEW_MAX_HTML_BYTES)}

    assert "Damped Harmonic Oscillators: Three Characteristic Regimes" in titles
    assert "Graph Traversal Algorithms: BFS and DFS" in titles
    assert "The Spectral Theorem for Symmetric Matrices" in titles
    # 17 MB of inline HTML dropped the preview's database connection (July 2026).
    assert "Interactive Analysis of the Iris Dataset" not in titles


def test_preview_workflow_uses_that_limit():
    from pathlib import Path

    workflow = (Path(__file__).parent.parent / ".github/workflows/preview.yml").read_text()

    assert f"--max-html-bytes {PREVIEW_MAX_HTML_BYTES}" in workflow
