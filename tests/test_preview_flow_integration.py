"""Integration tests for preview flow features.

Tests the complete flow including:
- Edit button functionality
- Form prefilling from session
- Resubmit updates existing preview
"""

from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scroll import Scroll


@pytest.mark.asyncio
async def test_resubmit_without_file_uses_existing_html(
    authenticated_client: AsyncClient, test_db: AsyncSession, test_user, test_subject
):
    """Test that resubmitting without a new file preserves existing HTML content."""
    original_html = b"<html><body><h1>Original Content</h1></body></html>"

    # Create initial preview
    form_data = {
        "title": "Original Title",
        "authors": "Test Author",
        "subject_id": str(test_subject.id),
        "abstract": "Test abstract",
        "keywords": "test",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
    }

    response = await authenticated_client.post(
        "/upload-form",
        data=form_data,
        files={"file": ("test.html", original_html, "text/html")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    preview_url = response.headers["location"]
    url_hash = preview_url.split("/")[-1]

    # Click Edit Details
    response = await authenticated_client.post(f"/preview/{url_hash}/edit", follow_redirects=False)
    assert response.status_code == 303

    # Resubmit with modified metadata but NO new file
    modified_form_data = {
        "title": "Updated Title",
        "authors": "Test Author",
        "subject_id": str(test_subject.id),
        "abstract": "Test abstract",
        "keywords": "test",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
    }

    response = await authenticated_client.post(
        "/upload-form",
        data=modified_form_data,
        # NO file parameter - should use existing HTML
        follow_redirects=False,
    )

    assert response.status_code == 303

    # Verify the HTML content is preserved from original upload
    result = await test_db.execute(
        select(Scroll)
        .where(Scroll.status == "preview", Scroll.title == "Updated Title")
        .order_by(Scroll.created_at.desc())
        .limit(1)
    )
    scroll = result.scalar_one_or_none()

    assert scroll is not None
    assert scroll.title == "Updated Title"
    assert scroll.html_content == original_html.decode("utf-8")


@pytest.mark.asyncio
async def test_resubmit_with_new_file_replaces_html(
    authenticated_client: AsyncClient, test_db: AsyncSession, test_user, test_subject
):
    """Test that resubmitting with a new file replaces the HTML content."""
    original_html = b"<html><body><h1>Original Content</h1></body></html>"
    new_html = b"<html><body><h1>New Content</h1></body></html>"

    # Create initial preview
    form_data = {
        "title": "Test Title",
        "authors": "Test Author",
        "subject_id": str(test_subject.id),
        "abstract": "Test abstract",
        "keywords": "test",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
    }

    response = await authenticated_client.post(
        "/upload-form",
        data=form_data,
        files={"file": ("test.html", original_html, "text/html")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    preview_url = response.headers["location"]
    url_hash = preview_url.split("/")[-1]

    # Click Edit Details
    response = await authenticated_client.post(f"/preview/{url_hash}/edit", follow_redirects=False)
    assert response.status_code == 303

    # Resubmit with NEW file
    response = await authenticated_client.post(
        "/upload-form",
        data=form_data,
        files={"file": ("test.html", new_html, "text/html")},
        follow_redirects=False,
    )

    assert response.status_code == 303

    # Verify the HTML content is replaced
    result = await test_db.execute(
        select(Scroll)
        .where(Scroll.status == "preview", Scroll.title == "Test Title")
        .order_by(Scroll.created_at.desc())
        .limit(1)
    )
    scroll = result.scalar_one_or_none()

    assert scroll is not None
    assert scroll.html_content == new_html.decode("utf-8")
    assert scroll.html_content != original_html.decode("utf-8")


@pytest.mark.asyncio
async def test_edit_button_redirects_to_upload(
    authenticated_client: AsyncClient, test_db: AsyncSession, test_user, test_subject
):
    """Test that clicking Edit Details redirects to upload page."""
    # Create a preview
    form_data = {
        "title": "Test Preview",
        "authors": "Test Author",
        "subject_id": str(test_subject.id),
        "abstract": "Test abstract",
        "keywords": "test",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
    }

    response = await authenticated_client.post(
        "/upload-form",
        data=form_data,
        files={"file": ("test.html", b"<html><body>Test</body></html>", "text/html")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    preview_url = response.headers["location"]
    url_hash = preview_url.split("/")[-1]

    # Click Edit Details button
    response = await authenticated_client.post(f"/preview/{url_hash}/edit", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/upload"


@pytest.mark.asyncio
async def test_edit_button_requires_ownership(
    authenticated_client: AsyncClient, test_db: AsyncSession, test_user, test_subject
):
    """Test that edit button only works for preview owner."""
    from app.auth.utils import get_password_hash
    from app.models.user import User

    # Create another user
    other_user = User(
        email="other@example.com",
        password_hash=get_password_hash("password123"),
        display_name="Other User",
        email_verified=True,
    )
    test_db.add(other_user)
    await test_db.commit()
    await test_db.refresh(other_user)

    # Create a preview owned by other_user
    scroll = Scroll(
        user_id=other_user.id,
        title="Other User's Preview",
        authors="Other Author",
        subject_id=test_subject.id,
        abstract="Test abstract",
        html_content="<html><body>Test</body></html>",
        license="cc-by-4.0",
        url_hash="other123",
        content_hash="hash123",
        status="preview",
    )
    test_db.add(scroll)
    await test_db.commit()

    # Try to edit as test_user (different owner)
    response = await authenticated_client.post("/preview/other123/edit", follow_redirects=False)

    # Should fail with 404
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_form_prefills_from_session_after_edit(
    authenticated_client: AsyncClient, test_db: AsyncSession, test_user, test_subject
):
    """Test that upload form pre-fills with data after clicking Edit Details."""
    # Create a preview
    form_data = {
        "title": "Original Title",
        "authors": "Original Author",
        "subject_id": str(test_subject.id),
        "abstract": "Original abstract",
        "keywords": "original, keywords",
        "license": "arr",
        "confirm_rights": "true",
    }

    response = await authenticated_client.post(
        "/upload-form",
        data=form_data,
        files={"file": ("test.html", b"<html><body>Test</body></html>", "text/html")},
    )

    preview_url = response.headers["location"]
    url_hash = preview_url.split("/")[-1]

    # Click Edit Details
    await authenticated_client.post(f"/preview/{url_hash}/edit")

    # Visit upload page
    response = await authenticated_client.get("/upload")
    html = response.text

    # Form should be pre-filled
    assert "Original Title" in html
    assert "Original Author" in html
    assert "Original abstract" in html
    assert "original, keywords" in html


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_resubmit_updates_existing_preview(
    authenticated_client: AsyncClient, test_db: AsyncSession, test_user, test_subject
):
    """Test that resubmitting form updates existing preview instead of creating duplicate."""
    # Create initial preview
    form_data = {
        "title": "Original Title",
        "authors": "Original Author",
        "subject_id": str(test_subject.id),
        "abstract": "Original abstract",
        "keywords": "original",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
    }

    await authenticated_client.post(
        "/upload-form",
        data=form_data,
        files={"file": ("test.html", b"<html><body>Test</body></html>", "text/html")},
    )

    # Edit and resubmit with different metadata
    form_data["title"] = "Updated Title"
    form_data["abstract"] = "Updated abstract"

    await authenticated_client.post(
        "/upload-form",
        data=form_data,
        files={"file": ("test.html", b"<html><body>Test</body></html>", "text/html")},
    )

    # Should still only have one preview
    result = await test_db.execute(
        select(Scroll).where(
            Scroll.user_id == test_user.id,
            Scroll.status == "preview",
        )
    )
    previews = result.scalars().all()
    assert len(previews) == 1

    # Preview should have updated data
    assert previews[0].title == "Updated Title"
    assert previews[0].abstract == "Updated abstract"


@pytest.mark.asyncio
async def test_resubmit_creates_new_preview_if_content_differs(
    authenticated_client: AsyncClient, test_db: AsyncSession, test_user, test_subject
):
    """Test that resubmitting with different content creates a new preview."""
    # Create initial preview
    form_data = {
        "title": "First Paper",
        "authors": "Test Author",
        "subject_id": str(test_subject.id),
        "abstract": "First abstract",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
    }

    await authenticated_client.post(
        "/upload-form",
        data=form_data,
        files={"file": ("test1.html", b"<html><body>Content 1</body></html>", "text/html")},
    )

    # Submit with different HTML content
    form_data["title"] = "Second Paper"
    await authenticated_client.post(
        "/upload-form",
        data=form_data,
        files={"file": ("test2.html", b"<html><body>Content 2</body></html>", "text/html")},
    )

    # Should have two previews (different content)
    result = await test_db.execute(
        select(Scroll).where(
            Scroll.user_id == test_user.id,
            Scroll.status == "preview",
        )
    )
    previews = result.scalars().all()
    assert len(previews) == 2


@pytest.mark.asyncio
async def test_session_data_cleared_after_confirm(
    authenticated_client: AsyncClient, test_db: AsyncSession, test_user, test_subject
):
    """Test that session data is cleared after confirming preview."""
    # Create a preview
    form_data = {
        "title": "Test Preview",
        "authors": "Test Author",
        "subject_id": str(test_subject.id),
        "abstract": "Test abstract",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
    }

    response = await authenticated_client.post(
        "/upload-form",
        data=form_data,
        files={"file": ("test.html", b"<html><body>Test</body></html>", "text/html")},
    )

    url_hash = response.headers["location"].split("/")[-1]

    # Confirm preview (publishes it)
    await authenticated_client.post(f"/preview/{url_hash}/confirm")

    # Visit upload page
    response = await authenticated_client.get("/upload")
    html = response.text

    # Form should NOT be pre-filled anymore
    assert "Test Preview" not in html or 'value="Test Preview"' not in html


@pytest.mark.asyncio
async def test_banner_shows_draft_title(
    authenticated_client: AsyncClient, test_db: AsyncSession, test_user, test_subject
):
    """Test that the banner shows the draft title (or 'Untitled' if empty)."""
    # Create a draft with a title
    form_data = {
        "title": "My Research Paper",
        "authors": "Test Author",
        "subject_id": str(test_subject.id),
        "abstract": "Test abstract",
        "keywords": "test",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
    }

    response = await authenticated_client.post(
        "/upload-form",
        data=form_data,
        files={"file": ("test.html", b"<html><body>Test</body></html>", "text/html")},
        follow_redirects=False,
    )

    assert response.status_code == 303

    # Navigate to dashboard first (clears active editing context)
    await authenticated_client.get("/dashboard")

    # Now visit upload page (should show banner with draft title)
    response = await authenticated_client.get("/upload")
    html = response.text

    # Banner should show the draft title
    assert "My Research Paper" in html, "Draft title should appear in banner"
    assert "You have 1 draft" in html, "Banner should show draft count"

    # Form should be EMPTY (not pre-filled)
    assert 'value="My Research Paper"' not in html, "Form should not be pre-filled"


@pytest.mark.asyncio
async def test_start_fresh_clears_session(
    authenticated_client: AsyncClient, test_db: AsyncSession, test_user, test_subject
):
    """Test that Start Fresh button clears session data."""
    # Create a draft
    form_data = {
        "title": "Draft to Clear",
        "authors": "Test Author",
        "subject_id": str(test_subject.id),
        "abstract": "Test abstract",
        "keywords": "test",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
    }

    response = await authenticated_client.post(
        "/upload-form",
        data=form_data,
        files={"file": ("test.html", b"<html><body>Test</body></html>", "text/html")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    url_hash = response.headers["location"].split("/")[-1]

    # Click Edit Details to load draft into session
    response = await authenticated_client.post(f"/preview/{url_hash}/edit", follow_redirects=False)
    assert response.status_code == 303

    # Verify form is pre-filled
    response = await authenticated_client.get("/upload")
    html = response.text
    assert 'value="Draft to Clear"' in html

    # Click Start Fresh
    response = await authenticated_client.post("/upload/start-fresh", follow_redirects=False)
    assert response.status_code == 303

    # Visit upload page again - form should be empty AND banner should be hidden
    response = await authenticated_client.get("/upload")
    html = response.text

    # Form should be empty (session cleared)
    assert 'value="Draft to Clear"' not in html

    # Banner should NOT appear (dismissed for this session)
    assert "drafts-banner" not in html, "Banner should be dismissed after Start Fresh"
    assert "You have 1 draft" not in html, "Banner text should not appear"

    # But draft still exists in database
    result = await test_db.execute(
        select(Scroll).where(Scroll.url_hash == url_hash, Scroll.status == "preview")
    )
    assert result.scalar_one_or_none() is not None, "Draft should still exist in DB"


@pytest.mark.asyncio
async def test_dashboard_visit_clears_preview_session(
    authenticated_client: AsyncClient, test_db: AsyncSession, test_user, test_subject
):
    """Test that visiting dashboard clears preview editing session data."""
    # Create a draft and click Edit Details to load it into session
    form_data = {
        "title": "Dashboard Clear Test",
        "authors": "Test Author",
        "subject_id": str(test_subject.id),
        "abstract": "Testing dashboard clearing session",
        "keywords": "test",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
    }

    response = await authenticated_client.post(
        "/upload-form",
        data=form_data,
        files={"file": ("test.html", b"<html><body>Test</body></html>", "text/html")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    url_hash = response.headers["location"].split("/")[-1]

    # Click Edit Details to load draft into session
    response = await authenticated_client.post(f"/preview/{url_hash}/edit", follow_redirects=False)
    assert response.status_code == 303

    # Verify form is pre-filled (session has form_data)
    response = await authenticated_client.get("/upload")
    html = response.text
    assert 'value="Dashboard Clear Test"' in html, "Form should be pre-filled after Edit Details"

    # Visit dashboard (should clear preview session data)
    await authenticated_client.get("/dashboard")

    # Visit upload page again - should show banner (not pre-filled form)
    response = await authenticated_client.get("/upload")
    html = response.text

    # Form should NOT be pre-filled (session cleared)
    assert 'value="Dashboard Clear Test"' not in html, (
        "Form should not be pre-filled after dashboard visit"
    )

    # Banner should appear (draft exists but not in active editing mode)
    assert "You have 1 draft" in html, "Banner should appear after dashboard clears session"
    assert "Dashboard Clear Test" in html, "Banner should show draft title"
