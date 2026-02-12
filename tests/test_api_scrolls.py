"""Tests for /api/scrolls endpoint used by subject filtering."""

from httpx import AsyncClient
import pytest

from app.models.scroll import Subject
from tests.conftest import create_content_addressable_scroll


@pytest.mark.asyncio
async def test_api_scrolls_returns_all_scrolls_without_filter(
    client: AsyncClient, test_db, test_user
):
    """Test that /api/scrolls returns all scrolls when no subject filter."""
    # Create subjects
    physics = Subject(name="Physics", description="Physics research")
    cs = Subject(name="Computer Science", description="CS research")
    test_db.add_all([physics, cs])
    await test_db.commit()
    await test_db.refresh(physics)
    await test_db.refresh(cs)

    # Create scrolls with unique content
    physics_scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        physics,
        title="Quantum Paper",
        authors="Alice",
        abstract="Physics abstract",
        html_content="<h1>Quantum Physics Content</h1>",
    )
    physics_scroll.publish()

    cs_scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        cs,
        title="Algorithm Paper",
        authors="Bob",
        abstract="CS abstract",
        html_content="<h1>Computer Science Content</h1>",
    )
    cs_scroll.publish()

    await test_db.commit()

    # Request all scrolls
    response = await client.get("/api/scrolls")
    assert response.status_code == 200

    data = response.json()
    assert "scrolls" in data
    assert len(data["scrolls"]) == 2

    # Verify both scrolls are present
    titles = [s["title"] for s in data["scrolls"]]
    assert "Quantum Paper" in titles
    assert "Algorithm Paper" in titles


@pytest.mark.asyncio
async def test_api_scrolls_filters_by_subject(client: AsyncClient, test_db, test_user):
    """Test that /api/scrolls filters by subject parameter."""
    # Create subjects
    physics = Subject(name="Physics", description="Physics research")
    cs = Subject(name="Computer Science", description="CS research")
    test_db.add_all([physics, cs])
    await test_db.commit()
    await test_db.refresh(physics)
    await test_db.refresh(cs)

    # Create scrolls with unique content
    physics_scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        physics,
        title="Quantum Paper",
        authors="Alice",
        abstract="Physics abstract",
        html_content="<h1>Quantum Research Content</h1>",
    )
    physics_scroll.publish()

    cs_scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        cs,
        title="Algorithm Paper",
        authors="Bob",
        abstract="CS abstract",
        html_content="<h1>Algorithm Research Content</h1>",
    )
    cs_scroll.publish()

    await test_db.commit()

    # Request only Physics scrolls
    response = await client.get("/api/scrolls?subject=Physics")
    assert response.status_code == 200

    data = response.json()
    assert len(data["scrolls"]) == 1
    assert data["scrolls"][0]["title"] == "Quantum Paper"
    assert data["scrolls"][0]["subject_name"] == "Physics"


@pytest.mark.asyncio
async def test_api_scrolls_returns_empty_for_nonexistent_subject(
    client: AsyncClient, test_db, test_user
):
    """Test that /api/scrolls returns empty list for nonexistent subject."""
    response = await client.get("/api/scrolls?subject=Nonexistent")
    assert response.status_code == 200

    data = response.json()
    assert len(data["scrolls"]) == 0


@pytest.mark.asyncio
async def test_api_scrolls_respects_limit_parameter(client: AsyncClient, test_db, test_user):
    """Test that /api/scrolls respects the limit parameter."""
    # Create subject
    physics = Subject(name="Physics", description="Physics research")
    test_db.add(physics)
    await test_db.commit()
    await test_db.refresh(physics)

    # Create 5 scrolls with unique content
    for i in range(5):
        scroll = await create_content_addressable_scroll(
            test_db,
            test_user,
            physics,
            title=f"Paper {i}",
            authors="Alice",
            abstract=f"Abstract {i}",
            html_content=f"<h1>Content {i}</h1><p>Unique content for scroll {i}</p>",
        )
        scroll.publish()

    await test_db.commit()

    # Request with limit=2
    response = await client.get("/api/scrolls?limit=2")
    assert response.status_code == 200

    data = response.json()
    assert len(data["scrolls"]) == 2


@pytest.mark.asyncio
async def test_api_scrolls_returns_newest_first(client: AsyncClient, test_db, test_user):
    """Test that /api/scrolls returns scrolls in descending order by created_at."""
    # Create subject
    physics = Subject(name="Physics", description="Physics research")
    test_db.add(physics)
    await test_db.commit()
    await test_db.refresh(physics)

    # Create scrolls in order with unique content
    scroll1 = await create_content_addressable_scroll(
        test_db,
        test_user,
        physics,
        title="First Paper",
        authors="Alice",
        abstract="First",
        html_content="<h1>First Content</h1>",
    )
    scroll1.publish()
    await test_db.commit()

    scroll2 = await create_content_addressable_scroll(
        test_db,
        test_user,
        physics,
        title="Second Paper",
        authors="Bob",
        abstract="Second",
        html_content="<h1>Second Content</h1>",
    )
    scroll2.publish()
    await test_db.commit()

    # Request scrolls
    response = await client.get("/api/scrolls")
    data = response.json()

    # Newest should be first
    assert data["scrolls"][0]["title"] == "Second Paper"
    assert data["scrolls"][1]["title"] == "First Paper"


@pytest.mark.asyncio
async def test_api_scrolls_includes_required_fields(client: AsyncClient, test_db, test_user):
    """Test that /api/scrolls includes all required fields."""
    # Create subject and scroll
    physics = Subject(name="Physics", description="Physics research")
    test_db.add(physics)
    await test_db.commit()
    await test_db.refresh(physics)

    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        physics,
        title="Test Paper",
        authors="Alice",
        abstract="Test abstract",
        keywords=["quantum", "mechanics"],
        html_content="<h1>Test Paper Content</h1>",
    )
    scroll.publish()
    await test_db.commit()

    # Request scrolls
    response = await client.get("/api/scrolls")
    data = response.json()

    scroll_data = data["scrolls"][0]
    required_fields = [
        "title",
        "authors",
        "abstract",
        "keywords",
        "subject_name",
        "version",
        "url_hash",
        "created_at",
    ]

    for field in required_fields:
        assert field in scroll_data, f"Missing required field: {field}"

    # Verify field values
    assert scroll_data["title"] == "Test Paper"
    assert scroll_data["authors"] == "Alice"
    assert scroll_data["subject_name"] == "Physics"
    assert scroll_data["keywords"] == ["quantum", "mechanics"]


@pytest.mark.asyncio
async def test_partials_scrolls_returns_html(client: AsyncClient, test_db, test_user):
    """Test that /partials/scrolls returns HTML partial for HTMX."""
    # Create subject and scroll
    physics = Subject(name="Physics", description="Physics research")
    test_db.add(physics)
    await test_db.commit()
    await test_db.refresh(physics)

    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        physics,
        title="Test Paper",
        authors="Alice",
        abstract="Test abstract",
        html_content="<h1>Test Content</h1>",
    )
    scroll.publish()
    await test_db.commit()

    # Request HTML partial
    response = await client.get("/partials/scrolls")
    assert response.status_code == 200

    # Should return HTML, not JSON
    assert "text/html" in response.headers["content-type"]
    html = response.text

    # Should contain scroll card elements
    assert 'class="scrolls-grid"' in html or 'id="scrolls-grid"' in html
    assert "Test Paper" in html
    assert "Alice" in html


@pytest.mark.asyncio
async def test_partials_scrolls_filters_by_subject(
    client: AsyncClient, test_db, test_user
):
    """Test that /partials/scrolls filters by subject and returns HTML."""
    # Create subjects
    physics = Subject(name="Physics", description="Physics research")
    cs = Subject(name="Computer Science", description="CS research")
    test_db.add_all([physics, cs])
    await test_db.commit()
    await test_db.refresh(physics)
    await test_db.refresh(cs)

    # Create scrolls
    physics_scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        physics,
        title="Quantum Paper",
        authors="Alice",
        abstract="Physics abstract",
        html_content="<h1>Quantum Content</h1>",
    )
    physics_scroll.publish()

    cs_scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        cs,
        title="Algorithm Paper",
        authors="Bob",
        abstract="CS abstract",
        html_content="<h1>Algorithm Content</h1>",
    )
    cs_scroll.publish()

    await test_db.commit()

    # Request only Physics scrolls
    response = await client.get("/partials/scrolls?subject=Physics")
    assert response.status_code == 200

    html = response.text
    # Should contain Physics paper
    assert "Quantum Paper" in html
    # Should NOT contain CS paper
    assert "Algorithm Paper" not in html
