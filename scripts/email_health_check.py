#!/usr/bin/env python3
"""Post-deployment email health check.

Sends a test email using production configuration to verify:
- Resend API key is valid
- FROM_EMAIL domain is properly configured
- BASE_URL is correct for email links
- Email delivery is working

This script should be run after each production deployment to catch
email configuration issues immediately.
"""

import asyncio
from datetime import UTC, datetime
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.emails.service import get_email_service


async def main():
    """Send test email to admin using production configuration."""
    print("🔍 Email Health Check - Production Configuration")
    print("=" * 60)

    # Check required environment variables
    resend_api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("FROM_EMAIL", "noreply@updates.aris.pub")
    base_url = os.getenv("BASE_URL")
    admin_email = os.getenv("ADMIN_EMAIL")

    if not resend_api_key or resend_api_key == "your_resend_api_key_here":
        print("❌ RESEND_API_KEY not configured")
        sys.exit(1)

    if not admin_email:
        print("❌ ADMIN_EMAIL not configured")
        sys.exit(1)

    print(f"📧 FROM_EMAIL: {from_email}")
    print(f"🌐 BASE_URL: {base_url}")
    print(f"👤 ADMIN_EMAIL: {admin_email}")
    print()

    # Get email service
    email_service = get_email_service()
    if not email_service:
        print("❌ Email service not configured")
        sys.exit(1)

    # Send test email
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    environment = os.getenv("ENVIRONMENT", "unknown")

    print("📨 Sending test email...")

    html_content = f"""
    <h2>Email Health Check - PASSED</h2>
    <p>This is an automated health check email sent after deployment.</p>

    <h3>Configuration:</h3>
    <ul>
        <li><strong>Environment:</strong> {environment}</li>
        <li><strong>Base URL:</strong> {base_url}</li>
        <li><strong>From Email:</strong> {from_email}</li>
        <li><strong>Timestamp:</strong> {timestamp}</li>
    </ul>

    <p>If you received this email, your email service is configured correctly!</p>

    <hr>
    <p><small>This email was sent by the post-deployment health check script.</small></p>
    """

    text_content = f"""
Email Health Check - PASSED

This is an automated health check email sent after deployment.

Configuration:
- Environment: {environment}
- Base URL: {base_url}
- From Email: {from_email}
- Timestamp: {timestamp}

If you received this email, your email service is configured correctly!

---
This email was sent by the post-deployment health check script.
    """.strip()

    try:
        params = {
            "from": f"Scroll Press Health Check <{from_email}>",
            "to": [admin_email],
            "subject": f"✅ Email Health Check - {environment.upper()}",
            "html": html_content,
            "text": text_content,
        }

        success = email_service._send_email(params, "health check", admin_email)

        if success:
            print(f"✅ Test email sent successfully to {admin_email}")
            print()
            print("📬 Please check your inbox to confirm delivery")
            sys.exit(0)
        else:
            print(f"❌ Failed to send test email to {admin_email}")
            print("   Check logs for details")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Error sending test email: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
