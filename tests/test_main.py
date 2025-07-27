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
        preview_id="recent123",
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
        status="draft",  # Draft status
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
        preview_id="pub123",
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
        preview_id="link123",
    )
    test_db.add(preview)
    await test_db.commit()

    response = await client.get("/")
    assert response.status_code == 200
    assert "/preview/link123" in response.text


async def test_about_page(client: AsyncClient):
    """Test about page loads correctly."""
    response = await client.get("/about")
    assert response.status_code == 200
    assert "About Press" in response.text
    assert "Research publications. Web-native. Human-first." in response.text
    assert "Preview Press is where modern research lives" in response.text


async def test_contact_page(client: AsyncClient):
    """Test contact page loads correctly."""
    response = await client.get("/contact")
    assert response.status_code == 200
    assert "Get in Touch" in response.text
    assert "Community" in response.text
    assert "Development" in response.text
    assert "Zulip" in response.text
    assert "GitHub" in response.text


async def test_homepage_has_filtering_elements(client: AsyncClient):
    """Test homepage contains filtering UI elements."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "Browse by Subject" in response.text
    assert "Show All" in response.text
    assert "show-all-btn" in response.text
    assert "recent-submissions-heading" in response.text


async def test_preview_card_subject_links(client: AsyncClient, test_db, test_user):
    """Test preview cards contain clickable subject links."""
    # Create test subject and published preview
    subject = Subject(name="Machine Learning", description="ML research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = Preview(
        title="Test ML Preview",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Content</h1>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="published",
        preview_id="ml123",
    )
    test_db.add(preview)
    await test_db.commit()

    response = await client.get("/")
    assert response.status_code == 200
    assert "preview-subject-link" in response.text
    assert 'data-subject-name="machine-learning"' in response.text
    assert 'data-subject-display="Machine Learning"' in response.text


async def test_search_no_query_redirects(client: AsyncClient):
    """Test search without query redirects to homepage."""
    response = await client.get("/search", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/"


async def test_search_empty_query_redirects(client: AsyncClient):
    """Test search with empty query redirects to homepage."""
    response = await client.get("/search?q=", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/"


async def test_search_with_results(client: AsyncClient, test_db, test_user):
    """Test search returns matching results."""
    # Create test subject and published preview
    subject = Subject(name="Computer Science", description="CS research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = Preview(
        title="Machine Learning Fundamentals",
        authors="Dr. AI Researcher",
        abstract="This paper covers the basics of machine learning algorithms.",
        html_content="<h1>Introduction to ML</h1><p>Machine learning is...</p>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="published",
        preview_id="ml123",
    )
    test_db.add(preview)
    await test_db.commit()

    # Search for matching terms
    response = await client.get("/search?q=machine+learning")
    assert response.status_code == 200
    assert "Search Results" in response.text
    # Check for highlighted terms instead of exact title
    assert "Machine" in response.text and "Learning" in response.text and "Fundamentals" in response.text
    assert "Dr. AI Researcher" in response.text
    assert "Showing" in response.text and "1" in response.text and "result" in response.text


async def test_search_no_results(client: AsyncClient):
    """Test search with no matching results."""
    response = await client.get("/search?q=nonexistent+topic")
    assert response.status_code == 200
    assert "Search Results" in response.text
    assert "No results found" in response.text
    assert "Browse All Subjects" in response.text
    assert "Recent Papers" in response.text


async def test_search_only_published_previews(client: AsyncClient, test_db, test_user):
    """Test search only returns published previews, not drafts."""
    # Create test subject
    subject = Subject(name="Physics", description="Physics research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    # Create draft preview (should not appear in search)
    draft_preview = Preview(
        title="Draft Physics Paper",
        authors="Draft Author",
        abstract="This is a draft paper about quantum mechanics.",
        html_content="<h1>Draft Content</h1>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="draft",
    )

    # Create published preview (should appear in search)
    published_preview = Preview(
        title="Published Physics Paper",
        authors="Published Author",
        abstract="This is a published paper about quantum mechanics.",
        html_content="<h1>Published Content</h1>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="published",
        preview_id="phys123",
    )

    test_db.add(draft_preview)
    test_db.add(published_preview)
    await test_db.commit()

    # Search for common term in both
    response = await client.get("/search?q=quantum+mechanics")
    assert response.status_code == 200
    
    # Should find published paper
    assert "Published Physics Paper" in response.text
    assert "Published Author" in response.text
    
    # Should not find draft paper
    assert "Draft Physics Paper" not in response.text
    assert "Draft Author" not in response.text


async def test_search_term_highlighting(client: AsyncClient, test_db, test_user):
    """Test that search terms are highlighted in results."""
    # Create test subject and published preview
    subject = Subject(name="Biology", description="Bio research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = Preview(
        title="Neural Networks in Biology",
        authors="Bio Researcher",
        abstract="Study of neural networks and their biological applications.",
        html_content="<h1>Neural Networks</h1>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="published",
        preview_id="bio123",
    )
    test_db.add(preview)
    await test_db.commit()

    # Search for term that should be highlighted
    response = await client.get("/search?q=neural")
    assert response.status_code == 200
    assert "<mark>Neural</mark>" in response.text or "<mark>neural</mark>" in response.text
    assert "Showing" in response.text and "1" in response.text and "result" in response.text


async def test_search_partial_matching(client: AsyncClient, test_db, test_user):
    """Test that search works with partial word matches."""
    # Create test subject and published preview with "algorithm" in title
    subject = Subject(name="Computer Science", description="CS research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = Preview(
        title="Advanced Algorithms in Machine Learning",
        authors="Dr. Algorithm Expert",
        abstract="This paper discusses algorithmic approaches to ML.",
        html_content="<h1>Algorithms</h1><p>Various algorithmic methods...</p>",
        user_id=test_user.id,
        subject_id=subject.id,
        status="published",
        preview_id="algo123",
    )
    test_db.add(preview)
    await test_db.commit()

    # Test partial match: "algo" should find "algorithm", "algorithms", "algorithmic"
    response = await client.get("/search?q=algo")
    assert response.status_code == 200
    # Check for highlighted partial matches (title will be highlighted)
    assert "Advanced" in response.text and "rithms" in response.text and "Machine Learning" in response.text
    assert "Dr. Algorithm Expert" in response.text
    assert "Showing" in response.text and "1" in response.text and "result" in response.text
    # Verify highlighting is working for partial matches
    assert "<mark>Algo</mark>" in response.text or "<mark>algo</mark>" in response.text


async def test_search_form_on_homepage(client: AsyncClient):
    """Test that homepage search form submits to /search."""
    response = await client.get("/")
    assert response.status_code == 200
    assert 'action="/search"' in response.text
    assert 'method="get"' in response.text
    assert 'name="q"' in response.text


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
