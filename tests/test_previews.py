"""Tests for preview routes."""

from httpx import AsyncClient
from sqlalchemy import select

from app.models.scroll import Scroll, Subject
from tests.conftest import create_content_addressable_scroll


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
    assert "HTML File" in response.text


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
        "license": "cc-by-4.0",
        "confirm_rights": "true",
        "action": "publish",
    }

    response = await authenticated_client.post("/upload-form", data=upload_data)
    assert response.status_code == 200
    assert "Your scroll has been published successfully!" in response.text

    # Verify scroll was created and published in database
    result = await test_db.execute(select(Scroll).where(Scroll.title == "Test Scroll"))
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
        "title": "Published Scroll",
        "authors": "Test Author",
        "subject_id": str(subject.id),
        "abstract": "Test abstract",
        "keywords": "test, preview",
        "html_content": "<h1>Published Content</h1>",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
        "action": "publish",
    }

    response = await authenticated_client.post("/upload-form", data=upload_data)
    assert response.status_code == 200
    assert "Your scroll has been published successfully!" in response.text

    # Verify preview was created and published
    result = await test_db.execute(select(Scroll).where(Scroll.title == "Published Scroll"))
    preview = result.scalar_one()
    assert preview.status == "published"
    assert preview.url_hash is not None


async def test_upload_form_validation_errors(authenticated_client: AsyncClient, test_db):
    """Test POST /upload-form validates required fields."""
    upload_data = {
        "title": "",  # Missing title
        "authors": "Test Author",
        "subject_id": "invalid-uuid",
        "abstract": "Test abstract",
        "html_content": "<h1>Test Content</h1>",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
        "action": "draft",
    }

    response = await authenticated_client.post("/upload-form", data=upload_data)
    assert response.status_code == 422
    assert "Title is required" in response.text


async def test_upload_form_missing_checkbox(authenticated_client: AsyncClient, test_db):
    """Test POST /upload-form validates checkbox is required."""
    # Create a subject for the test
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    upload_data = {
        "title": "Test Title",
        "authors": "Test Author",
        "subject_id": str(subject.id),
        "abstract": "Test abstract",
        "html_content": "<h1>Test Content</h1>",
        "license": "cc-by-4.0",
        # Missing confirm_rights checkbox
        "action": "publish",
    }

    response = await authenticated_client.post("/upload-form", data=upload_data)
    assert response.status_code == 422
    assert "You must confirm that you have the right to publish this content" in response.text


async def test_view_published_preview(client: AsyncClient, test_db, test_user):
    """Test GET /preview/{preview_id} shows published preview."""
    # Create a subject and published preview
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Test Published Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Published Content</h1>",
        license="cc-by-4.0",
    )
    preview.publish()
    await test_db.commit()

    response = await client.get(f"/scroll/{preview.url_hash}")
    assert response.status_code == 200
    assert "Test Published Scroll" in response.text
    assert "Test Author" in response.text
    # HTML content should be available in the JSON data section for dynamic loading
    # The content gets CSS-injected and JSON-encoded, so we check for the text content
    assert "Test Published Content" in response.text
    # Verify dynamic loading infrastructure is present
    assert "user-content-data" in response.text
    assert "user-content-container" in response.text
    # Verify CSS injection happened (content should be wrapped)
    assert '\\u003cdiv class=\\"injected-scroll-content\\"\\u003e' in response.text


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

    preview = Scroll(
        title="Test Unpublished Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Unpublished Content</h1>",
        license="cc-by-4.0",
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
        "title": "Test Scroll",
        "authors": "Test Author",
        "subject_id": "test-uuid",  # Add required field
        "abstract": "Test abstract",
        "html_content": "<h1>Test Content</h1>",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
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

    preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Unstyled Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Plain HTML Content</h1><p>This has no styling.</p>",
        license="cc-by-4.0",
    )
    preview.publish()
    await test_db.commit()

    response = await client.get(f"/scroll/{preview.url_hash}")
    assert response.status_code == 200

    # Check that CSS was injected
    assert "<style>" in response.text
    assert ".injected-scroll-content" in response.text
    assert "font-family: -apple-system" in response.text
    assert "font-family: Georgia, serif" in response.text
    assert "var(--gray-bg)" in response.text
    assert "var(--red)" in response.text

    # Check that content is wrapped in the injected container (JSON-encoded)
    assert '\\u003cdiv class=\\"injected-scroll-content\\"\\u003e' in response.text
    assert "Plain HTML Content" in response.text
    # Verify dynamic loading infrastructure is present
    assert "user-content-data" in response.text


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

    preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Styled Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content=styled_content,
        license="cc-by-4.0",
    )
    preview.publish()
    await test_db.commit()

    response = await client.get(f"/scroll/{preview.url_hash}")
    assert response.status_code == 200

    # Check that the original CSS is preserved
    assert "background: red;" in response.text
    assert "color: blue;" in response.text

    # Check that our CSS injection styles are NOT present
    assert ".injected-scroll-content" not in response.text
    assert "font-family: -apple-system" not in response.text
    assert '\\u003cdiv class=\\"injected-scroll-content\\"\\u003e' not in response.text

    # Original content should be in JSON data
    assert "Styled Content" in response.text
    assert "This already has CSS" in response.text
    # Verify dynamic loading infrastructure is present
    assert "user-content-data" in response.text


async def test_upload_form_with_file_content_integration(
    authenticated_client: AsyncClient, test_db, test_user
):
    """Test complete file upload integration from form to database."""
    # Create a subject for the test
    subject = Subject(name="File Upload Subject", description="Test subject for file uploads")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    # Simulate content that would come from a file upload (safe HTML without scripts)
    file_html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Uploaded Research Document</title>
    <style>
        body { 
            font-family: 'Times New Roman', serif; 
            max-width: 900px; 
            margin: 0 auto; 
            padding: 2rem;
            line-height: 1.6;
        }
        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; }
        .abstract { background: #ecf0f1; padding: 1.5rem; margin: 2rem 0; }
        .figure { text-align: center; margin: 2rem 0; }
        code { background: #f8f9fa; padding: 0.2rem 0.4rem; }
    </style>
</head>
<body>
    <h1>Advanced Machine Learning Techniques for Research Data Analysis</h1>
    
    <div class="abstract">
        <strong>Abstract:</strong> This paper presents novel approaches to analyzing 
        research data using advanced machine learning algorithms. We demonstrate 
        improved accuracy and efficiency through innovative preprocessing techniques.
    </div>
    
    <h2>Introduction</h2>
    <p>Modern research generates vast amounts of data requiring sophisticated 
    analysis methods. Traditional statistical approaches often fall short when 
    dealing with high-dimensional datasets.</p>
    
    <h2>Methodology</h2>
    <p>Our approach combines several techniques:</p>
    <ul>
        <li>Deep neural networks for feature extraction</li>
        <li>Ensemble methods for robust predictions</li>
        <li>Cross-validation for model selection</li>
    </ul>
    
    <div class="figure">
        <p><strong>Figure 1:</strong> Model Performance Comparison</p>
        <p><code>accuracy = train_model(data, params)</code></p>
    </div>
    
    <h2>Results</h2>
    <p>Our experiments show significant improvements over baseline methods, 
    with accuracy increases of up to 15% on benchmark datasets.</p>
    
    <h2>Conclusion</h2>
    <p>The proposed methodology offers a practical solution for researchers 
    dealing with complex data analysis challenges.</p>
</body>
</html>"""

    upload_data = {
        "title": "Advanced ML Techniques for Research Data",
        "authors": "Dr. Jane Smith, Prof. John Doe",
        "subject_id": str(subject.id),
        "abstract": "Novel approaches to research data analysis using ML algorithms with improved accuracy and efficiency.",
        "keywords": "machine learning, data analysis, research, neural networks, ensemble methods",
        "html_content": file_html_content,  # Content from file upload
        "license": "cc-by-4.0",
        "confirm_rights": "true",
        "action": "publish",
    }

    response = await authenticated_client.post("/upload-form", data=upload_data)
    assert response.status_code == 200
    assert "Your scroll has been published successfully!" in response.text

    # Verify the scroll was created with file content
    result = await test_db.execute(
        select(Scroll).where(Scroll.title == "Advanced ML Techniques for Research Data")
    )
    scroll = result.scalar_one()
    assert scroll.status == "published"
    assert scroll.user_id == test_user.id
    assert scroll.url_hash is not None
    assert scroll.content_hash is not None

    # Verify the HTML content was preserved (JavaScript was removed for security)
    assert "Advanced Machine Learning Techniques" in scroll.html_content
    assert "font-family: 'Times New Roman'" in scroll.html_content
    assert "<h2>Introduction</h2>" in scroll.html_content
    assert "<h2>Methodology</h2>" in scroll.html_content
    assert "<h2>Results</h2>" in scroll.html_content
    assert "<h2>Conclusion</h2>" in scroll.html_content


async def test_upload_form_file_validation_server_side(authenticated_client: AsyncClient, test_db):
    """Test server-side validation of file upload content."""
    # Create a subject for the test
    subject = Subject(name="Validation Subject", description="Test validation")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    # Test with content that would fail validation (whitespace only)
    invalid_upload_data = {
        "title": "Invalid Content Test",
        "authors": "Test Author",
        "subject_id": str(subject.id),
        "abstract": "Testing server-side validation",
        "keywords": "validation, test",
        "html_content": "   \n\t  \n   ",  # Only whitespace
        "license": "cc-by-4.0",
        "confirm_rights": "true",
        "action": "publish",
    }

    response = await authenticated_client.post("/upload-form", data=invalid_upload_data)
    assert response.status_code == 422
    assert "HTML content is required" in response.text

    # Test with valid minimal content
    valid_upload_data = {
        "title": "Valid Minimal Content Test",
        "authors": "Test Author",
        "subject_id": str(subject.id),
        "abstract": "Testing valid minimal content",
        "keywords": "minimal, valid",
        "html_content": "<html><body><h1>Valid</h1></body></html>",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
        "action": "publish",
    }

    response = await authenticated_client.post("/upload-form", data=valid_upload_data)
    assert response.status_code == 200
    assert "Your scroll has been published successfully!" in response.text


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

    preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Link CSS Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content=content_with_link,
        license="cc-by-4.0",
    )
    preview.publish()
    await test_db.commit()

    response = await client.get(f"/scroll/{preview.url_hash}")
    assert response.status_code == 200

    # Check that the original link tag is preserved (in JSON data)
    assert 'rel="stylesheet"' in response.text or 'rel=\\"stylesheet\\"' in response.text
    assert 'href="styles.css"' in response.text or 'href=\\"styles.css\\"' in response.text

    # Check that our CSS injection styles are NOT present
    assert ".injected-scroll-content" not in response.text
    assert "font-family: -apple-system" not in response.text
    assert '\\u003cdiv class=\\"injected-scroll-content\\"\\u003e' not in response.text
    # Verify dynamic loading infrastructure is present
    assert "user-content-data" in response.text


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

    preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Inline CSS Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content=content_with_inline,
        license="cc-by-4.0",
    )
    preview.publish()
    await test_db.commit()

    response = await client.get(f"/scroll/{preview.url_hash}")
    assert response.status_code == 200

    # Check that the original inline styles are preserved (in JSON data)
    assert (
        'style="color: green; font-size: 24px;"' in response.text
        or 'style=\\"color: green; font-size: 24px;\\"' in response.text
    )

    # Check that our CSS injection styles are NOT present
    assert ".injected-scroll-content" not in response.text
    assert "font-family: -apple-system" not in response.text
    assert '\\u003cdiv class=\\"injected-scroll-content\\"\\u003e' not in response.text
    # Verify dynamic loading infrastructure is present
    assert "user-content-data" in response.text
