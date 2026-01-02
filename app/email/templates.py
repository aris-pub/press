def get_verification_email(name: str, token: str, base_url: str) -> tuple[str, str]:
    """Generate email verification email content.

    Args:
        name: User's display name
        token: Verification token to include in link
        base_url: Base URL for the application

    Returns:
        Tuple of (html_content, text_content)
    """
    verification_link = f"{base_url}/verify-email?token={token}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verify your Scroll Press account</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #ef4444; margin: 0;">Welcome to Scroll Press!</h1>
            <p style="color: #6b7280; margin: 5px 0 0 0;">Verify your email to get started</p>
        </div>

        <div style="background: #f8fafc; border-radius: 12px; padding: 30px; margin-bottom: 30px; border-left: 4px solid #ef4444;">
            <h2 style="margin-top: 0; color: #1f2937;">Hi {name} 👋</h2>
            <p style="font-size: 16px; margin: 0 0 20px 0;">Thanks for joining Scroll Press! Please verify your email address to start uploading and sharing your research manuscripts.</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{verification_link}" style="background: #ef4444; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">Verify Email Address</a>
            </div>

            <p style="font-size: 14px; color: #6b7280; margin: 20px 0 0 0;">
                Or copy and paste this link into your browser:<br>
                <a href="{verification_link}" style="color: #ef4444; word-break: break-all;">{verification_link}</a>
            </p>
        </div>

        <div style="text-align: center; color: #6b7280; font-size: 14px; border-top: 1px solid #e5e7eb; padding-top: 20px;">
            <p>If you didn't create an account with Scroll Press, you can safely ignore this email.</p>
            <p style="margin-top: 15px; font-size: 12px;">
                Scroll Press - HTML-native preprint server for modern research
            </p>
        </div>
    </body>
    </html>
    """

    text_content = f"""
Welcome to Scroll Press!

Hi {name} 👋

Thanks for joining Scroll Press! Please verify your email address to start uploading and sharing your research manuscripts.

Verify your email by clicking this link:
{verification_link}

If you didn't create an account with Scroll Press, you can safely ignore this email.

---
Scroll Press - HTML-native preprint server for modern research
    """

    return html_content, text_content


def get_password_reset_email(name: str, token: str, base_url: str) -> tuple[str, str]:
    """Generate password reset email content.

    Args:
        name: User's display name
        token: Reset token to include in link
        base_url: Base URL for the application

    Returns:
        Tuple of (html_content, text_content)
    """
    reset_link = f"{base_url}/reset-password?token={token}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reset your Scroll Press password</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #ef4444; margin: 0;">Reset Your Password</h1>
            <p style="color: #6b7280; margin: 5px 0 0 0;">Scroll Press</p>
        </div>

        <div style="background: #f8fafc; border-radius: 12px; padding: 30px; margin-bottom: 30px; border-left: 4px solid #ef4444;">
            <h2 style="margin-top: 0; color: #1f2937;">Hi {name},</h2>
            <p style="font-size: 16px; margin: 0 0 20px 0;">We received a request to reset your password. Click the button below to create a new password:</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_link}" style="background: #ef4444; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">Reset Password</a>
            </div>

            <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 15px; margin: 20px 0;">
                <p style="margin: 0; font-size: 14px; color: #856404;">
                    ⚠️ <strong>Security notice:</strong> This link expires in 1 hour. If you didn't request a password reset, you can safely ignore this email.
                </p>
            </div>

            <p style="font-size: 14px; color: #6b7280; margin: 20px 0 0 0;">
                Or copy and paste this link into your browser:<br>
                <a href="{reset_link}" style="color: #ef4444; word-break: break-all;">{reset_link}</a>
            </p>
        </div>

        <div style="text-align: center; color: #6b7280; font-size: 14px; border-top: 1px solid #e5e7eb; padding-top: 20px;">
            <p>If you're having trouble, reply to this email for support.</p>
            <p style="margin-top: 15px; font-size: 12px;">
                Scroll Press - HTML-native preprint server for modern research
            </p>
        </div>
    </body>
    </html>
    """

    text_content = f"""
Reset Your Password
Scroll Press

Hi {name},

We received a request to reset your password. Click the link below to create a new password:

{reset_link}

⚠️ Security notice: This link expires in 1 hour. If you didn't request a password reset, you can safely ignore this email.

If you're having trouble, reply to this email for support.

---
Scroll Press - HTML-native preprint server for modern research
    """

    return html_content, text_content
