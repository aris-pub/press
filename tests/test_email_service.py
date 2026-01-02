from unittest.mock import patch

import pytest

from app.emails.service import EmailConfig, EmailService, get_email_service


def test_email_service_initialization():
    """Test that email service can be initialized with config."""
    config = EmailConfig(
        resend_api_key="test_api_key",
        from_email="test@example.com",
        base_url="http://localhost:8000",
    )
    service = EmailService(config)

    assert service.config.resend_api_key == "test_api_key"
    assert service.config.from_email == "test@example.com"
    assert service.config.base_url == "http://localhost:8000"


@pytest.mark.asyncio
@patch("resend.Emails.send")
async def test_send_verification_email_composes_message(mock_send):
    """Test that verification email is composed correctly."""
    config = EmailConfig(
        resend_api_key="test_api_key",
        from_email="noreply@example.com",
        base_url="http://localhost:8000",
    )
    service = EmailService(config)

    result = await service.send_verification_email(
        to_email="user@example.com", name="Test User", token="test_token_123"
    )

    assert result is True
    mock_send.assert_called_once()

    # Check the email params
    call_args = mock_send.call_args[0][0]
    assert call_args["to"] == ["user@example.com"]
    assert call_args["from"] == "Scroll Press <noreply@example.com>"
    assert (
        "verify" in call_args["subject"].lower() or "verification" in call_args["subject"].lower()
    )
    assert "html" in call_args
    assert "text" in call_args


@pytest.mark.asyncio
@patch("resend.Emails.send")
async def test_send_password_reset_email_composes_message(mock_send):
    """Test that password reset email is composed correctly."""
    config = EmailConfig(
        resend_api_key="test_api_key",
        from_email="noreply@example.com",
        base_url="http://localhost:8000",
    )
    service = EmailService(config)

    result = await service.send_password_reset_email(
        to_email="user@example.com", name="Test User", token="reset_token_456"
    )

    assert result is True
    mock_send.assert_called_once()

    # Check the email params
    call_args = mock_send.call_args[0][0]
    assert call_args["to"] == ["user@example.com"]
    assert call_args["from"] == "Scroll Press <noreply@example.com>"
    assert "password" in call_args["subject"].lower() and "reset" in call_args["subject"].lower()
    assert "html" in call_args
    assert "text" in call_args


@pytest.mark.asyncio
@patch("resend.Emails.send")
async def test_verification_link_includes_token(mock_send):
    """Test that verification email includes token in link."""
    config = EmailConfig(
        resend_api_key="test_api_key",
        from_email="noreply@example.com",
        base_url="http://localhost:8000",
    )
    service = EmailService(config)

    token = "my_secret_token_123"
    await service.send_verification_email(
        to_email="user@example.com", name="Test User", token=token
    )

    call_args = mock_send.call_args[0][0]
    html_content = call_args["html"]
    text_content = call_args["text"]

    # Both HTML and text should contain the verification link with token
    expected_link = f"http://localhost:8000/verify-email?token={token}"
    assert expected_link in html_content
    assert expected_link in text_content


@pytest.mark.asyncio
@patch("resend.Emails.send")
async def test_reset_link_includes_token(mock_send):
    """Test that password reset email includes token in link."""
    config = EmailConfig(
        resend_api_key="test_api_key",
        from_email="noreply@example.com",
        base_url="http://localhost:8000",
    )
    service = EmailService(config)

    token = "my_reset_token_456"
    await service.send_password_reset_email(
        to_email="user@example.com", name="Test User", token=token
    )

    call_args = mock_send.call_args[0][0]
    html_content = call_args["html"]
    text_content = call_args["text"]

    # Both HTML and text should contain the reset link with token
    expected_link = f"http://localhost:8000/reset-password?token={token}"
    assert expected_link in html_content
    assert expected_link in text_content


@pytest.mark.asyncio
@patch("resend.Emails.send")
async def test_email_from_address_configuration(mock_send):
    """Test that configured from_email is used."""
    config = EmailConfig(
        resend_api_key="test_api_key",
        from_email="custom@domain.com",
        base_url="http://localhost:8000",
    )
    service = EmailService(config)

    await service.send_verification_email(
        to_email="user@example.com", name="Test User", token="token_123"
    )

    call_args = mock_send.call_args[0][0]
    assert call_args["from"] == "Scroll Press <custom@domain.com>"


@pytest.mark.asyncio
@patch("resend.Emails.send")
async def test_email_html_and_plain_text(mock_send):
    """Test that emails include both HTML and plain text versions."""
    config = EmailConfig(
        resend_api_key="test_api_key",
        from_email="noreply@example.com",
        base_url="http://localhost:8000",
    )
    service = EmailService(config)

    await service.send_verification_email(
        to_email="user@example.com", name="Test User", token="token_123"
    )

    call_args = mock_send.call_args[0][0]
    assert "html" in call_args
    assert "text" in call_args
    assert len(call_args["html"]) > 0
    assert len(call_args["text"]) > 0
    # HTML should have tags
    assert "<" in call_args["html"] and ">" in call_args["html"]
    # Text should not have HTML tags
    assert "<html" not in call_args["text"].lower()


@pytest.mark.asyncio
@patch("resend.Emails.send")
async def test_email_service_api_error_handling(mock_send):
    """Test that API errors are handled gracefully."""
    mock_send.side_effect = Exception("Resend API error")

    config = EmailConfig(
        resend_api_key="test_api_key",
        from_email="noreply@example.com",
        base_url="http://localhost:8000",
    )
    service = EmailService(config)

    # Should return False on error, not raise exception
    result = await service.send_verification_email(
        to_email="user@example.com", name="Test User", token="token_123"
    )

    assert result is False


def test_get_email_service_returns_none_if_not_configured():
    """Test that get_email_service returns None when not configured."""
    # Test with missing API key
    with patch.dict("os.environ", {}, clear=True):
        service = get_email_service()
        assert service is None

    # Test with placeholder API key
    with patch.dict("os.environ", {"RESEND_API_KEY": "your_resend_api_key_here"}):
        service = get_email_service()
        assert service is None


def test_get_email_service_returns_service_when_configured():
    """Test that get_email_service returns service when properly configured."""
    with patch.dict(
        "os.environ",
        {
            "RESEND_API_KEY": "real_api_key",
            "FROM_EMAIL": "test@example.com",
            "BASE_URL": "http://localhost:8000",
        },
    ):
        service = get_email_service()
        assert service is not None
        assert isinstance(service, EmailService)
        assert service.config.resend_api_key == "real_api_key"
