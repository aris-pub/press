"""Essential tests for scroll page functionality."""

from httpx import AsyncClient

from app.models.preview import Preview, Subject


async def test_scroll_page_functionality(client: AsyncClient, test_db, test_user):
    """Test critical scroll page functionality."""
    # Create subject
    subject = Subject(name="Test Subject")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    # Create and publish scroll (all scrolls are published directly)
    preview = Preview(
        title="Basic Test Scroll",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Content</h1>",
        status="published",  # Always published now
        user_id=test_user.id,
        subject_id=subject.id,
    )
    test_db.add(preview)
    await test_db.commit()
    await test_db.refresh(preview)

    # Publish to get preview_id
    preview.publish()
    await test_db.commit()
    await test_db.refresh(preview)

    # Test the page
    response = await client.get(f"/scroll/{preview.preview_id}")
    assert response.status_code == 200

    # Functionality: Check key components are present
    assert "basic test scroll" in response.text.lower()
    assert 'class="fab"' in response.text
    assert "press-logo-64.svg" in response.text
    assert 'id="info-modal"' in response.text
    assert "scroll press" in response.text.lower()

    # Standalone: Check navbar is not present
    assert "<nav" not in response.text.lower()
    assert "login" not in response.text.lower()

    # JavaScript: Check essential functions are present
    assert "function openModal()" in response.text
    assert "function downloadHTML()" in response.text


async def test_scroll_not_found(client: AsyncClient):
    """Test 404 for non-existent scroll."""
    response = await client.get("/scroll/nonexistent")
    assert response.status_code == 404
