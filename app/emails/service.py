import os
from typing import Optional

from pydantic import BaseModel
import resend

from .templates import get_password_reset_email, get_verification_email


class EmailConfig(BaseModel):
    resend_api_key: str
    from_email: str = "noreply@updates.aris.pub"
    base_url: str = "http://localhost:8000"


class EmailService:
    def __init__(self, config: EmailConfig):
        self.config = config
        resend.api_key = config.resend_api_key

    async def send_verification_email(self, to_email: str, name: str, token: str) -> bool:
        """Send email verification email.

        Args:
            to_email: Recipient email address
            name: User's display name
            token: Verification token to include in link

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
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

            resend.Emails.send(params)  # type: ignore
            return True

        except Exception as e:
            # Log error in production
            print(f"Failed to send verification email to {to_email}: {str(e)}")
            return False

    async def send_password_reset_email(self, to_email: str, name: str, token: str) -> bool:
        """Send password reset email.

        Args:
            to_email: Recipient email address
            name: User's display name
            token: Password reset token to include in link

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
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

            resend.Emails.send(params)  # type: ignore
            return True

        except Exception as e:
            # Log error in production
            print(f"Failed to send password reset email to {to_email}: {str(e)}")
            return False


def get_email_service() -> Optional[EmailService]:
    """Get configured email service instance.

    Returns:
        EmailService if properly configured, None otherwise
    """
    resend_api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("FROM_EMAIL", "noreply@updates.aris.pub")

    # Use PORT env var for default BASE_URL
    port = os.getenv("PORT", "8000")
    base_url = os.getenv("BASE_URL", f"https://127.0.0.1:{port}")

    # Don't initialize service if API key is missing or placeholder
    if not resend_api_key or resend_api_key == "your_resend_api_key_here":
        return None

    config = EmailConfig(resend_api_key=resend_api_key, from_email=from_email, base_url=base_url)

    return EmailService(config)
