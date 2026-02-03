"""Tests for admin notification integration during signup and publish events."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scroll import Scroll


@pytest.mark.asyncio
@patch("app.routes.auth.get_email_service")
async def test_admin_notified_on_user_signup(mock_get_email_service, client: AsyncClient):
    """Test that admin receives notification when a new user signs up."""
    mock_email_service = AsyncMock()
    mock_email_service.send_verification_email = AsyncMock(return_value=True)
    mock_email_service.send_admin_signup_notification = AsyncMock(return_value=True)
    mock_get_email_service.return_value = mock_email_service

    register_data = {
        "email": "testuser@example.com",
        "password": "testpass123",
        "confirm_password": "testpass123",
        "display_name": "Test User",
        "agree_terms": "true",
    }

    response = await client.post("/register-form", data=register_data)
    assert response.status_code == 200
    assert "session_id" in response.cookies

    mock_email_service.send_admin_signup_notification.assert_called_once()
    call_args = mock_email_service.send_admin_signup_notification.call_args
    assert call_args.kwargs["user_email"] == "testuser@example.com"
    assert call_args.kwargs["display_name"] == "Test User"
    assert "user_id" in call_args.kwargs


@pytest.mark.asyncio
@patch("app.routes.auth.get_email_service")
async def test_admin_notification_not_sent_when_email_service_unavailable(
    mock_get_email_service, client: AsyncClient
):
    """Test that signup works even when email service is not configured."""
    mock_get_email_service.return_value = None

    register_data = {
        "email": "testuser2@example.com",
        "password": "testpass123",
        "confirm_password": "testpass123",
        "display_name": "Test User 2",
        "agree_terms": "true",
    }

    response = await client.post("/register-form", data=register_data)
    assert response.status_code == 200
    assert "session_id" in response.cookies


@pytest.mark.asyncio
@patch("app.routes.scrolls.get_email_service")
async def test_admin_notified_on_preview_publish(
    mock_get_email_service, authenticated_client, test_db: AsyncSession, test_user, test_subject
):
    """Test that admin receives notification when a preview is published."""
    mock_email_service = AsyncMock()
    mock_email_service.send_admin_publish_notification = AsyncMock(return_value=True)
    mock_get_email_service.return_value = mock_email_service

    scroll = Scroll(
        user_id=test_user.id,
        title="Test Paper for Notification",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Test</h1></body></html>",
        license="cc-by-4.0",
        content_hash="notify123",
        url_hash="notify123",
        status="preview",
    )
    test_db.add(scroll)
    await test_db.commit()

    response = await authenticated_client.post(f"/preview/{scroll.url_hash}/confirm")
    assert response.status_code in [200, 303]

    mock_email_service.send_admin_publish_notification.assert_called_once()
    call_args = mock_email_service.send_admin_publish_notification.call_args
    assert call_args.kwargs["user_email"] == test_user.email
    assert call_args.kwargs["display_name"] == test_user.display_name
    assert call_args.kwargs["scroll_title"] == "Test Paper for Notification"
    assert call_args.kwargs["url_hash"] == "notify123"
    assert "/scroll/notify123" in call_args.kwargs["scroll_url"]


@pytest.mark.asyncio
@patch("app.routes.scrolls.get_email_service")
async def test_publish_works_when_email_service_unavailable(
    mock_get_email_service, authenticated_client, test_db: AsyncSession, test_user, test_subject
):
    """Test that publishing works even when email service is not configured."""
    mock_get_email_service.return_value = None

    scroll = Scroll(
        user_id=test_user.id,
        title="Test Paper No Email",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Test</h1></body></html>",
        license="cc-by-4.0",
        content_hash="noemail123",
        url_hash="noemail123",
        status="preview",
    )
    test_db.add(scroll)
    await test_db.commit()

    response = await authenticated_client.post(f"/preview/{scroll.url_hash}/confirm")
    assert response.status_code in [200, 303]

    await test_db.refresh(scroll)
    assert scroll.status == "published"


@pytest.mark.asyncio
@patch("app.routes.scrolls.get_email_service")
async def test_admin_notification_failure_does_not_block_publish(
    mock_get_email_service, authenticated_client, test_db: AsyncSession, test_user, test_subject
):
    """Test that publishing succeeds even if admin notification fails."""
    mock_email_service = AsyncMock()
    mock_email_service.send_admin_publish_notification = AsyncMock(return_value=False)
    mock_get_email_service.return_value = mock_email_service

    scroll = Scroll(
        user_id=test_user.id,
        title="Test Paper Email Fail",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Test</h1></body></html>",
        license="cc-by-4.0",
        content_hash="failmail123",
        url_hash="failmail123",
        status="preview",
    )
    test_db.add(scroll)
    await test_db.commit()

    response = await authenticated_client.post(f"/preview/{scroll.url_hash}/confirm")
    assert response.status_code in [200, 303]

    await test_db.refresh(scroll)
    assert scroll.status == "published"
