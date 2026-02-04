import os
from typing import Optional

from pydantic import BaseModel
import resend
import sentry_sdk

from app.logging_config import get_logger

from .templates import (
    get_admin_publish_notification,
    get_admin_signup_notification,
    get_password_reset_email,
    get_verification_email,
)


class EmailConfig(BaseModel):
    resend_api_key: str
    from_email: str = "noreply@updates.aris.pub"
    base_url: str = "http://localhost:8000"
    admin_email: Optional[str] = None


class EmailService:
    def __init__(self, config: EmailConfig):
        self.config = config
        resend.api_key = config.resend_api_key

    def _send_email(self, params: dict, email_type: str, recipient: str) -> bool:
        """Internal helper to send email with proper error handling.

        Args:
            params: Resend email parameters
            email_type: Type of email for logging (e.g., "verification", "password reset")
            recipient: Recipient email address

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            resend.Emails.send(params)  # type: ignore
            get_logger().info(f"Sent {email_type} email to {recipient}")
            return True
        except Exception as e:
            get_logger().error(f"Failed to send {email_type} email to {recipient}: {str(e)}")
            sentry_sdk.capture_exception(e)
            return False

    async def send_verification_email(self, to_email: str, name: str, token: str) -> bool:
        """Send email verification email.

        Args:
            to_email: Recipient email address
            name: User's display name
            token: Verification token to include in link

        Returns:
            True if email sent successfully, False otherwise
        """
        html_content, text_content = get_verification_email(
            name=name, token=token, base_url=self.config.base_url
        )

        params = {
            "from": f"Scroll Press <{self.config.from_email}>",
            "to": [to_email],
            "subject": "Verify your Scroll Press email address",
            "html": html_content,
            "text": text_content,
        }

        return self._send_email(params, "verification", to_email)

    async def send_password_reset_email(self, to_email: str, name: str, token: str) -> bool:
        """Send password reset email.

        Args:
            to_email: Recipient email address
            name: User's display name
            token: Password reset token to include in link

        Returns:
            True if email sent successfully, False otherwise
        """
        html_content, text_content = get_password_reset_email(
            name=name, token=token, base_url=self.config.base_url
        )

        params = {
            "from": f"Scroll Press <{self.config.from_email}>",
            "to": [to_email],
            "subject": "Reset your Scroll Press password",
            "html": html_content,
            "text": text_content,
        }

        return self._send_email(params, "password reset", to_email)

    async def send_admin_signup_notification(
        self, user_email: str, display_name: str, user_id: str
    ) -> bool:
        """Send admin notification for new user signup.

        Args:
            user_email: New user's email address
            display_name: New user's display name
            user_id: New user's ID

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.config.admin_email:
            return False

        html_content, text_content = get_admin_signup_notification(
            user_email=user_email, display_name=display_name, user_id=user_id
        )

        params = {
            "from": f"Scroll Press <{self.config.from_email}>",
            "to": [self.config.admin_email],
            "subject": f"New Signup: {display_name}",
            "html": html_content,
            "text": text_content,
        }

        return self._send_email(params, "admin signup notification", self.config.admin_email)

    async def send_admin_publish_notification(
        self, user_email: str, display_name: str, scroll_title: str, scroll_url: str, url_hash: str
    ) -> bool:
        """Send admin notification for new paper publish.

        Args:
            user_email: User's email address
            display_name: User's display name
            scroll_title: Title of the published scroll
            scroll_url: Full URL to the published scroll
            url_hash: URL hash of the scroll

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.config.admin_email:
            return False

        html_content, text_content = get_admin_publish_notification(
            user_email=user_email,
            display_name=display_name,
            scroll_title=scroll_title,
            scroll_url=scroll_url,
            url_hash=url_hash,
        )

        params = {
            "from": f"Scroll Press <{self.config.from_email}>",
            "to": [self.config.admin_email],
            "subject": f"New Publication: {scroll_title[:50]}",
            "html": html_content,
            "text": text_content,
        }

        return self._send_email(params, "admin publish notification", self.config.admin_email)


def get_email_service() -> Optional[EmailService]:
    """Get configured email service instance.

    Returns:
        EmailService if properly configured, None otherwise
    """
    resend_api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("FROM_EMAIL", "noreply@updates.aris.pub")
    admin_email = os.getenv("ADMIN_EMAIL")

    # Use PORT env var for default BASE_URL
    port = os.getenv("PORT", "8000")
    base_url = os.getenv("BASE_URL", f"https://127.0.0.1:{port}")

    # Don't initialize service if API key is missing or placeholder
    if not resend_api_key or resend_api_key == "your_resend_api_key_here":
        return None

    config = EmailConfig(
        resend_api_key=resend_api_key,
        from_email=from_email,
        base_url=base_url,
        admin_email=admin_email,
    )

    return EmailService(config)
