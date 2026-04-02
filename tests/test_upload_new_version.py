"""Tests for Upload New Version button on dashboard and upload form revision variant."""

from httpx import AsyncClient
import pytest

from tests.conftest import create_content_addressable_scroll


@pytest.mark.asyncio
async def test_dashboard_shows_upload_new_version_for_published_scrolls(
    authenticated_client: AsyncClient, test_db, test_user, test_subject
):
    scroll = await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="Published Scroll"
    )

    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert f"/upload?revises={scroll.url_hash}" in response.text
    assert "Upload New Version" in response.text


@pytest.mark.asyncio
async def test_dashboard_does_not_show_upload_button_for_preview_scrolls(
    authenticated_client: AsyncClient, test_db, test_user, test_subject
):
    scroll = await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="Draft Scroll"
    )
    scroll.status = "preview"
    await test_db.commit()

    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    # The draft should appear in drafts section, not with an Upload New Version button
    assert "Upload New Version" not in response.text


@pytest.mark.asyncio
async def test_upload_form_prefills_metadata_when_revising(
    authenticated_client: AsyncClient, test_db, test_user, test_subject
):
    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Original Title",
        authors="Jane Doe, John Smith",
        abstract="Original abstract text",
        keywords=["quantum", "physics"],
    )

    response = await authenticated_client.get(f"/upload?revises={scroll.url_hash}")
    assert response.status_code == 200
    assert "Original Title" in response.text
    assert "Jane Doe, John Smith" in response.text
    assert "Original abstract text" in response.text
    assert "quantum, physics" in response.text


@pytest.mark.asyncio
async def test_upload_form_header_changes_when_revising(
    authenticated_client: AsyncClient, test_db, test_user, test_subject
):
    scroll = await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="My Great Paper"
    )

    response = await authenticated_client.get(f"/upload?revises={scroll.url_hash}")
    assert response.status_code == 200
    assert "Upload New Version" in response.text
    # The revision context box should show the scroll title and version info
    assert "My Great Paper" in response.text
    assert "v1" in response.text or "v 1" in response.text


@pytest.mark.asyncio
async def test_upload_form_shows_revision_context_box(
    authenticated_client: AsyncClient, test_db, test_user, test_subject
):
    scroll = await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="Spectral Properties"
    )

    response = await authenticated_client.get(f"/upload?revises={scroll.url_hash}")
    assert response.status_code == 200
    assert "revision-context" in response.text
    assert "Updating:" in response.text
    assert "This will become v2" in response.text


@pytest.mark.asyncio
async def test_upload_form_submit_button_changes_when_revising(
    authenticated_client: AsyncClient, test_db, test_user, test_subject
):
    scroll = await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="Test Paper"
    )

    response = await authenticated_client.get(f"/upload?revises={scroll.url_hash}")
    assert response.status_code == 200
    assert "Preview New Version" in response.text


@pytest.mark.asyncio
async def test_upload_revises_invalid_hash_ignored(
    authenticated_client: AsyncClient, test_db, test_user, test_subject
):
    """An invalid hash should just show the normal upload form."""
    response = await authenticated_client.get("/upload?revises=nonexistenthash")
    assert response.status_code == 200
    assert "revision-context" not in response.text
    assert "Upload New Scroll" in response.text


@pytest.mark.asyncio
async def test_upload_revises_other_users_scroll_rejected(
    authenticated_client: AsyncClient, test_db, test_user, test_subject
):
    """Cannot revise a scroll owned by a different user."""
    from app.auth.utils import get_password_hash
    from app.models.user import User

    other_user = User(
        email="other@example.com",
        password_hash=get_password_hash("password123"),
        display_name="Other User",
        email_verified=True,
    )
    test_db.add(other_user)
    await test_db.commit()
    await test_db.refresh(other_user)

    scroll = await create_content_addressable_scroll(
        test_db, other_user, test_subject, title="Other User Scroll"
    )

    response = await authenticated_client.get(f"/upload?revises={scroll.url_hash}")
    assert response.status_code == 200
    # Should show normal upload form, not revision mode
    assert "revision-context" not in response.text
    assert "Upload New Scroll" in response.text


@pytest.mark.asyncio
async def test_dashboard_shows_only_latest_version_per_scroll(
    authenticated_client: AsyncClient, test_db, test_user, test_subject
):
    """When a scroll has multiple versions, dashboard should show only the latest."""
    import uuid

    series_id = uuid.uuid4()

    # Create v1 of a scroll
    v1 = await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="My Paper v1", html_content="<h1>v1</h1>"
    )
    v1.version = 1
    v1.scroll_series_id = series_id
    v1.slug = "my-paper"
    v1.publication_year = 2026

    # Create v2 of the same scroll
    v2 = await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="My Paper v2", html_content="<h1>v2</h1>"
    )
    v2.version = 2
    v2.scroll_series_id = series_id
    v2.slug = "my-paper"
    v2.publication_year = 2026

    await test_db.commit()

    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    # v2 (latest) should be shown, v1 should not
    assert "My Paper v2" in response.text
    assert "My Paper v1" not in response.text
    # Only one Upload New Version button
    assert response.text.count("Upload New Version") == 1


@pytest.mark.asyncio
async def test_dashboard_shows_separate_cards_for_different_scrolls(
    authenticated_client: AsyncClient, test_db, test_user, test_subject
):
    """Different scroll series should each get their own card."""
    import uuid

    scroll_a = await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="Paper Alpha", html_content="<h1>Alpha</h1>"
    )
    scroll_a.scroll_series_id = uuid.uuid4()
    scroll_a.slug = "paper-alpha"
    scroll_a.publication_year = 2026

    scroll_b = await create_content_addressable_scroll(
        test_db, test_user, test_subject, title="Paper Beta", html_content="<h1>Beta</h1>"
    )
    scroll_b.scroll_series_id = uuid.uuid4()
    scroll_b.slug = "paper-beta"
    scroll_b.publication_year = 2026

    await test_db.commit()

    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert "Paper Alpha" in response.text
    assert "Paper Beta" in response.text
    assert response.text.count("Upload New Version") == 2


@pytest.mark.asyncio
async def test_upload_form_normal_mode_unchanged(
    authenticated_client: AsyncClient, test_db, test_user, test_subject
):
    """Normal upload form (no revises param) should be unchanged."""
    response = await authenticated_client.get("/upload")
    assert response.status_code == 200
    assert "Upload New Scroll" in response.text
    assert "Share your interactive" in response.text
    assert "revision-context" not in response.text
    assert "Preview Scroll" in response.text
