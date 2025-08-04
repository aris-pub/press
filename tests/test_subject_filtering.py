"""Tests for subject filtering functionality on homepage."""

from httpx import AsyncClient
import pytest

from app.models.scroll import Subject
from tests.conftest import create_content_addressable_scroll


@pytest.mark.asyncio
async def test_homepage_subject_filtering_data_attributes(client: AsyncClient, test_db, test_user):
    """Test that homepage scroll cards have correct data-subject attributes for filtering."""
    # Create test subjects
    physics_subject = Subject(name="Physics", description="Physics research")
    cs_subject = Subject(name="Computer Science", description="CS research")
    test_db.add(physics_subject)
    test_db.add(cs_subject)
    await test_db.commit()
    await test_db.refresh(physics_subject)
    await test_db.refresh(cs_subject)

    # Create test scrolls in different subjects
    physics_scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        physics_subject,
        title="Quantum Mechanics Study",
        authors="Test Author",
        abstract="Physics research",
        html_content="<h1>Physics Content</h1>",
        license="cc-by-4.0",
    )
    physics_scroll.publish()

    cs_scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        cs_subject,
        title="Algorithm Analysis",
        authors="Test Author",
        abstract="Computer Science research",
        html_content="<h1>CS Content</h1>",
        license="cc-by-4.0",
    )
    cs_scroll.publish()

    await test_db.commit()

    # Get homepage
    response = await client.get("/")
    assert response.status_code == 200
    html_content = response.text

    # Check that scroll cards have correct data-subject attributes (normalized format)
    assert 'data-subject="physics"' in html_content
    assert 'data-subject="computer-science"' in html_content

    # Check that subject cards have correct data attributes for filtering
    # Subject names are normalized to lowercase with dashes
    assert 'data-subject-name="physics"' in html_content
    assert 'data-subject-name="computer-science"' in html_content

    # Verify the scroll cards have the preview class for JavaScript targeting
    assert 'class="scroll preview"' in html_content


@pytest.mark.asyncio
async def test_subject_card_data_attributes(client: AsyncClient, test_db):
    """Test that subject cards have the correct data attributes for JavaScript filtering."""
    # Create test subject to ensure subject cards are rendered
    from app.models.scroll import Subject

    physics_subject = Subject(name="Physics", description="Physics research")
    test_db.add(physics_subject)
    await test_db.commit()

    response = await client.get("/")
    assert response.status_code == 200
    html_content = response.text

    # Subject cards should have data-subject-name and data-subject-display attributes
    # These are used by JavaScript for filtering
    assert "data-subject-name=" in html_content
    assert 'class="subject-card"' in html_content
