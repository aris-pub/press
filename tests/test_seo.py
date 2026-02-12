"""Tests for SEO-related endpoints (robots.txt, sitemap.xml, meta tags)."""

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
    url_hash, content_hash, _ = await generate_permanent_url(test_db, "<html><body>Test</body></html>")
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
    url_hash, content_hash, _ = await generate_permanent_url(test_db, "<html><body>Test</body></html>")
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
