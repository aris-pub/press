"""Tests for main routes."""

from httpx import AsyncClient

from app.models.scroll import Scroll, Subject
from tests.conftest import create_content_addressable_scroll


async def test_homepage_anonymous_user(client: AsyncClient):
    """Test GET / for anonymous users."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "Scroll Press" in response.text
    assert "A preprint server for interactive research papers" in response.text


async def test_homepage_authenticated_user(authenticated_client: AsyncClient):
    """Test GET / for authenticated users."""
    response = await authenticated_client.get("/")
    assert response.status_code == 200
    assert "Scroll Press" in response.text


async def test_homepage_shows_subjects(client: AsyncClient, test_db, test_user):
    """Test homepage displays subjects with counts."""
    # Create test subjects
    subject1 = Subject(name="Computer Science", description="CS research")
    subject2 = Subject(name="Physics", description="Physics research")
    test_db.add(subject1)
    test_db.add(subject2)
    await test_db.commit()
    await test_db.refresh(subject1)
    await test_db.refresh(subject2)

    # Create scrolls for these subjects so they appear (subjects with 0 scrolls are hidden)
    scroll1 = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject1,
        title="CS Paper",
        authors="CS Author",
        abstract="CS abstract",
        html_content="<h1>CS Content</h1>",
        license="cc-by-4.0",
    )
    scroll1.publish()

    scroll2 = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject2,
        title="Physics Paper",
        authors="Physics Author",
        abstract="Physics abstract",
        html_content="<h1>Physics Content</h1>",
        license="cc-by-4.0",
    )
    scroll2.publish()
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

    preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Recent Test Scroll",
        authors="Test Author",
        abstract="Test abstract for recent preview",
        html_content="<h1>Test Content</h1>",
        license="cc-by-4.0",
    )
    preview.publish()
    await test_db.commit()

    response = await client.get("/")
    assert response.status_code == 200
    assert "Recent Scrolls" in response.text
    assert "Recent Test Scroll" in response.text
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
    draft_preview = Scroll(
        title="Draft Scroll",
        authors="Draft Author",
        abstract="Draft abstract",
        html_content="<h1>Draft Content</h1>",
        license="cc-by-4.0",
        user_id=test_user.id,
        subject_id=subject.id,
        status="preview",  # Draft status
    )

    # Create published preview (should appear)
    published_preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Published Scroll",
        authors="Published Author",
        abstract="Published abstract",
        html_content="<h1>Published Content</h1>",
        license="cc-by-4.0",
    )
    published_preview.publish()

    test_db.add(draft_preview)
    test_db.add(published_preview)
    await test_db.commit()

    response = await client.get("/")
    assert response.status_code == 200

    # Should show published preview
    assert "Published Scroll" in response.text
    assert "Published Author" in response.text

    # Should not show draft preview
    assert "Draft Scroll" not in response.text
    assert "Draft Author" not in response.text


async def test_homepage_preview_links(client: AsyncClient, test_db, test_user):
    """Test that preview cards link to individual preview pages."""
    # Create test subject and published preview
    subject = Subject(name="Test Subject", description="Test description")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Linkable Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Content</h1>",
        license="cc-by-4.0",
    )
    preview.publish()
    await test_db.commit()
    await test_db.refresh(preview)

    response = await client.get("/")
    assert response.status_code == 200
    assert f"/scroll/{preview.url_hash}" in response.text


async def test_about_page(client: AsyncClient):
    """Test about page loads correctly."""
    response = await client.get("/about")
    assert response.status_code == 200
    assert "About Scroll Press" in response.text
    assert "Research publications. Web-native. Human-first." in response.text
    assert "Scroll Press is where modern research lives" in response.text


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


async def test_scroll_card_subject_links(client: AsyncClient, test_db, test_user):
    """Test preview cards contain clickable subject links."""
    # Create test subject and published preview
    subject = Subject(name="Machine Learning", description="ML research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Test ML Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Content</h1>",
        license="cc-by-4.0",
    )
    preview.publish()
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

    preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Machine Learning Fundamentals",
        authors="Dr. AI Researcher",
        abstract="This paper covers the basics of machine learning algorithms.",
        html_content="<h1>Introduction to ML</h1><p>Machine learning is...</p>",
        license="cc-by-4.0",
    )
    preview.publish()
    await test_db.commit()

    # Search for matching terms
    response = await client.get("/search?q=machine+learning")
    assert response.status_code == 200
    assert "Search Results" in response.text
    # Check for highlighted terms instead of exact title
    assert (
        "Machine" in response.text
        and "Learning" in response.text
        and "Fundamentals" in response.text
    )
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
    draft_preview = Scroll(
        title="Draft Physics Paper",
        authors="Draft Author",
        abstract="This is a draft paper about quantum mechanics.",
        html_content="<h1>Draft Content</h1>",
        license="cc-by-4.0",
        user_id=test_user.id,
        subject_id=subject.id,
        status="preview",
    )

    # Create published preview (should appear in search)
    published_preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Published Physics Paper",
        authors="Published Author",
        abstract="This is a published paper about quantum mechanics.",
        html_content="<h1>Published Content</h1>",
        license="cc-by-4.0",
    )
    published_preview.publish()

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

    preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Neural Networks in Biology",
        authors="Bio Researcher",
        abstract="Study of neural networks and their biological applications.",
        html_content="<h1>Neural Networks</h1>",
        license="cc-by-4.0",
    )
    preview.publish()
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

    preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Advanced Algorithms in Machine Learning",
        authors="Dr. Algorithm Expert",
        abstract="This paper discusses algorithmic approaches to ML.",
        html_content="<h1>Algorithms</h1><p>Various algorithmic methods...</p>",
        license="cc-by-4.0",
    )
    preview.publish()
    await test_db.commit()

    # Test partial match: "algo" should find "algorithm", "algorithms", "algorithmic"
    response = await client.get("/search?q=algo")
    assert response.status_code == 200
    # Check for highlighted partial matches (title will be highlighted)
    assert (
        "Advanced" in response.text
        and "rithms" in response.text
        and "Machine Learning" in response.text
    )
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
    assert data["service"] == "scroll-press"
    assert "timestamp" in data
    assert "response_time_ms" in data
    assert "metrics" in data
    assert "db_latency_ms" in data["metrics"]
    assert "scrolls_query_latency_ms" in data["metrics"]
    assert "scroll_count" in data["metrics"]


# Dashboard Tests (TDD)


async def test_dashboard_redirects_unauthenticated_users(client: AsyncClient):
    """Test 1: GET /dashboard redirects unauthenticated users to /login."""
    response = await client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_dashboard_shows_title_for_authenticated_users(authenticated_client: AsyncClient):
    """Test 2: GET /dashboard shows 'Your Scrolls' title for authenticated users."""
    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert "Your Scrolls" in response.text


async def test_dashboard_shows_users_published_papers(
    authenticated_client: AsyncClient, test_db, test_user
):
    """Test 3: Dashboard shows user's published papers using scroll_card component."""
    # Create test subject and published preview for the authenticated user
    subject = Subject(name="Computer Science", description="CS research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Efficient Algorithms for Large-Scale Graph Neural Networks",
        authors="John Smith, Li Chen, Maria Garcia",
        abstract="We present a novel approach to scaling graph neural networks",
        html_content="<h1>Test Content</h1>",
        license="cc-by-4.0",
    )
    preview.publish()
    await test_db.commit()

    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert "Efficient Algorithms for Large-Scale Graph Neural Networks" in response.text
    assert "John Smith, Li Chen, Maria Garcia" in response.text
    assert "We present a novel approach to scaling graph neural networks" in response.text
    assert "Computer Science" in response.text


async def test_dashboard_only_shows_current_users_papers(
    authenticated_client: AsyncClient, test_db, test_user
):
    """Test 4: Dashboard only shows current user's papers, not other users' papers."""
    # Create test subject
    subject = Subject(name="Physics", description="Physics research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    # Create another user
    from app.models.user import User

    other_user = User(
        email="other@example.com",
        display_name="Other User",
        password_hash="fake_hash",
        email_verified=True,
    )
    test_db.add(other_user)
    await test_db.commit()
    await test_db.refresh(other_user)

    # Create preview for current user
    user_preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Current User's Paper",
        authors="Current User",
        abstract="This is the current user's paper",
        html_content="<h1>Current User Content</h1>",
        license="cc-by-4.0",
    )
    user_preview.publish()

    # Create preview for other user
    other_preview = await create_content_addressable_scroll(
        test_db,
        other_user,
        subject,
        title="Other User's Paper",
        authors="Other User",
        abstract="This is another user's paper",
        html_content="<h1>Other User Content</h1>",
        license="cc-by-4.0",
    )
    other_preview.publish()

    test_db.add(user_preview)
    test_db.add(other_preview)
    await test_db.commit()

    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    # Should show current user's paper (check for both regular and HTML-escaped versions)
    assert "Current User's Paper" in response.text or "Current User&#39;s Paper" in response.text
    assert "Current User" in response.text  # Check for author name which appears unescaped
    # Should NOT show other user's paper
    assert (
        "Other User's Paper" not in response.text and "Other User&#39;s Paper" not in response.text
    )
    assert "Other User" not in response.text  # Check author doesn't appear


async def test_dashboard_shows_empty_state_when_no_published_papers(
    authenticated_client: AsyncClient,
):
    """Test 5: Dashboard shows empty state when user has no published papers."""
    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert "Your Scrolls" in response.text
    assert "No published papers yet" in response.text
    assert "Upload Your First Scroll" in response.text


async def test_dashboard_shows_drafts_and_published_separately(
    authenticated_client: AsyncClient, test_db, test_user
):
    """Test: Dashboard shows drafts in 'My Drafts' section and published in 'Your Scrolls' section."""
    # Create test subject
    subject = Subject(name="Mathematics", description="Math research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    # Create draft preview (should appear in "My Drafts" section)
    draft_preview = Scroll(
        title="Draft Mathematics Paper",
        authors="Test Author",
        abstract="This is a draft paper",
        html_content="<h1>Draft Content</h1>",
        license="cc-by-4.0",
        user_id=test_user.id,
        subject_id=subject.id,
        status="preview",  # Draft status
        url_hash="draft123",
        content_hash="drafthash123",
    )

    # Create published paper (should appear in "Your Scrolls" section)
    published_preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Published Mathematics Paper",
        authors="Test Author",
        abstract="This is a published paper",
        html_content="<h1>Published Content</h1>",
        license="cc-by-4.0",
    )
    published_preview.publish()

    test_db.add(draft_preview)
    test_db.add(published_preview)
    await test_db.commit()

    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    html = response.text

    # Verify "My Drafts" section exists and shows draft
    assert "My Drafts" in html, "Should have 'My Drafts' section"
    assert "Draft Mathematics Paper" in html, "Draft should appear in My Drafts section"
    assert "draft-card" in html, "Should have draft card styling"

    # Verify "Your Scrolls" section exists and shows published paper
    assert "Your Scrolls" in html, "Should have 'Your Scrolls' section"
    assert "Published Mathematics Paper" in html, "Published paper should appear"
    assert "This is a published paper" in html, "Published abstract should appear"

    # Verify drafts have correct styling/metadata
    assert "DRAFT" in html, "Should have draft badge"
    assert "Last edited" in html, "Should show last edited date for drafts"


async def test_dashboard_papers_ordered_by_created_at_descending(
    authenticated_client: AsyncClient, test_db, test_user
):
    """Test 7: Papers are ordered by created_at descending (newest first)."""
    import datetime

    from sqlalchemy import update

    # Create test subject
    subject = Subject(name="Engineering", description="Engineering research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    # Create multiple published previews
    older_preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Older Paper",
        authors="Test Author",
        abstract="This is an older paper",
        html_content="<h1>Older Content</h1>",
        license="cc-by-4.0",
    )
    older_preview.publish()

    newer_preview = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Newer Paper",
        authors="Test Author",
        abstract="This is a newer paper",
        html_content="<h1>Newer Content</h1>",
        license="cc-by-4.0",
    )
    newer_preview.publish()

    test_db.add(older_preview)
    test_db.add(newer_preview)
    await test_db.commit()

    # Manually set different created_at timestamps
    older_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    newer_time = datetime.datetime.now(datetime.timezone.utc)

    await test_db.execute(
        update(Scroll).where(Scroll.id == older_preview.id).values(created_at=older_time)
    )
    await test_db.execute(
        update(Scroll).where(Scroll.id == newer_preview.id).values(created_at=newer_time)
    )
    await test_db.commit()

    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200

    # Check that newer paper appears before older paper in the HTML
    content = response.text
    newer_pos = content.find("Newer Paper")
    older_pos = content.find("Older Paper")
    assert newer_pos != -1 and older_pos != -1
    assert newer_pos < older_pos  # Newer paper should appear first


async def test_dashboard_preview_count_in_title(authenticated_client, test_db, test_user):
    """Test that dashboard title shows correct preview count."""
    # Create test subject
    subject = Subject(name="Computer Science", description="CS research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    # Create 3 published previews
    for i in range(3):
        preview = await create_content_addressable_scroll(
            test_db,
            test_user,
            subject,
            title=f"Test Paper {i + 1}",
            authors="Test Author",
            abstract="Test abstract",
            html_content=f"<h1>Test {i + 1}</h1>",  # Make content unique
            license="cc-by-4.0",
        )
        preview.publish()
        await test_db.commit()  # Commit each one individually

    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert "Your Scrolls (3)" in response.text


async def test_dashboard_empty_state_count(authenticated_client):
    """Test that dashboard shows (0) when user has no previews."""
    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert "Your Scrolls (0)" in response.text
    assert "No published papers yet" in response.text


async def test_navbar_shows_user_menu_when_authenticated(authenticated_client, test_user):
    """Test that navbar shows user menu with display name when user is logged in."""
    response = await authenticated_client.get("/")
    assert response.status_code == 200

    # Check user menu is present
    assert 'class="user-menu-trigger"' in response.text
    assert test_user.display_name in response.text
    # Check for inline SVG user icon instead of image file
    assert '<svg class="user-icon"' in response.text

    # Check dropdown menu items
    assert 'href="/dashboard"' in response.text
    assert 'action="/logout"' in response.text


async def test_navbar_shows_login_button_when_unauthenticated(client):
    """Test that navbar shows login/register buttons when user is not logged in."""
    response = await client.get("/")
    assert response.status_code == 200

    # Check login/register buttons are present
    assert 'href="/login"' in response.text
    assert 'href="/register"' in response.text

    # Check user menu is NOT present
    assert 'class="user-menu-trigger"' not in response.text
    assert "user-icon.svg" not in response.text
