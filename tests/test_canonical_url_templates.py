"""Tests for canonical year/slug URL usage in templates."""

from bs4 import BeautifulSoup
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def scroll_with_slug(test_db, test_user, test_subject):
    """Create a published scroll with slug and publication_year set."""
    from tests.conftest import create_content_addressable_scroll

    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Quantum Entanglement in Biological Systems",
        authors="Dr. Alice Chen",
        abstract="We demonstrate quantum coherence in photosynthetic complexes.",
        keywords=["quantum biology"],
        html_content="<h1>Quantum Entanglement</h1><p>Content here</p>",
    )

    scroll.slug = "quantum-entanglement-in-biological-systems"
    scroll.publication_year = 2026
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)
    return scroll


@pytest_asyncio.fixture
async def scroll_without_slug(test_db, test_user, test_subject):
    """Create a published scroll without slug (legacy scroll)."""
    from tests.conftest import create_content_addressable_scroll

    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Legacy Scroll Without Slug",
        authors="Dr. Bob",
        abstract="A legacy scroll.",
        html_content="<h1>Legacy</h1><p>Content</p>",
    )
    return scroll


@pytest.mark.asyncio
async def test_og_url_uses_canonical_url(client, scroll_with_slug):
    """og:url should use /{year}/{slug} when slug and year are set."""
    response = await client.get(f"/scroll/{scroll_with_slug.url_hash}")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    og_url = soup.find("meta", {"property": "og:url"})
    assert og_url is not None
    assert "/2026/quantum-entanglement-in-biological-systems" in og_url["content"]
    assert f"/scroll/{scroll_with_slug.url_hash}" not in og_url["content"]


@pytest.mark.asyncio
async def test_og_url_falls_back_for_legacy_scroll(client, scroll_without_slug):
    """og:url should fall back to /scroll/{hash} when no slug."""
    response = await client.get(f"/scroll/{scroll_without_slug.url_hash}")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    og_url = soup.find("meta", {"property": "og:url"})
    assert og_url is not None
    assert f"/scroll/{scroll_without_slug.url_hash}" in og_url["content"]


@pytest.mark.asyncio
async def test_canonical_link_present(client, scroll_with_slug):
    """A <link rel='canonical'> should be present with the canonical URL."""
    response = await client.get(f"/scroll/{scroll_with_slug.url_hash}")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    canonical = soup.find("link", {"rel": "canonical"})
    assert canonical is not None
    assert "/2026/quantum-entanglement-in-biological-systems" in canonical["href"]


@pytest.mark.asyncio
async def test_canonical_link_fallback_for_legacy(client, scroll_without_slug):
    """Canonical link should fall back to hash URL for legacy scrolls."""
    response = await client.get(f"/scroll/{scroll_without_slug.url_hash}")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    canonical = soup.find("link", {"rel": "canonical"})
    assert canonical is not None
    assert f"/scroll/{scroll_without_slug.url_hash}" in canonical["href"]


@pytest.mark.asyncio
async def test_jsonld_url_uses_canonical(client, scroll_with_slug):
    """JSON-LD structured data url should use canonical URL."""
    import json

    response = await client.get(f"/scroll/{scroll_with_slug.url_hash}")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    jsonld_script = soup.find("script", {"type": "application/ld+json"})
    assert jsonld_script is not None
    data = json.loads(jsonld_script.string)
    assert "/2026/quantum-entanglement-in-biological-systems" in data["url"]


@pytest.mark.asyncio
async def test_iframe_src_still_uses_hash(client, scroll_with_slug):
    """iframe src must still use /scroll/{url_hash}/paper, not canonical URL."""
    response = await client.get(f"/scroll/{scroll_with_slug.url_hash}")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    iframe = soup.find("iframe", {"id": "paper-frame"})
    assert iframe is not None
    assert f"/scroll/{scroll_with_slug.url_hash}/paper" in iframe["src"]


@pytest.mark.asyncio
async def test_dashboard_scroll_card_uses_canonical_url(
    authenticated_client, test_db, test_user, test_subject
):
    """Dashboard scroll cards should link to canonical URL when available."""
    from tests.conftest import create_content_addressable_scroll

    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Dashboard Card Test",
        authors="Author",
        abstract="Abstract for card test.",
        html_content="<h1>Card</h1>",
    )
    scroll.slug = "dashboard-card-test"
    scroll.publication_year = 2026
    test_db.add(scroll)
    await test_db.commit()

    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    card_links = soup.find_all("a", class_="scroll-card-link")
    found = False
    for link in card_links:
        if "/2026/dashboard-card-test" in link.get("href", ""):
            found = True
            break
    assert found, "Expected a scroll card link with canonical URL /2026/dashboard-card-test"
