"""Tests for the agent-friendly alternate representations of a scroll.

A canonical scroll page lives at /{year}/{slug}. For non-browser clients (curl,
agentic tools, indexers) the chrome+iframe wrapping makes the actual manuscript
invisible. We expose:

- /{year}/{slug}/paper        -> bare manuscript HTML, no chrome
- /{year}/{slug}.json         -> structured metadata + cite_as; NOT inlining HTML
- /{year}/{slug}/v{N}/paper   -> versioned bare HTML
- /{year}/{slug}/v{N}.json    -> versioned metadata
- Canonical page also advertises both via <link rel="alternate"> and Link:
- Canonical page 303-redirects to .json when Accept: application/json.
"""

from datetime import datetime, timezone
import uuid

import pytest
import pytest_asyncio

from app.auth.utils import get_password_hash
from app.models.scroll import Scroll, Subject
from app.models.user import User


@pytest_asyncio.fixture
async def subject(test_db):
    subj = Subject(name="Physics", description="Physics research")
    test_db.add(subj)
    await test_db.commit()
    await test_db.refresh(subj)
    return subj


@pytest_asyncio.fixture
async def user(test_db):
    u = User(
        email="alt-rep-test@example.com",
        password_hash=get_password_hash("testpass123"),
        display_name="Alt Rep Tester",
        email_verified=True,
    )
    test_db.add(u)
    await test_db.commit()
    await test_db.refresh(u)
    return u


_BARE_HTML = (
    "<!DOCTYPE html><html><head><title>Bare</title></head>"
    "<body><h1>Bare body marker</h1><p>The manuscript text lives here.</p></body></html>"
)


def _make_scroll(user, subject, **overrides):
    defaults = dict(
        title="Quantum Entanglement in Many-Body Systems",
        authors="Alice Physicist, Bob Theorist",
        abstract="We study entanglement in many-body systems.",
        keywords=["entanglement", "many-body"],
        html_content=_BARE_HTML,
        license="cc-by-4.0",
        content_hash=uuid.uuid4().hex,
        url_hash=uuid.uuid4().hex[:12],
        status="published",
        user_id=user.id,
        subject_id=subject.id,
        published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        publication_year=2026,
        slug="quantum-entanglement",
        version=1,
        storage_type="inline",
    )
    defaults.update(overrides)
    return Scroll(**defaults)


class TestBarePaperRoute:
    """GET /{year}/{slug}/paper returns the manuscript HTML with no chrome."""

    @pytest.mark.asyncio
    async def test_returns_bare_html_for_inline_scroll(self, client, test_db, user, subject):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get("/2026/quantum-entanglement/paper")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "Bare body marker" in response.text
        # No chrome: the canonical page wraps an iframe; the bare URL must not.
        assert "<iframe" not in response.text.lower()
        # ETag derived from content hash, quoted per RFC.
        assert response.headers.get("etag") == f'"{scroll.content_hash}"'

    @pytest.mark.asyncio
    async def test_versioned_paper_route(self, client, test_db, user, subject):
        scroll = _make_scroll(user, subject, version=1)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get("/2026/quantum-entanglement/v1/paper")
        assert response.status_code == 200
        assert "Bare body marker" in response.text

    @pytest.mark.asyncio
    async def test_404_for_unknown_slug(self, client, test_db, user, subject):
        response = await client.get("/2026/no-such-paper/paper")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_archive_scroll_redirects_to_hash_url(
        self, client, test_db, user, subject
    ):
        scroll = _make_scroll(
            user,
            subject,
            storage_type="archive",
            entry_point="index.html",
            slug="archive-paper",
        )
        test_db.add(scroll)
        await test_db.commit()

        # follow_redirects=False so we can assert the 302 target
        response = await client.get(
            "/2026/archive-paper/paper", follow_redirects=False
        )
        assert response.status_code == 302
        assert response.headers["location"] == f"/scroll/{scroll.url_hash}/paper/"


class TestMetadataJsonRoute:
    """GET /{year}/{slug}.json returns structured metadata WITHOUT inlining HTML."""

    @pytest.mark.asyncio
    async def test_returns_metadata_shape(self, client, test_db, user, subject):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get("/2026/quantum-entanglement.json")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        data = response.json()

        # Core metadata
        assert data["title"] == scroll.title
        assert data["authors"] == scroll.authors
        assert data["year"] == 2026
        assert data["slug"] == "quantum-entanglement"
        assert data["version"] == 1
        assert data["license"] == "cc-by-4.0"
        assert data["subject"] == "Physics"
        assert data["url_hash"] == scroll.url_hash

        # URL fields
        assert data["canonical_url"].endswith("/2026/quantum-entanglement")
        assert data["paper_url"].endswith("/2026/quantum-entanglement/paper")
        assert data["paper_version_url"].endswith("/2026/quantum-entanglement/v1/paper")

        # Size / hash for the manuscript HTML
        assert data["html_sha256"] == scroll.content_hash
        assert data["html_bytes"] == len(_BARE_HTML.encode("utf-8"))

    @pytest.mark.asyncio
    async def test_does_not_inline_html(self, client, test_db, user, subject):
        """The JSON response must NOT contain the manuscript HTML inline.

        The whole point of the metadata endpoint is to be cheap: indexers should
        be able to fetch it, dedupe by hash, and choose whether to download the
        body separately. Inlining bloats responses and forces whole-document
        allocation before reading the abstract.
        """
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get("/2026/quantum-entanglement.json")
        data = response.json()
        # No top-level html field.
        assert "html" not in data
        # And the bare-HTML marker must not appear anywhere in the response body.
        assert "Bare body marker" not in response.text

    @pytest.mark.asyncio
    async def test_cite_as_bibtex_and_csl(self, client, test_db, user, subject):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get("/2026/quantum-entanglement.json")
        cite = response.json()["cite_as"]

        # BibTeX includes the title, both authors joined by 'and', and year.
        assert "@misc" in cite["bibtex"]
        assert "Quantum Entanglement in Many-Body Systems" in cite["bibtex"]
        assert " and " in cite["bibtex"]  # multi-author join
        assert "2026" in cite["bibtex"]

        # CSL-JSON has the standard fields and split authors.
        csl = cite["csl_json"]
        assert csl["title"] == scroll.title
        assert csl["type"] == "article"
        assert csl["issued"] == {"date-parts": [[2026]]}
        assert len(csl["author"]) == 2
        assert csl["author"][0] == {"family": "Physicist", "given": "Alice"}
        assert csl["author"][1] == {"family": "Theorist", "given": "Bob"}

    @pytest.mark.asyncio
    async def test_versioned_json_route(self, client, test_db, user, subject):
        scroll = _make_scroll(user, subject, version=2)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get("/2026/quantum-entanglement/v2.json")
        assert response.status_code == 200
        assert response.json()["version"] == 2


class TestCanonicalPageAdvertisesAlternates:
    """The chrome page must advertise the alternate representations both in
    HTML (<link rel="alternate">) and as RFC 8288 Link: headers."""

    @pytest.mark.asyncio
    async def test_link_rel_alternate_in_head(self, client, test_db, user, subject):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get("/2026/quantum-entanglement")
        assert response.status_code == 200
        assert (
            'rel="alternate" type="text/html"' in response.text
            and "/2026/quantum-entanglement/paper" in response.text
        )
        assert (
            'rel="alternate" type="application/json"' in response.text
            and "/2026/quantum-entanglement.json" in response.text
        )

    @pytest.mark.asyncio
    async def test_link_http_header_present(self, client, test_db, user, subject):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get("/2026/quantum-entanglement")
        link = response.headers.get("link", "")
        assert "/2026/quantum-entanglement/paper" in link
        assert "/2026/quantum-entanglement.json" in link
        assert 'rel="alternate"' in link

    @pytest.mark.asyncio
    async def test_accept_json_redirects_to_json_endpoint(
        self, client, test_db, user, subject
    ):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get(
            "/2026/quantum-entanglement",
            headers={"Accept": "application/json"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/2026/quantum-entanglement.json"

    @pytest.mark.asyncio
    async def test_accept_html_does_not_redirect(self, client, test_db, user, subject):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get(
            "/2026/quantum-entanglement",
            headers={"Accept": "text/html"},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "<iframe" in response.text.lower()


class TestConditionalRequests:
    """ETag / If-None-Match — agents should be able to cheaply re-check
    a known scroll without re-downloading the body."""

    @pytest.mark.asyncio
    async def test_if_none_match_on_paper_returns_304(
        self, client, test_db, user, subject
    ):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        first = await client.get("/2026/quantum-entanglement/paper")
        etag = first.headers["etag"]

        second = await client.get(
            "/2026/quantum-entanglement/paper",
            headers={"If-None-Match": etag},
        )
        assert second.status_code == 304
        assert second.content == b""
        # 304 must still echo the ETag so the client knows the validator.
        assert second.headers["etag"] == etag

    @pytest.mark.asyncio
    async def test_if_none_match_on_json_returns_304(
        self, client, test_db, user, subject
    ):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        first = await client.get("/2026/quantum-entanglement.json")
        etag = first.headers["etag"]

        second = await client.get(
            "/2026/quantum-entanglement.json",
            headers={"If-None-Match": etag},
        )
        assert second.status_code == 304
        assert second.content == b""

    @pytest.mark.asyncio
    async def test_if_none_match_star_returns_304(
        self, client, test_db, user, subject
    ):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get(
            "/2026/quantum-entanglement/paper",
            headers={"If-None-Match": "*"},
        )
        assert response.status_code == 304

    @pytest.mark.asyncio
    async def test_if_none_match_mismatch_returns_200(
        self, client, test_db, user, subject
    ):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get(
            "/2026/quantum-entanglement/paper",
            headers={"If-None-Match": '"some-unrelated-tag"'},
        )
        assert response.status_code == 200
        assert "Bare body marker" in response.text


class TestAlternateRoutesDoNotCollideWithCanonical:
    """Sanity check: declaring /{year}/{slug}.json and /{year}/{slug}/paper
    before /{year}/{slug} must not swallow the canonical route."""

    @pytest.mark.asyncio
    async def test_canonical_route_still_serves_chrome_page(
        self, client, test_db, user, subject
    ):
        scroll = _make_scroll(user, subject)
        test_db.add(scroll)
        await test_db.commit()

        response = await client.get("/2026/quantum-entanglement")
        assert response.status_code == 200
        # Chrome page renders the iframe wrapper, not the bare body.
        assert "<iframe" in response.text.lower()
