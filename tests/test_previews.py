"""Tests for preview routes."""

from httpx import AsyncClient
from sqlalchemy import select

from app.models.preview import Preview, Subject


async def test_upload_page_requires_auth(client: AsyncClient):
    """Test GET /upload redirects unauthenticated users."""
    response = await client.get("/upload", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_upload_page_shows_form(authenticated_client: AsyncClient):
    """Test GET /upload shows upload form for authenticated users."""
    response = await authenticated_client.get("/upload")
    assert response.status_code == 200
    assert "Upload New Scroll" in response.text
    assert "Title" in response.text
    assert "HTML Content" in response.text


async def test_upload_form_publish_scroll(authenticated_client: AsyncClient, test_db, test_user):
    """Test POST /upload-form publishes scroll directly (no drafts)."""
    # Create a subject for the test
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    upload_data = {
        "title": "Test Scroll",
        "authors": "Test Author",
        "subject_id": str(subject.id),
        "abstract": "Test abstract",
        "keywords": "test, scroll",
        "html_content": "<h1>Test Content</h1>",
        "action": "publish",
    }

    response = await authenticated_client.post("/upload-form", data=upload_data)
    assert response.status_code == 200
    assert "Your scroll has been published successfully!" in response.text

    # Verify scroll was created and published in database
    result = await test_db.execute(select(Preview).where(Preview.title == "Test Scroll"))
    preview = result.scalar_one()
    assert preview.status == "published"
    assert preview.user_id == test_user.id


async def test_upload_form_publish_preview(authenticated_client: AsyncClient, test_db, test_user):
    """Test POST /upload-form publishes preview directly."""
    # Create a subject for the test
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    upload_data = {
        "title": "Published Preview",
        "authors": "Test Author",
        "subject_id": str(subject.id),
        "abstract": "Test abstract",
        "keywords": "test, preview",
        "html_content": "<h1>Published Content</h1>",
        "action": "publish",
    }

    response = await authenticated_client.post("/upload-form", data=upload_data)
    assert response.status_code == 200
    assert "Your scroll has been published successfully!" in response.text

    # Verify preview was created and published
    result = await test_db.execute(select(Preview).where(Preview.title == "Published Preview"))
    preview = result.scalar_one()
    assert preview.status == "published"
    assert preview.preview_id is not None


async def test_upload_form_validation_errors(authenticated_client: AsyncClient, test_db):
    """Test POST /upload-form validates required fields."""
    upload_data = {
        "title": "",  # Missing title
        "authors": "Test Author",
        "subject_id": "invalid-uuid",
        "abstract": "Test abstract",
        "html_content": "<h1>Test Content</h1>",
        "action": "draft",
    }

    response = await authenticated_client.post("/upload-form", data=upload_data)
    assert response.status_code == 422
    assert "Title is required" in response.text


async def test_view_published_preview(client: AsyncClient, test_db, test_user):
    """Test GET /preview/{preview_id} shows published preview."""
    # Create a subject and published preview
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = Preview(
        title="Test Published Preview",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Published Content</h1>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="published",
        preview_id="test123",
    )
    test_db.add(preview)
    await test_db.commit()

    response = await client.get("/scroll/test123")
    assert response.status_code == 200
    assert "Test Published Preview" in response.text
    assert "Test Author" in response.text
    # HTML content should be rendered directly (no iframe)
    assert "<h1>Test Published Content</h1>" in response.text


async def test_view_nonexistent_scroll_404(client: AsyncClient):
    """Test GET /scroll/{scroll_id} returns 404 for non-existent scroll."""
    response = await client.get("/scroll/nonexistent")
    assert response.status_code == 404
    assert "404" in response.text


async def test_view_unpublished_scroll_404(client: AsyncClient, test_db, test_user):
    """Test GET /scroll/{scroll_id} returns 404 for unpublished scrolls."""
    # Create a subject and unpublished scroll (hypothetical - all scrolls are now published)
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = Preview(
        title="Test Unpublished Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Unpublished Content</h1>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="draft",  # Hypothetical unpublished status
    )
    test_db.add(preview)
    await test_db.commit()

    # Try to access unpublished scroll by UUID (should fail)
    response = await client.get(f"/scroll/{preview.id}")
    assert response.status_code == 404


async def test_upload_form_requires_auth(client: AsyncClient):
    """Test POST /upload-form redirects unauthenticated users."""
    upload_data = {
        "title": "Test Preview",
        "authors": "Test Author",
        "subject_id": "test-uuid",  # Add required field
        "abstract": "Test abstract",
        "html_content": "<h1>Test Content</h1>",
        "action": "draft",
    }

    response = await client.post("/upload-form", data=upload_data, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_css_injection_for_unstyled_content(client: AsyncClient, test_db, test_user):
    """Test CSS injection when HTML content has no CSS styling."""
    # Create a subject and published scroll with no CSS
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = Preview(
        title="Unstyled Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Plain HTML Content</h1><p>This has no styling.</p>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="published",
        preview_id="unstyled123",
    )
    test_db.add(preview)
    await test_db.commit()

    response = await client.get("/scroll/unstyled123")
    assert response.status_code == 200

    # Check that CSS was injected
    assert "<style>" in response.text
    assert ".injected-scroll-content" in response.text
    assert "font-family: -apple-system" in response.text
    assert "font-family: Georgia, serif" in response.text
    assert "var(--gray-bg)" in response.text
    assert "var(--red)" in response.text

    # Check that content is wrapped in the injected container
    assert '<div class="injected-scroll-content">' in response.text
    assert "<h1>Plain HTML Content</h1><p>This has no styling.</p>" in response.text


async def test_no_css_injection_for_styled_content(client: AsyncClient, test_db, test_user):
    """Test CSS is NOT injected when HTML content already has CSS."""
    # Create a subject and published scroll with existing CSS
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    styled_content = """
    <style>
        body { background: red; }
        h1 { color: blue; }
    </style>
    <h1>Styled Content</h1>
    <p>This already has CSS.</p>
    """

    preview = Preview(
        title="Styled Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content=styled_content,
        user_id=test_user.id,
        subject_id=subject.id,
        status="published",
        preview_id="styled123",
    )
    test_db.add(preview)
    await test_db.commit()

    response = await client.get("/scroll/styled123")
    assert response.status_code == 200

    # Check that the original CSS is preserved
    assert "background: red;" in response.text
    assert "color: blue;" in response.text

    # Check that our CSS injection styles are NOT present
    assert ".injected-scroll-content" not in response.text
    assert "font-family: -apple-system" not in response.text
    assert '<div class="injected-scroll-content">' not in response.text

    # Original content should be rendered as-is
    assert "<h1>Styled Content</h1>" in response.text
    assert "<p>This already has CSS.</p>" in response.text


async def test_css_detection_with_link_tags(client: AsyncClient, test_db, test_user):
    """Test CSS detection works with <link> stylesheet tags."""
    # Create a subject and published scroll with link tag CSS
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    content_with_link = """
    <link rel="stylesheet" href="styles.css">
    <h1>Content with Link Tag</h1>
    <p>This has CSS via link tag.</p>
    """

    preview = Preview(
        title="Link CSS Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content=content_with_link,
        user_id=test_user.id,
        subject_id=subject.id,
        status="published",
        preview_id="link123",
    )
    test_db.add(preview)
    await test_db.commit()

    response = await client.get("/scroll/link123")
    assert response.status_code == 200

    # Check that the original link tag is preserved
    assert 'rel="stylesheet"' in response.text
    assert 'href="styles.css"' in response.text

    # Check that our CSS injection styles are NOT present
    assert ".injected-scroll-content" not in response.text
    assert "font-family: -apple-system" not in response.text
    assert '<div class="injected-scroll-content">' not in response.text


async def test_css_detection_with_inline_styles(client: AsyncClient, test_db, test_user):
    """Test CSS detection works with inline style attributes."""
    # Create a subject and published scroll with inline styles
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    content_with_inline = """
    <h1 style="color: green; font-size: 24px;">Content with Inline Styles</h1>
    <p>This has CSS via inline styles.</p>
    """

    preview = Preview(
        title="Inline CSS Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content=content_with_inline,
        user_id=test_user.id,
        subject_id=subject.id,
        status="published",
        preview_id="inline123",
    )
    test_db.add(preview)
    await test_db.commit()

    response = await client.get("/scroll/inline123")
    assert response.status_code == 200

    # Check that the original inline styles are preserved
    assert 'style="color: green; font-size: 24px;"' in response.text

    # Check that our CSS injection styles are NOT present
    assert ".injected-scroll-content" not in response.text
    assert "font-family: -apple-system" not in response.text
    assert '<div class="injected-scroll-content">' not in response.text
