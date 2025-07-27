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
    assert "Upload Your Research Preview" in response.text
    assert "Title" in response.text
    assert "HTML Content" in response.text


async def test_upload_form_create_draft(authenticated_client: AsyncClient, test_db, test_user):
    """Test POST /upload-form creates draft preview."""
    # Create a subject for the test
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    upload_data = {
        "title": "Test Preview",
        "authors": "Test Author",
        "subject_id": str(subject.id),
        "abstract": "Test abstract",
        "keywords": "test, preview",
        "html_content": "<h1>Test Content</h1>",
        "action": "draft",
    }

    response = await authenticated_client.post("/upload-form", data=upload_data)
    assert response.status_code == 200
    assert "Draft 'Test Preview' has been saved successfully!" in response.text

    # Verify preview was created in database
    result = await test_db.execute(select(Preview).where(Preview.title == "Test Preview"))
    preview = result.scalar_one()
    assert preview.status == "draft"
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
    assert "Your preview has been published successfully!" in response.text

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

    response = await client.get("/preview/test123")
    assert response.status_code == 200
    assert "Test Published Preview" in response.text
    assert "Test Author" in response.text
    assert "<h1>Test Published Content</h1>" in response.text


async def test_view_nonexistent_preview_404(client: AsyncClient):
    """Test GET /preview/{preview_id} returns 404 for non-existent preview."""
    response = await client.get("/preview/nonexistent")
    assert response.status_code == 404
    assert "404" in response.text


async def test_view_draft_preview_404(client: AsyncClient, test_db, test_user):
    """Test GET /preview/{preview_id} returns 404 for draft previews."""
    # Create a subject and draft preview
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = Preview(
        title="Test Draft Preview",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Draft Content</h1>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="draft",  # Draft status
    )
    test_db.add(preview)
    await test_db.commit()

    # Try to access draft preview by UUID (should fail)
    response = await client.get(f"/preview/{preview.id}")
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
