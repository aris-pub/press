"""Debug test to understand current homepage structure."""

from httpx import AsyncClient
import pytest


@pytest.mark.asyncio
async def test_debug_homepage_structure(client: AsyncClient, test_db, test_user):
    """Debug test to see what's actually rendered on homepage."""
    # Create test data first
    from app.models.scroll import Subject
    from tests.conftest import create_content_addressable_scroll

    # Create test subjects
    physics_subject = Subject(name="Physics", description="Physics research")
    test_db.add(physics_subject)
    await test_db.commit()
    await test_db.refresh(physics_subject)

    # Create test scroll
    physics_scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        physics_subject,
        title="Test Physics Paper",
        authors="Test Author",
        abstract="Physics research",
        html_content="<h1>Physics Content</h1>",
        license="cc-by-4.0",
    )
    physics_scroll.publish()
    await test_db.commit()

    response = await client.get("/")
    assert response.status_code == 200
    html_content = response.text

    # Print relevant sections for debugging
    print("\n=== HOMEPAGE HTML DEBUG ===")

    # Find recent scrolls section
    if "recent-submissions-heading" in html_content:
        print("✓ Found recent submissions section")
    else:
        print("✗ Recent submissions section not found")

    # Check for subject cards
    if "subject-card" in html_content:
        print("✓ Found subject cards")
        # Extract a sample subject card
        import re

        subject_pattern = r'<div class="subject-card"[^>]*>(.*?)</div>'
        matches = re.findall(subject_pattern, html_content, re.DOTALL)
        if matches:
            print(f"Sample subject card: {matches[0][:200]}...")
    else:
        print("✗ No subject cards found")

    # Check for scroll cards
    if "scroll" in html_content:
        print("✓ Found scroll elements")
        # Look for scroll-related classes
        scroll_classes = []
        if 'class="scroll' in html_content:
            scroll_classes.append("scroll")
        if 'class="preview' in html_content:
            scroll_classes.append("preview")
        print(f"Scroll classes found: {scroll_classes}")
    else:
        print("✗ No scroll elements found")

    # Check for data attributes
    data_attrs = []
    if "data-subject=" in html_content:
        data_attrs.append("data-subject")
    if "data-subject-name=" in html_content:
        data_attrs.append("data-subject-name")
    if "data-subject-display=" in html_content:
        data_attrs.append("data-subject-display")
    print(f"Data attributes found: {data_attrs}")

    # Look for specific subject filtering elements
    filtering_elements = []
    if "filterPreviews" in html_content:
        filtering_elements.append("filterPreviews function")
    if "previewCards" in html_content:
        filtering_elements.append("previewCards variable")
    if "subjectCards" in html_content:
        filtering_elements.append("subjectCards variable")
    print(f"Filtering elements found: {filtering_elements}")

    print("=== END DEBUG ===\n")

    # The test should always pass - it's just for debugging
    assert True
