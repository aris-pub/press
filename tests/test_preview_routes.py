"""Unit tests for preview route functionality."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scroll import Scroll


@pytest.mark.asyncio
async def test_upload_creates_preview_scroll(
    client, test_db: AsyncSession, authenticated_client, test_subject
):
    """Test that upload route creates a scroll with preview status."""
    html_content = """
    <!DOCTYPE html>
    <html><head><title>Test Paper</title></head>
    <body><h1>Test Paper</h1><p>Content here with enough words to pass validation.</p></body></html>
    """

    response = await authenticated_client.post(
        "/upload-form",
        data={
            "title": "Test Paper",
            "authors": "John Doe",
            "subject_id": str(test_subject.id),
            "abstract": "This is a test abstract with enough words to pass validation checks.",
            "keywords": "test, paper",
            "html_content": html_content,
            "license": "cc-by-4.0",
            "confirm_rights": "true",
            "action": "publish",
        },
        follow_redirects=False,
    )

    # Should return 200 (preview page rendered)
    assert response.status_code == 200

    # Verify scroll was created with preview status
    result = await test_db.execute(select(Scroll).where(Scroll.title == "Test Paper"))
    scroll = result.scalar_one_or_none()

    assert scroll is not None
    assert scroll.status == "preview"
    assert scroll.published_at is None


@pytest.mark.asyncio
async def test_preview_page_shows_preview_banner(
    authenticated_client, test_db: AsyncSession, test_user, test_subject
):
    """Test that preview page displays preview banner."""
    # Create preview scroll
    scroll = Scroll(
        user_id=test_user.id,
        title="Preview Paper",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Test</h1></body></html>",
        license="cc-by-4.0",
        content_hash="preview123",
        url_hash="preview123",
        status="preview",
    )
    test_db.add(scroll)
    await test_db.commit()

    response = await authenticated_client.get(f"/preview/{scroll.url_hash}")

    assert response.status_code == 200
    assert b"PREVIEW MODE" in response.content or b"Preview:" in response.content


@pytest.mark.asyncio
async def test_confirm_preview_redirects_to_published_scroll(
    authenticated_client, test_db: AsyncSession, test_user, test_subject
):
    """Test that confirming a preview publishes and redirects."""
    # Create preview scroll
    scroll = Scroll(
        user_id=test_user.id,
        title="Preview to Confirm",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Test</h1></body></html>",
        license="cc-by-4.0",
        content_hash="confirm456",
        url_hash="confirm456",
        status="preview",
    )
    test_db.add(scroll)
    await test_db.commit()

    response = await authenticated_client.post(
        f"/preview/{scroll.url_hash}/confirm",
        follow_redirects=False,
    )

    # Should redirect to published scroll
    assert response.status_code == 303
    assert response.headers["location"] == f"/scroll/{scroll.url_hash}"

    # Verify scroll is published
    await test_db.refresh(scroll)
    assert scroll.status == "published"
    assert scroll.published_at is not None


@pytest.mark.asyncio
async def test_cancel_preview_deletes_and_redirects(
    authenticated_client, test_db: AsyncSession, test_user, test_subject
):
    """Test that canceling a preview deletes scroll and redirects to upload."""
    # Create preview scroll
    scroll = Scroll(
        user_id=test_user.id,
        title="Preview to Cancel",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Test</h1></body></html>",
        license="cc-by-4.0",
        content_hash="cancel789",
        url_hash="cancel789",
        status="preview",
    )
    test_db.add(scroll)
    await test_db.commit()
    scroll_id = scroll.id

    response = await authenticated_client.post(
        f"/preview/{scroll.url_hash}/cancel",
        follow_redirects=False,
    )

    # Should redirect to upload page
    assert response.status_code == 303
    assert response.headers["location"] == "/upload"

    # Verify scroll is deleted
    result = await test_db.execute(select(Scroll).where(Scroll.id == scroll_id))
    deleted_scroll = result.scalar_one_or_none()
    assert deleted_scroll is None


@pytest.mark.asyncio
async def test_preview_routes_require_authentication(client, test_db: AsyncSession, test_subject):
    """Test that preview routes redirect unauthenticated users."""
    # Create preview scroll (without user for this test)
    scroll = Scroll(
        title="Preview Paper",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Test</h1></body></html>",
        license="cc-by-4.0",
        content_hash="noauth123",
        url_hash="noauth123",
        status="preview",
    )
    test_db.add(scroll)
    await test_db.commit()

    # Try to access preview page
    response = await client.get(f"/preview/{scroll.url_hash}", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]

    # Try to confirm preview
    response = await client.post(f"/preview/{scroll.url_hash}/confirm", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]

    # Try to cancel preview
    response = await client.post(f"/preview/{scroll.url_hash}/cancel", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


@pytest.mark.asyncio
async def test_preview_iframe_only_accessible_by_owner(
    authenticated_client, test_db: AsyncSession, test_user, test_subject
):
    """Test that preview iframe content is only accessible by the owner."""
    # Create preview scroll owned by test_user
    scroll = Scroll(
        user_id=test_user.id,
        title="Preview Paper",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Preview Content</h1></body></html>",
        license="cc-by-4.0",
        content_hash="iframe123",
        url_hash="iframe123",
        status="preview",
    )
    test_db.add(scroll)
    await test_db.commit()

    # Owner (authenticated_client is logged in as test_user) can access
    response = await authenticated_client.get(f"/scroll/{scroll.url_hash}/paper")
    assert response.status_code == 200
    assert b"Preview Content" in response.content


@pytest.mark.asyncio
async def test_preview_iframe_not_accessible_without_auth(
    client, test_db: AsyncSession, test_user, test_subject
):
    """Test that preview iframe requires authentication."""
    # Create preview scroll
    scroll = Scroll(
        user_id=test_user.id,
        title="Preview Paper",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Preview Content</h1></body></html>",
        license="cc-by-4.0",
        content_hash="iframe456",
        url_hash="iframe456",
        status="preview",
    )
    test_db.add(scroll)
    await test_db.commit()

    # Non-authenticated user cannot access
    response = await client.get(f"/scroll/{scroll.url_hash}/paper")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_published_scroll_iframe_accessible_to_all(
    client, test_db: AsyncSession, test_user, test_subject
):
    """Test that published scroll iframe is accessible to everyone."""
    # Create published scroll
    scroll = Scroll(
        user_id=test_user.id,
        title="Published Paper",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Public Content</h1></body></html>",
        license="cc-by-4.0",
        content_hash="public123",
        url_hash="public123",
        status="published",
    )
    scroll.publish()
    test_db.add(scroll)
    await test_db.commit()

    # Non-authenticated user can access
    response = await client.get(f"/scroll/{scroll.url_hash}/paper")
    assert response.status_code == 200
    assert b"Public Content" in response.content
