"""Tests for the /api/v1/ public REST API for AI agent access."""

from datetime import datetime, timezone

from httpx import AsyncClient
import pytest
import pytest_asyncio

from tests.conftest import create_content_addressable_scroll


@pytest_asyncio.fixture
async def published_scroll(test_db, test_user, test_subject):
    """Create a published scroll for API tests."""
    return await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Quantum Computing in Practice",
        authors="Alice Smith, Bob Jones",
        abstract="A study of practical quantum computing applications.",
        keywords=["quantum", "computing", "algorithms"],
        license="cc-by-4.0",
    )


@pytest_asyncio.fixture
async def second_scroll(test_db, test_user, test_subject):
    """Create a second published scroll for list/search tests."""
    return await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Neural Networks for Climate Modeling",
        authors="Carol Davis, Eve Wilson",
        abstract="Deep learning approaches to climate prediction.",
        keywords=["neural networks", "climate", "deep learning"],
        license="arr",
        html_content="<h1>Neural Networks for Climate Modeling</h1><p>Content here.</p>",
    )


@pytest_asyncio.fixture
async def second_subject(test_db):
    """Create a second subject."""
    from app.models.scroll import Subject

    subject = Subject(
        name="Physics",
        description="Physical sciences and related fields",
    )
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)
    return subject


# --- GET /api/v1/scrolls (search/list) ---


class TestListScrolls:
    """Tests for the scrolls listing/search endpoint."""

    @pytest.mark.asyncio
    async def test_list_scrolls_empty(self, client: AsyncClient):
        response = await client.get("/api/v1/scrolls")
        assert response.status_code == 200
        data = response.json()
        assert data["scrolls"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["per_page"] == 20

    @pytest.mark.asyncio
    async def test_list_scrolls_returns_published(
        self, client: AsyncClient, published_scroll, second_scroll
    ):
        response = await client.get("/api/v1/scrolls")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["scrolls"]) == 2

    @pytest.mark.asyncio
    async def test_list_scrolls_metadata_fields(
        self, client: AsyncClient, published_scroll
    ):
        response = await client.get("/api/v1/scrolls")
        data = response.json()
        scroll = data["scrolls"][0]
        assert scroll["title"] == "Quantum Computing in Practice"
        assert scroll["authors"] == "Alice Smith, Bob Jones"
        assert scroll["abstract"] == "A study of practical quantum computing applications."
        assert scroll["keywords"] == ["quantum", "computing", "algorithms"]
        assert scroll["subject"] == "Computer Science"
        assert scroll["version"] == 1
        assert scroll["url_hash"] is not None
        assert scroll["license"] == "cc-by-4.0"
        assert "created_at" in scroll
        assert "published_at" in scroll

    @pytest.mark.asyncio
    async def test_list_scrolls_excludes_drafts(
        self, client: AsyncClient, test_db, test_user, test_subject
    ):
        from app.models.scroll import Scroll

        draft = Scroll(
            title="Draft Paper",
            authors="Draft Author",
            abstract="Not published yet",
            html_content="<h1>Draft</h1>",
            license="cc-by-4.0",
            status="preview",
            user_id=test_user.id,
            subject_id=test_subject.id,
        )
        test_db.add(draft)
        await test_db.commit()

        response = await client.get("/api/v1/scrolls")
        data = response.json()
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_search_by_query(
        self, client: AsyncClient, published_scroll, second_scroll
    ):
        response = await client.get("/api/v1/scrolls", params={"q": "quantum"})
        data = response.json()
        assert data["total"] == 1
        assert data["scrolls"][0]["title"] == "Quantum Computing in Practice"

    @pytest.mark.asyncio
    async def test_search_by_query_abstract(
        self, client: AsyncClient, published_scroll, second_scroll
    ):
        response = await client.get("/api/v1/scrolls", params={"q": "climate prediction"})
        data = response.json()
        assert data["total"] == 1
        assert data["scrolls"][0]["title"] == "Neural Networks for Climate Modeling"

    @pytest.mark.asyncio
    async def test_filter_by_author(
        self, client: AsyncClient, published_scroll, second_scroll
    ):
        response = await client.get("/api/v1/scrolls", params={"author": "Alice Smith"})
        data = response.json()
        assert data["total"] == 1
        assert data["scrolls"][0]["authors"] == "Alice Smith, Bob Jones"

    @pytest.mark.asyncio
    async def test_filter_by_subject(
        self, client: AsyncClient, published_scroll, second_scroll
    ):
        response = await client.get(
            "/api/v1/scrolls", params={"subject": "Computer Science"}
        )
        data = response.json()
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_pagination(
        self, client: AsyncClient, published_scroll, second_scroll
    ):
        response = await client.get("/api/v1/scrolls", params={"per_page": 1, "page": 1})
        data = response.json()
        assert len(data["scrolls"]) == 1
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["per_page"] == 1

    @pytest.mark.asyncio
    async def test_pagination_page_2(
        self, client: AsyncClient, published_scroll, second_scroll
    ):
        response = await client.get("/api/v1/scrolls", params={"per_page": 1, "page": 2})
        data = response.json()
        assert len(data["scrolls"]) == 1
        assert data["page"] == 2

    @pytest.mark.asyncio
    async def test_pagination_out_of_range(
        self, client: AsyncClient, published_scroll
    ):
        response = await client.get("/api/v1/scrolls", params={"page": 999})
        data = response.json()
        assert data["scrolls"] == []
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_per_page_rejects_over_100(
        self, client: AsyncClient, published_scroll
    ):
        response = await client.get("/api/v1/scrolls", params={"per_page": 500})
        assert response.status_code == 422


# --- GET /api/v1/scrolls/{url_hash} (single paper metadata) ---


class TestGetScroll:
    """Tests for the single scroll metadata endpoint."""

    @pytest.mark.asyncio
    async def test_get_scroll_by_hash(
        self, client: AsyncClient, published_scroll
    ):
        response = await client.get(f"/api/v1/scrolls/{published_scroll.url_hash}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Quantum Computing in Practice"
        assert data["authors"] == "Alice Smith, Bob Jones"
        assert data["abstract"] == "A study of practical quantum computing applications."
        assert data["keywords"] == ["quantum", "computing", "algorithms"]
        assert data["subject"] == "Computer Science"
        assert data["license"] == "cc-by-4.0"
        assert data["version"] == 1
        assert data["url_hash"] == published_scroll.url_hash
        assert "created_at" in data
        assert "published_at" in data
        assert "citation" in data

    @pytest.mark.asyncio
    async def test_get_scroll_citation_format(
        self, client: AsyncClient, published_scroll
    ):
        response = await client.get(f"/api/v1/scrolls/{published_scroll.url_hash}")
        data = response.json()
        citation = data["citation"]
        assert "Alice Smith" in citation
        assert "Bob Jones" in citation
        assert "Quantum Computing in Practice" in citation

    @pytest.mark.asyncio
    async def test_get_scroll_with_doi(
        self, client: AsyncClient, test_db, published_scroll
    ):
        published_scroll.doi = "10.1234/test.5678"
        published_scroll.doi_status = "minted"
        published_scroll.doi_minted_at = datetime.now(timezone.utc)
        await test_db.commit()
        await test_db.refresh(published_scroll)

        response = await client.get(f"/api/v1/scrolls/{published_scroll.url_hash}")
        data = response.json()
        assert data["doi"] == "10.1234/test.5678"

    @pytest.mark.asyncio
    async def test_get_scroll_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/scrolls/nonexistent123")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_draft_scroll_returns_404(
        self, client: AsyncClient, test_db, test_user, test_subject
    ):
        from app.models.scroll import Scroll

        draft = Scroll(
            title="Draft Paper",
            authors="Draft Author",
            abstract="Not published yet",
            html_content="<h1>Draft</h1>",
            license="cc-by-4.0",
            status="preview",
            url_hash="draft123hash",
            content_hash="a" * 64,
            user_id=test_user.id,
            subject_id=test_subject.id,
        )
        test_db.add(draft)
        await test_db.commit()

        response = await client.get("/api/v1/scrolls/draft123hash")
        assert response.status_code == 404


# --- GET /api/v1/scrolls/{url_hash}/content (full-text content) ---


class TestGetScrollContent:
    """Tests for the full-text content endpoint."""

    @pytest.mark.asyncio
    async def test_get_content_html(
        self, client: AsyncClient, published_scroll
    ):
        response = await client.get(
            f"/api/v1/scrolls/{published_scroll.url_hash}/content"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "html"
        assert "<h1>" in data["content"]
        assert data["license"] == "cc-by-4.0"
        assert "citation" in data

    @pytest.mark.asyncio
    async def test_get_content_plain_text(
        self, client: AsyncClient, published_scroll
    ):
        response = await client.get(
            f"/api/v1/scrolls/{published_scroll.url_hash}/content",
            params={"format": "text"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "text"
        assert "<h1>" not in data["content"]
        assert "Test Content" in data["content"]

    @pytest.mark.asyncio
    async def test_get_content_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/scrolls/nonexistent123/content")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_content_invalid_format(
        self, client: AsyncClient, published_scroll
    ):
        response = await client.get(
            f"/api/v1/scrolls/{published_scroll.url_hash}/content",
            params={"format": "pdf"},
        )
        assert response.status_code == 422


# --- GET /api/v1/subjects ---


class TestListSubjects:
    """Tests for the subjects listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_subjects_empty(self, client: AsyncClient):
        response = await client.get("/api/v1/subjects")
        assert response.status_code == 200
        data = response.json()
        assert data["subjects"] == []

    @pytest.mark.asyncio
    async def test_list_subjects_with_counts(
        self, client: AsyncClient, published_scroll, second_scroll, test_subject
    ):
        response = await client.get("/api/v1/subjects")
        data = response.json()
        assert len(data["subjects"]) == 1
        cs = data["subjects"][0]
        assert cs["name"] == "Computer Science"
        assert cs["scroll_count"] == 2

    @pytest.mark.asyncio
    async def test_list_subjects_excludes_drafts_from_count(
        self, client: AsyncClient, test_db, test_user, test_subject, published_scroll
    ):
        from app.models.scroll import Scroll

        draft = Scroll(
            title="Draft Paper",
            authors="Draft Author",
            abstract="Not published",
            html_content="<h1>Draft</h1>",
            license="cc-by-4.0",
            status="preview",
            user_id=test_user.id,
            subject_id=test_subject.id,
        )
        test_db.add(draft)
        await test_db.commit()

        response = await client.get("/api/v1/subjects")
        data = response.json()
        cs = data["subjects"][0]
        assert cs["scroll_count"] == 1

    @pytest.mark.asyncio
    async def test_list_subjects_multiple(
        self,
        client: AsyncClient,
        test_db,
        test_user,
        test_subject,
        second_subject,
        published_scroll,
    ):
        await create_content_addressable_scroll(
            test_db,
            test_user,
            second_subject,
            title="Particle Physics Today",
            authors="Frank Physics",
            abstract="Modern particle physics.",
            html_content="<h1>Physics Paper</h1>",
        )

        response = await client.get("/api/v1/subjects")
        data = response.json()
        assert len(data["subjects"]) == 2
        names = {s["name"] for s in data["subjects"]}
        assert names == {"Computer Science", "Physics"}


# --- Response format ---


class TestResponseFormat:
    """Tests for API response format and headers."""

    @pytest.mark.asyncio
    async def test_response_is_json(self, client: AsyncClient):
        response = await client.get("/api/v1/scrolls")
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_cors_headers_not_present_by_default(self, client: AsyncClient):
        """CORS is not configured for MVP -- verify no CORS headers leak."""
        response = await client.get("/api/v1/scrolls")
        assert "access-control-allow-origin" not in response.headers
