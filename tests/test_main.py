"""Tests for main routes."""

from httpx import AsyncClient

from app.models.preview import Preview, Subject


async def test_homepage_anonymous_user(client: AsyncClient):
    """Test GET / for anonymous users."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "Preview Press" in response.text
    assert "Open access to research preprints" in response.text


async def test_homepage_authenticated_user(authenticated_client: AsyncClient):
    """Test GET / for authenticated users."""
    response = await authenticated_client.get("/")
    assert response.status_code == 200
    assert "Preview Press" in response.text


async def test_homepage_shows_subjects(client: AsyncClient, test_db):
    """Test homepage displays subjects with counts."""
    # Create test subjects
    subject1 = Subject(name="Computer Science", description="CS research")
    subject2 = Subject(name="Physics", description="Physics research")
    test_db.add(subject1)
    test_db.add(subject2)
    await test_db.commit()
    
    response = await client.get("/")
    assert response.status_code == 200
    assert "Browse by Subject" in response.text
    assert "Computer Science" in response.text
    assert "Physics" in response.text


async def test_homepage_shows_recent_previews(client: AsyncClient, test_db, test_user):
    """Test homepage displays recent published previews."""
    # Create test subject and published preview
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)
    
    preview = Preview(
        title="Recent Test Preview",
        authors="Test Author",
        abstract="Test abstract for recent preview",
        html_content="<h1>Test Content</h1>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="published",
        preview_id="recent123"
    )
    test_db.add(preview)
    await test_db.commit()
    
    response = await client.get("/")
    assert response.status_code == 200
    assert "Recent Submissions" in response.text
    assert "Recent Test Preview" in response.text
    assert "Test Author" in response.text
    assert "Test abstract for recent preview" in response.text


async def test_homepage_only_shows_published_previews(client: AsyncClient, test_db, test_user):
    """Test homepage only shows published previews, not drafts."""
    # Create test subject
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)
    
    # Create draft preview (should not appear)
    draft_preview = Preview(
        title="Draft Preview",
        authors="Draft Author",
        abstract="Draft abstract",
        html_content="<h1>Draft Content</h1>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="draft"  # Draft status
    )
    
    # Create published preview (should appear)
    published_preview = Preview(
        title="Published Preview",
        authors="Published Author",
        abstract="Published abstract",
        html_content="<h1>Published Content</h1>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="published",
        preview_id="pub123"
    )
    
    test_db.add(draft_preview)
    test_db.add(published_preview)
    await test_db.commit()
    
    response = await client.get("/")
    assert response.status_code == 200
    
    # Should show published preview
    assert "Published Preview" in response.text
    assert "Published Author" in response.text
    
    # Should not show draft preview
    assert "Draft Preview" not in response.text
    assert "Draft Author" not in response.text


async def test_homepage_preview_links(client: AsyncClient, test_db, test_user):
    """Test that preview cards link to individual preview pages."""
    # Create test subject and published preview
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)
    
    preview = Preview(
        title="Linkable Preview",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Content</h1>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="published",
        preview_id="link123"
    )
    test_db.add(preview)
    await test_db.commit()
    
    response = await client.get("/")
    assert response.status_code == 200
    assert "/preview/link123" in response.text


async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "response_time_ms" in data
    assert data["components"]["database"] == "healthy"
    assert data["components"]["models"] == "healthy"
    assert "subject_count" in data["metrics"]
    assert "preview_count" in data["metrics"]
    assert data["version"] == "0.1.0"