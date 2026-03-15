"""Tests for social media link preview meta tags and OG image generation."""

import json

from bs4 import BeautifulSoup
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def published_scroll(test_db, test_user, test_subject):
    """Create a published scroll for social meta tag tests."""
    from tests.conftest import create_content_addressable_scroll

    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Quantum Entanglement in Biological Systems",
        authors="Dr. Alice Chen, Prof. Bob Martinez",
        abstract="We demonstrate quantum coherence in photosynthetic complexes at room temperature, challenging the assumption that biological systems are too warm for quantum effects.",
        keywords=["quantum biology", "entanglement", "photosynthesis"],
        html_content="<h1>Quantum Entanglement</h1><p>Content here</p>",
    )

    return scroll


# --- OpenGraph meta tag tests ---


@pytest.mark.asyncio
async def test_og_url_uses_base_url_not_hardcoded(client, published_scroll):
    """og:url must use configurable base_url, not hardcoded domain."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    og_url = soup.find("meta", {"property": "og:url"})
    assert og_url is not None

    # Must NOT contain hardcoded domain
    assert "https://scroll.press" not in og_url["content"] or og_url["content"].endswith(
        f"/scroll/{published_scroll.url_hash}"
    )


@pytest.mark.asyncio
async def test_og_image_present(client, published_scroll):
    """Published scrolls must have an og:image meta tag."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    og_image = soup.find("meta", {"property": "og:image"})
    assert og_image is not None
    assert og_image["content"].endswith("/og-image.png")


@pytest.mark.asyncio
async def test_og_image_dimensions_present(client, published_scroll):
    """og:image should have width and height tags for optimal rendering."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    og_width = soup.find("meta", {"property": "og:image:width"})
    og_height = soup.find("meta", {"property": "og:image:height"})
    assert og_width is not None
    assert og_height is not None
    assert og_width["content"] == "1200"
    assert og_height["content"] == "630"


@pytest.mark.asyncio
async def test_og_type_is_article(client, published_scroll):
    """og:type must be 'article' for scroll pages."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    og_type = soup.find("meta", {"property": "og:type"})
    assert og_type is not None
    assert og_type["content"] == "article"


@pytest.mark.asyncio
async def test_article_published_time_present(client, published_scroll):
    """article:published_time must be present for published scrolls."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    published_time = soup.find("meta", {"property": "article:published_time"})
    assert published_time is not None
    # ISO 8601 format
    assert "T" in published_time["content"]


@pytest.mark.asyncio
async def test_article_section_present(client, published_scroll):
    """article:section should map to the scroll's subject."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    section = soup.find("meta", {"property": "article:section"})
    assert section is not None
    assert section["content"] == "Computer Science"


@pytest.mark.asyncio
async def test_article_tags_present(client, published_scroll):
    """article:tag should include scroll keywords."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    tags = soup.find_all("meta", {"property": "article:tag"})
    tag_values = [t["content"] for t in tags]
    assert "quantum biology" in tag_values
    assert "entanglement" in tag_values
    assert "photosynthesis" in tag_values


# --- Twitter Card meta tag tests ---


@pytest.mark.asyncio
async def test_twitter_card_is_summary_large_image(client, published_scroll):
    """Twitter card should be summary_large_image when og:image exists."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    twitter_card = soup.find("meta", {"name": "twitter:card"})
    assert twitter_card is not None
    assert twitter_card["content"] == "summary_large_image"


@pytest.mark.asyncio
async def test_twitter_image_present(client, published_scroll):
    """twitter:image must be present for rich previews."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    twitter_image = soup.find("meta", {"name": "twitter:image"})
    assert twitter_image is not None
    assert twitter_image["content"].endswith("/og-image.png")


# --- JSON-LD structured data tests ---


@pytest.mark.asyncio
async def test_jsonld_present(client, published_scroll):
    """Scroll page should include JSON-LD structured data for search engines."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    script_tag = soup.find("script", {"type": "application/ld+json"})
    assert script_tag is not None

    data = json.loads(script_tag.string)
    assert data["@type"] == "ScholarlyArticle"
    assert data["name"] == published_scroll.title
    assert data["publisher"]["name"] == "Scroll Press"


@pytest.mark.asyncio
async def test_jsonld_authors_structured(client, published_scroll):
    """JSON-LD should list authors as structured Person objects."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    script_tag = soup.find("script", {"type": "application/ld+json"})
    data = json.loads(script_tag.string)

    assert "author" in data
    assert len(data["author"]) == 2
    assert data["author"][0]["@type"] == "Person"
    assert data["author"][0]["name"] == "Dr. Alice Chen"


# --- OG image endpoint tests ---


@pytest.mark.asyncio
async def test_og_image_endpoint_returns_png(client, published_scroll):
    """OG image endpoint should return a valid PNG image."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}/og-image.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    # PNG magic bytes
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_og_image_endpoint_404_for_nonexistent(client):
    """OG image endpoint should 404 for nonexistent scrolls."""
    response = await client.get("/scroll/nonexistent123/og-image.png")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_og_image_endpoint_cache_headers(client, published_scroll):
    """OG image should have cache-control headers for performance."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}/og-image.png")
    assert response.status_code == 200
    assert "cache-control" in response.headers
    assert "max-age" in response.headers["cache-control"]


# --- Abstract truncation tests ---


@pytest.mark.asyncio
async def test_og_description_truncation(client, published_scroll):
    """OG description should truncate long abstracts cleanly."""
    response = await client.get(f"/scroll/{published_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    og_desc = soup.find("meta", {"property": "og:description"})
    assert og_desc is not None
    # Should not exceed 300 chars (some room for the truncation marker)
    assert len(og_desc["content"]) <= 300


# --- Edge cases ---


@pytest.mark.asyncio
async def test_scroll_without_keywords_no_article_tags(client, test_db, test_user, test_subject):
    """Scrolls without keywords should not have article:tag meta tags."""
    from tests.conftest import create_content_addressable_scroll

    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="No Keywords Paper",
        authors="Author",
        abstract="Abstract",
        keywords=[],
        html_content="<p>Content</p>",
    )

    response = await client.get(f"/scroll/{scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    tags = soup.find_all("meta", {"property": "article:tag"})
    assert len(tags) == 0
