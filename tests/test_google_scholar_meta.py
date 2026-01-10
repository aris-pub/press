"""Tests for Google Scholar meta tag implementation."""

import pytest
import pytest_asyncio
from bs4 import BeautifulSoup


@pytest_asyncio.fixture
async def test_scroll(test_db, test_user, test_subject):
    """Create a published test scroll for Google Scholar meta tag tests."""
    from tests.conftest import create_content_addressable_scroll

    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Test Research Paper",
        authors="Dr. Jane Smith, Prof. John Doe",
        abstract="This is a test abstract for Google Scholar meta tags.",
        keywords=["test", "research", "meta tags"],
        html_content="<h1>Test Research</h1><p>Content here</p>",
    )

    # Publish the scroll
    scroll.publish()
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)

    return scroll


@pytest.mark.asyncio
async def test_scroll_has_google_scholar_meta_tags(client, test_scroll):
    """Verify that published scroll pages include Google Scholar meta tags."""
    response = await client.get(f"/scroll/{test_scroll.url_hash}")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")

    # Check required minimum fields
    assert soup.find("meta", {"name": "citation_title"})
    assert soup.find("meta", {"name": "citation_author"})
    assert soup.find("meta", {"name": "citation_publication_date"})

    # Check optional but recommended fields
    assert soup.find("meta", {"name": "citation_journal_title"})
    assert soup.find("meta", {"name": "citation_abstract"})
    assert soup.find("meta", {"name": "citation_fulltext_html_url"})


@pytest.mark.asyncio
async def test_citation_title_matches_scroll_title(client, test_scroll):
    """Verify citation_title matches the actual scroll title."""
    response = await client.get(f"/scroll/{test_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    citation_title = soup.find("meta", {"name": "citation_title"})
    assert citation_title["content"] == test_scroll.title


@pytest.mark.asyncio
async def test_multiple_authors_have_separate_tags(client, test_scroll):
    """Verify each author gets a separate citation_author tag."""
    authors = test_scroll.authors.split(",")

    response = await client.get(f"/scroll/{test_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    author_tags = soup.find_all("meta", {"name": "citation_author"})
    assert len(author_tags) == len(authors)

    for author_tag, expected_author in zip(author_tags, authors):
        assert author_tag["content"] == expected_author.strip()


@pytest.mark.asyncio
async def test_citation_date_format(client, test_scroll):
    """Verify citation_publication_date uses correct YYYY/MM/DD format."""
    response = await client.get(f"/scroll/{test_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    date_tag = soup.find("meta", {"name": "citation_publication_date"})
    date_value = date_tag["content"]

    # Check format matches YYYY/MM/DD
    import re

    assert re.match(r"^\d{4}/\d{2}/\d{2}$", date_value)


@pytest.mark.asyncio
async def test_keywords_have_separate_tags(client, test_scroll):
    """Verify each keyword gets a separate citation_keywords tag."""
    if not test_scroll.keywords:
        pytest.skip("Sample scroll has no keywords")

    response = await client.get(f"/scroll/{test_scroll.url_hash}")
    soup = BeautifulSoup(response.text, "html.parser")

    keyword_tags = soup.find_all("meta", {"name": "citation_keywords"})
    assert len(keyword_tags) == len(test_scroll.keywords)


# CRITICAL XSS SECURITY TESTS
@pytest.mark.asyncio
async def test_xss_prevention_in_title(client, test_db, test_user, test_subject):
    """Verify title with XSS payload is properly escaped."""
    from app.models.scroll import Scroll

    malicious_scroll = Scroll(
        user_id=test_user.id,
        title='<script>alert("XSS")</script>Malicious Title',
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract",
        keywords=["test"],
        html_content="<p>Content</p>",
        license="cc-by-4.0",
        content_hash="xss123",
        url_hash="xss789",
        status="published",
    )
    malicious_scroll.publish()
    test_db.add(malicious_scroll)
    await test_db.commit()
    await test_db.refresh(malicious_scroll)

    response = await client.get(f"/scroll/{malicious_scroll.url_hash}")
    assert response.status_code == 200

    # Check raw HTML has escaped entities (not parsed by BeautifulSoup)
    assert "&lt;script&gt;" in response.text
    # The script tag should NOT appear unescaped in the raw HTML
    assert 'content="<script>alert' not in response.text


@pytest.mark.asyncio
async def test_xss_prevention_in_authors(client, test_db, test_user, test_subject):
    """Verify authors with XSS payload is properly escaped."""
    from app.models.scroll import Scroll

    malicious_scroll = Scroll(
        user_id=test_user.id,
        title="Test Title",
        authors='<img src=x onerror="alert(1)">Evil Author',
        subject_id=test_subject.id,
        abstract="Test abstract",
        keywords=["test"],
        html_content="<p>Content</p>",
        license="cc-by-4.0",
        content_hash="xss456",
        url_hash="xss012",
        status="published",
    )
    malicious_scroll.publish()
    test_db.add(malicious_scroll)
    await test_db.commit()
    await test_db.refresh(malicious_scroll)

    response = await client.get(f"/scroll/{malicious_scroll.url_hash}")
    assert response.status_code == 200

    # Check raw HTML has escaped entities
    assert "&lt;img" in response.text
    # The img tag with onerror should NOT appear unescaped
    assert 'content="<img src=x onerror=' not in response.text


@pytest.mark.asyncio
async def test_xss_prevention_in_abstract(client, test_db, test_user, test_subject):
    """Verify abstract with XSS payload is properly escaped."""
    from app.models.scroll import Scroll

    malicious_scroll = Scroll(
        user_id=test_user.id,
        title="Test Title",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract='"><script>alert("XSS in abstract")</script><meta name="',
        keywords=["test"],
        html_content="<p>Content</p>",
        license="cc-by-4.0",
        content_hash="xss789",
        url_hash="xss345",
        status="published",
    )
    malicious_scroll.publish()
    test_db.add(malicious_scroll)
    await test_db.commit()
    await test_db.refresh(malicious_scroll)

    response = await client.get(f"/scroll/{malicious_scroll.url_hash}")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    abstract_tag = soup.find("meta", {"name": "citation_abstract"})
    # Should not allow breaking out of attribute
    assert '"><script>' not in str(abstract_tag)


# EDGE CASE TESTS
@pytest.mark.asyncio
async def test_draft_scroll_no_google_scholar_tags(
    client, test_db, test_user, test_subject
):
    """Verify draft scrolls do NOT include Google Scholar meta tags."""
    from app.models.scroll import Scroll

    draft_scroll = Scroll(
        user_id=test_user.id,
        title="Draft Scroll",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Draft abstract",
        keywords=["test"],
        html_content="<p>Content</p>",
        license="cc-by-4.0",
        content_hash="draft123",
        url_hash="draft789",
        status="draft",  # NOT published
    )
    test_db.add(draft_scroll)
    await test_db.commit()
    await test_db.refresh(draft_scroll)

    # Draft scrolls might not be accessible, but if they are, they should not have meta tags
    response = await client.get(f"/scroll/{draft_scroll.url_hash}")

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        # Should NOT have Google Scholar tags
        assert soup.find("meta", {"name": "citation_title"}) is None


# Note: test_none_authors_handled_gracefully removed because the database schema
# has NOT NULL constraint on authors field, so None is not a valid test case


@pytest.mark.asyncio
async def test_empty_string_authors_handled_gracefully(
    client, test_db, test_user, test_subject
):
    """Verify scrolls with empty string authors don't crash."""
    from app.models.scroll import Scroll

    scroll = Scroll(
        user_id=test_user.id,
        title="Empty Authors",
        authors="",  # Empty string
        subject_id=test_subject.id,
        abstract="Test abstract",
        keywords=["test"],
        html_content="<p>Content</p>",
        license="cc-by-4.0",
        content_hash="empty123",
        url_hash="empty789",
        status="published",
    )
    scroll.publish()
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)

    response = await client.get(f"/scroll/{scroll.url_hash}")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    author_tags = soup.find_all("meta", {"name": "citation_author"})
    assert len(author_tags) == 0  # No author tags if empty


@pytest.mark.asyncio
async def test_empty_keywords_array_handled_gracefully(
    client, test_db, test_user, test_subject
):
    """Verify scrolls with empty keywords array don't crash."""
    from app.models.scroll import Scroll

    scroll = Scroll(
        user_id=test_user.id,
        title="Empty Keywords",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract",
        keywords=[],  # Empty array
        html_content="<p>Content</p>",
        license="cc-by-4.0",
        content_hash="emptykw123",
        url_hash="emptykw789",
        status="published",
    )
    scroll.publish()
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)

    response = await client.get(f"/scroll/{scroll.url_hash}")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    keyword_tags = soup.find_all("meta", {"name": "citation_keywords"})
    assert len(keyword_tags) == 0  # No keyword tags if empty
