"""The subject on a scroll card links to that subject's list on the homepage (prs-g1v).

The homepage must honor ?subject= on a fresh load, not only after an HTMX click,
otherwise the link, a reload and a shared address all show every subject.
"""

from html.parser import HTMLParser

import pytest_asyncio

from app.models.scroll import Subject
from tests.conftest import create_content_addressable_scroll


@pytest_asyncio.fixture
async def two_subjects(test_db, test_user, test_subject):
    maths = Subject(name="Mathematics", description="Maths")
    test_db.add(maths)
    await test_db.commit()
    cs_scroll = await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="A computing scroll", html_content="<p>cs</p>"
    )
    maths_scroll = await create_content_addressable_scroll(
        test_db, test_user, maths, title="A maths scroll", html_content="<p>maths</p>"
    )
    return cs_scroll, maths_scroll


class _Links(HTMLParser):
    """Records each link's href and whether it sits inside another link."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append((dict(attrs).get("href"), self.depth > 0))
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == "a":
            self.depth -= 1


def _links(html: str):
    parser = _Links()
    parser.feed(html)
    return parser.links


class TestHomepageHonorsSubject:
    async def test_fresh_load_shows_only_that_subject(self, client, two_subjects):
        response = await client.get("/?subject=Mathematics")

        assert response.status_code == 200
        assert "Recent Mathematics Scrolls" in response.text
        assert "A maths scroll" in response.text
        assert "A computing scroll" not in response.text

    async def test_subject_with_a_space(self, client, two_subjects):
        response = await client.get("/?subject=Computer%20Science")

        assert "Recent Computer Science Scrolls" in response.text
        assert "A computing scroll" in response.text
        assert "A maths scroll" not in response.text

    async def test_show_all_is_not_marked_active_when_filtered(self, client, two_subjects):
        response = await client.get("/?subject=Mathematics")

        assert 'class="show-all-btn active"' not in response.text

    async def test_no_subject_shows_everything(self, client, two_subjects):
        response = await client.get("/")

        assert "Recent Scrolls" in response.text
        assert "A maths scroll" in response.text
        assert "A computing scroll" in response.text
        assert 'class="show-all-btn active"' in response.text


class TestSubjectIsALink:
    async def test_homepage_cards(self, client, two_subjects):
        response = await client.get("/")

        links = _links(response.text)
        assert ("/?subject=Mathematics", False) in links
        assert ("/?subject=Computer%20Science", False) in links

    async def test_filtered_list_from_the_subject_buttons(self, client, two_subjects):
        response = await client.get("/partials/scrolls?subject=Mathematics")

        assert ("/?subject=Mathematics", False) in _links(response.text)

    async def test_scroll_details_modal(self, client, test_db, two_subjects):
        _, maths_scroll = two_subjects
        maths_scroll.publication_year, maths_scroll.slug = 2026, "a-maths-scroll"
        await test_db.commit()

        response = await client.get("/2026/a-maths-scroll")

        assert response.status_code == 200
        assert ("/?subject=Mathematics", False) in _links(response.text)

    async def test_search_results(self, client, two_subjects):
        response = await client.get("/search?q=maths")

        assert ("/?subject=Mathematics", False) in _links(response.text)

    async def test_no_unclickable_subject_left(self, client, two_subjects):
        for path in ("/", "/search?q=maths", "/partials/scrolls"):
            response = await client.get(path)
            assert "preview-subject-link" not in response.text, path
