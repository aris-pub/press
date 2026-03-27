"""Tests for SEO-related endpoints (robots.txt, sitemap.xml, meta tags)."""

import uuid

import pytest

from app.models.scroll import Scroll


@pytest.mark.asyncio
async def test_robots_txt(client):
    """Test robots.txt is served correctly."""
    response = await client.get("/robots.txt")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert "User-agent: *" in response.text
    assert "Allow: /" in response.text
    assert "Disallow: /api/" in response.text
    assert "Disallow: /dashboard" in response.text
    assert "Disallow: /scroll/*/paper" in response.text
    assert "Sitemap: https://scroll.press/sitemap.xml" in response.text


@pytest.mark.asyncio
async def test_sitemap_xml(client, test_db, test_user, test_subject):
    """Test sitemap.xml is generated correctly."""
    from app.storage.content_processing import generate_permanent_url

    # Create a published scroll for testing
    url_hash, content_hash, _ = await generate_permanent_url(
        test_db, "<html><body>Test</body></html>"
    )
    scroll = Scroll(
        user_id=test_user.id,
        subject_id=test_subject.id,
        title="Test Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<html><body>Test</body></html>",
        license="cc-by-4.0",
        status="published",
        url_hash=url_hash,
        content_hash=content_hash,
    )
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)

    response = await client.get("/sitemap.xml")

    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert '<?xml version="1.0" encoding="UTF-8"?>' in response.text
    assert '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' in response.text

    # Check static pages are included
    assert "<loc>https://scroll.press/</loc>" in response.text
    assert "<loc>https://scroll.press/about</loc>" in response.text
    assert "<loc>https://scroll.press/terms</loc>" in response.text

    # Check published scroll is included
    assert f"<loc>https://scroll.press/scroll/{scroll.url_hash}</loc>" in response.text


@pytest.mark.asyncio
async def test_base_template_has_seo_meta_tags(client):
    """Test that base template includes SEO meta tags."""
    response = await client.get("/")

    assert response.status_code == 200
    html = response.text

    # Check SEO meta tags
    assert '<meta name="description"' in html
    assert '<meta property="og:title"' in html
    assert '<meta property="og:description"' in html
    assert '<meta property="og:url"' in html
    assert '<meta property="og:site_name" content="Scroll Press">' in html
    assert '<meta name="twitter:card" content="summary">' in html


@pytest.mark.asyncio
async def test_scroll_page_has_article_meta_tags(client, test_db, test_user, test_subject):
    """Test that scroll pages have article-specific meta tags."""
    from app.storage.content_processing import generate_permanent_url

    # Create a published scroll for testing
    url_hash, content_hash, _ = await generate_permanent_url(
        test_db, "<html><body>Test</body></html>"
    )
    scroll = Scroll(
        user_id=test_user.id,
        subject_id=test_subject.id,
        title="Test Scroll",
        authors="Test Author",
        abstract="Test abstract for SEO",
        html_content="<html><body>Test</body></html>",
        license="cc-by-4.0",
        status="published",
        url_hash=url_hash,
        content_hash=content_hash,
    )
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)

    response = await client.get(f"/scroll/{scroll.url_hash}")

    assert response.status_code == 200
    html = response.text

    # Check article meta tags
    assert '<meta name="description"' in html
    assert '<meta property="og:type" content="article">' in html
    assert (
        f'<meta property="og:url" content="https://scroll.press/scroll/{scroll.url_hash}">' in html
    )
    assert f'<meta property="article:author" content="{scroll.authors}">' in html


@pytest.mark.asyncio
async def test_sitemap_uses_canonical_urls_for_versioned_scrolls(
    client, test_db, test_user, test_subject
):
    """Sitemap should list canonical /{year}/{slug} URLs, not version-specific ones."""
    from app.storage.content_processing import generate_permanent_url

    series_id = uuid.uuid4()

    url_hash_v1, content_hash_v1, _ = await generate_permanent_url(
        test_db, "<html><body>Sitemap V1</body></html>"
    )
    v1 = Scroll(
        user_id=test_user.id,
        subject_id=test_subject.id,
        title="Sitemap Test",
        authors="Author",
        abstract="Abstract",
        html_content="<html><body>Sitemap V1</body></html>",
        license="cc-by-4.0",
        status="published",
        url_hash=url_hash_v1,
        content_hash=content_hash_v1,
        version=1,
        scroll_series_id=series_id,
        publication_year=2026,
        slug="sitemap-test",
    )
    v1.publish()
    test_db.add(v1)

    url_hash_v2, content_hash_v2, _ = await generate_permanent_url(
        test_db, "<html><body>Sitemap V2</body></html>"
    )
    v2 = Scroll(
        user_id=test_user.id,
        subject_id=test_subject.id,
        title="Sitemap Test",
        authors="Author",
        abstract="Abstract",
        html_content="<html><body>Sitemap V2</body></html>",
        license="cc-by-4.0",
        status="published",
        url_hash=url_hash_v2,
        content_hash=content_hash_v2,
        version=2,
        scroll_series_id=series_id,
        publication_year=2026,
        slug="sitemap-test",
    )
    v2.publish()
    test_db.add(v2)

    await test_db.commit()

    response = await client.get("/sitemap.xml")
    assert response.status_code == 200

    # Should have canonical URL (no /v1, /v2)
    assert "<loc>https://scroll.press/2026/sitemap-test</loc>" in response.text

    # Should NOT have version-specific URLs
    assert "/v1</loc>" not in response.text
    assert "/v2</loc>" not in response.text

    # Should only appear once (deduplicated across versions)
    assert response.text.count("sitemap-test</loc>") == 1


@pytest.mark.asyncio
async def test_sitemap_falls_back_to_hash_url_without_year_slug(
    client, test_db, test_user, test_subject
):
    """Scrolls without year/slug should still use /scroll/{hash} in sitemap."""
    from app.storage.content_processing import generate_permanent_url

    url_hash, content_hash, _ = await generate_permanent_url(
        test_db, "<html><body>No slug scroll</body></html>"
    )
    scroll = Scroll(
        user_id=test_user.id,
        subject_id=test_subject.id,
        title="No Slug Scroll",
        authors="Author",
        abstract="Abstract",
        html_content="<html><body>No slug scroll</body></html>",
        license="cc-by-4.0",
        status="published",
        url_hash=url_hash,
        content_hash=content_hash,
    )
    scroll.publish()
    test_db.add(scroll)
    await test_db.commit()

    response = await client.get("/sitemap.xml")
    assert response.status_code == 200
    assert f"<loc>https://scroll.press/scroll/{url_hash}</loc>" in response.text
