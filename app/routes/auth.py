"""Authentication routes for registration, login, and logout."""

from datetime import UTC, datetime
import os
import re
import time

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import httpx
import sentry_sdk
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.csrf import get_csrf_token
from app.auth.session import create_session, delete_session, get_current_user_from_session
from app.auth.tokens import (
    create_password_reset_token,
    create_verification_token,
    invalidate_user_tokens,
    validate_token,
)
from app.auth.utils import get_password_hash, verify_password
from app.database import get_db
from app.emails.service import get_email_service
from app.logging_config import get_logger, log_auth_event, log_error, log_request
from app.models.session import Session
from app.models.token import Token
from app.models.user import User
from app.templates_config import templates

router = APIRouter()

IS_PRODUCTION = os.getenv("ENVIRONMENT") == "production"
IS_E2E_TESTING = os.getenv("E2E_TESTING", "").lower() in ("true", "1", "yes")

TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")
TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "")

SIGNUP_RATE_LIMIT = 5
SIGNUP_RATE_WINDOW = 3600  # 1 hour in seconds
_signup_timestamps: dict[str, list[float]] = {}


def _check_signup_rate_limit(ip: str) -> bool:
    """Return True if the IP is within rate limits, False if exceeded."""
    now = time.monotonic()
    timestamps = _signup_timestamps.get(ip, [])
    timestamps = [t for t in timestamps if now - t < SIGNUP_RATE_WINDOW]
    _signup_timestamps[ip] = timestamps
    return len(timestamps) < SIGNUP_RATE_LIMIT


def _record_signup(ip: str) -> None:
    _signup_timestamps.setdefault(ip, []).append(time.monotonic())


async def _verify_turnstile(token: str, remote_ip: str) -> bool:
    """Verify a Turnstile token with Cloudflare. Returns True if valid or if Turnstile is not configured."""
    if not TURNSTILE_SECRET_KEY:
        return True

    # If no token was submitted, the widget likely failed to render (e.g. Cloudflare
    # propagation delay). Fall through to other defenses (rate limiter) rather than
    # blocking legitimate users.
    if not token:
        get_logger().warning(f"Turnstile token missing from {remote_ip} - widget may not have rendered")
        return True

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": TURNSTILE_SECRET_KEY, "response": token, "remoteip": remote_ip},
        )
        result = resp.json()
        return result.get("success", False)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the user login page.

    Shows the login form to anonymous users. Authenticated users are automatically
    redirected to the homepage.

    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if current_user:
        get_logger().info(f"Authenticated user {current_user.id} redirected from login page")
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse(request, "auth/login.html", {"current_user": current_user})


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    """Log out the current user and redirect to homepage.

    Destroys the user session and clears the session cookie.

    """
    log_request(request)
    session_id = request.cookies.get("session_id")
    if session_id:
        await delete_session(db, session_id)
        get_logger().info(f"User session {session_id} destroyed during logout")

    # Clear the session cookie in the redirect response
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session_id")

    return response


@router.get("/csrf-token")
async def get_csrf_token_endpoint(request: Request, db: AsyncSession = Depends(get_db)):
    """Get CSRF token for the current session.

    Returns the CSRF token needed for state-changing requests (DELETE, POST, etc.).
    Requires an active session.

    Returns:
        JSONResponse: CSRF token for the current session

    Raises:
        HTTPException: 401 if no active session exists
    """
    # Validate session exists and is active
    current_user = await get_current_user_from_session(request, db)
    if not current_user:
        return JSONResponse({"error": "No active session"}, status_code=401)

    session_id = request.cookies.get("session_id")
    token = await get_csrf_token(session_id)

    return JSONResponse({"csrf_token": token})


@router.delete("/account")
async def delete_account(request: Request, db: AsyncSession = Depends(get_db)):
    """Delete the current user's account with proper auth guards.

    This endpoint safely deletes a user's account while preserving their published
    scrolls for the scholarly record. Only authenticated users can delete their own
    accounts. The deletion removes:
    - User profile and login credentials
    - All user sessions
    - Personal account data

    Published scrolls remain in the database to maintain citation integrity and
    scholarly record, but are no longer associated with the user account.

    Returns:
        JSONResponse: Success message confirming account deletion

    Raises:
        HTTPException: 401 if user is not authenticated
        HTTPException: 500 for database errors
    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    # Authentication guard - only logged in users can delete accounts
    if not current_user:
        log_auth_event(
            "delete_account",
            "anonymous",
            False,
            request,
            error_message="Unauthenticated deletion attempt",
        )
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = current_user.id
    user_email = current_user.email

    try:
        sentry_sdk.set_tag("operation", "account_deletion")
        sentry_sdk.set_user({"id": str(user_id), "email": user_email})
        log_auth_event("delete_account", user_email, True, request, user_id=str(user_id))

        # Delete all user sessions first (including current session)
        await db.execute(delete(Session).where(Session.user_id == user_id))

        # Delete all user tokens (verification and password reset)
        from app.models.token import Token

        await db.execute(delete(Token).where(Token.user_id == user_id))

        # Delete the user account (scrolls will remain due to ON DELETE SET NULL or similar)
        # Note: The scrolls table should have a foreign key constraint that either:
        # 1. Sets user_id to NULL when user is deleted (preserves scrolls)
        # 2. Or we handle this manually by updating scrolls first

        # Update scrolls to remove user association (preserve for scholarly record)
        from app.models.scroll import Scroll

        await db.execute(
            Scroll.__table__.update().where(Scroll.user_id == user_id).values(user_id=None)
        )

        # Now delete the user
        await db.execute(delete(User).where(User.id == user_id))

        # Commit all changes
        await db.commit()

        log_auth_event("delete_account", user_email, True, request, user_id=str(user_id))

        get_logger().info(f"Account deleted successfully for user {user_id} ({user_email})")

        return JSONResponse(content={"success": True, "message": "Account deleted successfully"})

    except Exception as e:
        # Rollback transaction on error
        await db.rollback()

        log_auth_event(
            "delete_account",
            user_email,
            False,
            request,
            user_id=str(user_id),
            error_message=str(e),
        )
        log_error(e, request, user_id=str(user_id), context="account_deletion")

        get_logger().error(f"Account deletion failed for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Account deletion failed")


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the user registration page.

    Shows the registration form to anonymous users. Logged-in users are automatically
    redirected to the homepage to prevent duplicate registrations.

    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if current_user:
        get_logger().info(f"Authenticated user {current_user.id} redirected from register page")
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse(
        request, "auth/register.html", {"current_user": current_user}
    )


# Form submission handlers
@router.post("/register-form", response_class=HTMLResponse)
async def register_form(
    request: Request,
    email: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(None),
    agree_terms: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Process user registration form submission via HTMX.

    Validates user input, checks for existing accounts, creates a new user account,
    and automatically logs them in with a session cookie. Uses HTMX for seamless
    form submission without page refreshes.

    Args:
        request: The HTTP request object for HTMX responses
        email: User's email address (must be unique, case-insensitive)
        display_name: User's display name for the platform
        password: User's password (will be hashed before storage)
        db: Database session dependency for user operations

    Returns:
        HTMLResponse: Success partial with auto-login or error form with validation messages

    Raises:
        ValueError: For validation errors (empty fields, duplicate email)
        Exception: For database or unexpected errors during registration
    """
    client_ip = request.client.host if request.client else "unknown"

    # Signup rate limit check (before any other validation)
    if not _check_signup_rate_limit(client_ip):
        log_auth_event(
            "register", email, False, request, error_message="Signup rate limit exceeded"
        )
        return templates.TemplateResponse(
            request,
            "auth/partials/register_form.html",
            {
                "errors": ["Too many signup attempts. Please try again later."],
                "form_data": {
                    "email": email,
                    "display_name": display_name,
                    "confirm_password": confirm_password,
                    "agree_terms": agree_terms,
                },
            },
            status_code=422,
        )

    # Turnstile verification
    form_data_raw = await request.form()
    turnstile_token = form_data_raw.get("cf-turnstile-response", "")
    if not await _verify_turnstile(turnstile_token, client_ip):
        log_auth_event(
            "register", email, False, request, error_message="Turnstile verification failed"
        )
        return templates.TemplateResponse(
            request,
            "auth/partials/register_form.html",
            {
                "errors": ["CAPTCHA verification failed. Please try again."],
                "form_data": {
                    "email": email,
                    "display_name": display_name,
                    "confirm_password": confirm_password,
                    "agree_terms": agree_terms,
                },
            },
            status_code=422,
        )

    try:
        sentry_sdk.set_tag("operation", "user_registration")
        sentry_sdk.set_context("registration", {"email": email, "display_name": display_name})
        log_request(request, extra_data={"email": email, "display_name": display_name})

        # Validate input
        if not email or not email.strip():
            raise ValueError("Email is required")

        # Display name validation
        if not display_name:
            raise ValueError("Display name is required")
        display_name_stripped = display_name.strip()
        if len(display_name_stripped) == 0:
            raise ValueError("Display name cannot be empty")
        if len(display_name_stripped) > 100:
            raise ValueError("Display name must be less than 100 characters")
        if re.search(r"https?://|www\.", display_name_stripped, re.IGNORECASE):
            raise ValueError("Display name cannot contain URLs")
        display_name = display_name_stripped

        # Password validation
        if not password or len(password) < 1:
            raise ValueError("Password is required")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(char.isdigit() for char in password):
            raise ValueError("Password must contain at least one number")
        if not confirm_password:
            raise ValueError("Password confirmation is required")
        if password != confirm_password:
            raise ValueError("Passwords do not match")

        if not agree_terms or agree_terms.lower() != "true":
            raise ValueError("You must agree to the Terms of Service and Privacy Policy")

        # Check if user already exists (case insensitive)
        normalized_email = email.strip().lower()
        result = await db.execute(select(User).where(User.email == normalized_email))
        if result.scalar_one_or_none():
            log_auth_event(
                "register",
                normalized_email,
                False,
                request,
                error_message="Email already registered",
            )
            return templates.TemplateResponse(
                request,
                "auth/partials/register_form.html",
                {
                    "errors": ["Email already registered"],
                    "form_data": {
                        "email": email,
                        "display_name": display_name,
                        "confirm_password": confirm_password,
                        "agree_terms": agree_terms,
                    },
                },
                status_code=422,
            )

        # Create new user
        hashed_password = get_password_hash(password)
        db_user = User(
            email=normalized_email,
            password_hash=hashed_password,
            display_name=display_name.strip(),
        )

        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

        _record_signup(client_ip)

        # Create email verification token
        verification_token = await create_verification_token(db, db_user.id)

        # Send verification email if email service is configured
        email_service = get_email_service()
        if email_service:
            await email_service.send_verification_email(
                to_email=normalized_email, name=db_user.display_name, token=verification_token
            )
            # Send admin notification for new signup
            await email_service.send_admin_signup_notification(
                user_email=normalized_email,
                display_name=db_user.display_name,
                user_id=str(db_user.id),
            )

        # Create session and auto-login user
        session_id = await create_session(db, db_user.id)

        log_auth_event("register", normalized_email, True, request, user_id=str(db_user.id))

        # Return success partial with automatic login
        # Use JavaScript redirect instead of HTMX to avoid nested content bug
        response = templates.TemplateResponse(
            request,
            "auth/partials/success_redirect.html",
            {
                "title": "Account Created!",
                "message": f"Welcome to Scroll Press, {db_user.display_name}! Please check your email to verify your account.",
                "redirect_url": "/",
            },
        )

        # Set session cookie
        response.set_cookie(
            "session_id", session_id, httponly=True, secure=IS_PRODUCTION, samesite="lax"
        )

        return response

    except Exception as e:
        error_message = str(e) if str(e) else "Registration failed. Please try again."
        log_auth_event("register", email, False, request, error_message=error_message)
        log_error(e, request, context="user_registration")
        return templates.TemplateResponse(
            request,
            "auth/partials/register_form.html",
            {
                "errors": [error_message],
                "form_data": {
                    "email": email,
                    "display_name": display_name,
                    "confirm_password": confirm_password,
                    "agree_terms": agree_terms,
                },
            },
            status_code=422,
        )


@router.post("/login-form", response_class=HTMLResponse)
async def login_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Process user login form submission via HTMX.

    Validates credentials, authenticates the user, and creates a session cookie
    for subsequent requests. Uses HTMX for seamless form submission without
    page refreshes.

    Args:
        request: The HTTP request object for HTMX responses
        email: User's email address (case-insensitive lookup)
        password: User's plaintext password for verification
        db: Database session dependency for user lookup

    Returns:
        HTMLResponse: Success partial with session cookie or error form with validation messages

    Raises:
        ValueError: For validation errors (empty fields, invalid credentials)
        Exception: For database or unexpected errors during authentication
    """
    try:
        sentry_sdk.set_tag("operation", "user_login")
        sentry_sdk.set_context("login", {"email": email})
        log_request(request, extra_data={"email": email})

        # Validate input
        if not email or not email.strip():
            raise ValueError("Email is required")
        if not password:
            raise ValueError("Password is required")

        # Get user from database (case insensitive)
        normalized_email = email.strip().lower()
        result = await db.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            log_auth_event(
                "login", normalized_email, False, request, error_message="Invalid credentials"
            )
            return templates.TemplateResponse(
                request,
                "auth/partials/login_form.html",
                {
                    "errors": ["Incorrect email or password"],
                    "form_data": {"email": email},
                },
                status_code=422,
            )

        # Create session
        session_id = await create_session(db, user.id)

        log_auth_event("login", normalized_email, True, request, user_id=str(user.id))

        # Return success partial
        response = templates.TemplateResponse(
            request,
            "auth/partials/success.html",
            {
                "title": "Welcome Back!",
                "message": f"Successfully signed in as {user.display_name}",
                "action_text": "Go to Dashboard",
                "action_url": "/dashboard",
            },
        )

        # Set session cookie
        response.set_cookie(
            "session_id", session_id, httponly=True, secure=IS_PRODUCTION, samesite="lax"
        )

        return response

    except Exception as e:
        error_message = str(e) if str(e) else "Login failed. Please try again."
        log_auth_event("login", email, False, request, error_message=error_message)
        log_error(e, request, context="user_login")
        return templates.TemplateResponse(
            request,
            "auth/partials/login_form.html",
            {"errors": [error_message], "form_data": {"email": email}},
            status_code=422,
        )


@router.get("/verify-email", response_class=HTMLResponse)
async def verify_email(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Verify user's email address using token from email."""
    log_request(request)

    try:
        # Validate token
        user = await validate_token(db, token, "email_verification")

        if not user:
            get_logger().warning("Invalid or expired verification token")
            return templates.TemplateResponse(
                request,
                "auth/verify_email.html",
                {
                    "success": False,
                    "message": "Invalid or expired verification link. Please request a new one.",
                    "current_user": None,
                },
            )

        # Mark email as verified
        user.email_verified = True
        await db.commit()

        # Mark token as used
        await db.execute(
            update(Token)
            .where(Token.user_id == user.id)
            .where(Token.token_type == "email_verification")
            .where(Token.used_at.is_(None))
            .values(used_at=datetime.now(UTC))
        )
        await db.commit()

        get_logger().info(f"Email verified for user {user.id}")

        # Rotate session for security (privilege escalation from unverified to verified)
        old_session_id = request.cookies.get("session_id")
        if old_session_id:
            from app.auth.session import rotate_session

            new_session_id = await rotate_session(db, old_session_id)

            # Return response with new session cookie
            response = templates.TemplateResponse(
                request,
                "auth/verify_email.html",
                {
                    "success": True,
                    "message": "Email verified successfully! You can now access all features.",
                    "current_user": user,
                },
            )
            response.set_cookie(
                key="session_id",
                value=new_session_id,
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=86400,  # 24 hours
            )
            return response

        return templates.TemplateResponse(
            request,
            "auth/verify_email.html",
            {
                "success": True,
                "message": "Email verified successfully! You can now access all features.",
                "current_user": user,
            },
        )

    except Exception as e:
        log_error(e, request, context="email_verification")
        return templates.TemplateResponse(
            request,
            "auth/verify_email.html",
            {
                "success": False,
                "message": "An error occurred during verification. Please try again.",
                "current_user": None,
            },
        )


@router.get("/resend-verification", response_class=HTMLResponse)
async def resend_verification_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Show resend verification page."""
    current_user = await get_current_user_from_session(request, db)

    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    if current_user.email_verified:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        request, "auth/resend_verification.html", {"current_user": current_user}
    )


@router.post("/resend-verification", response_class=HTMLResponse)
async def resend_verification(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Resend email verification to the current user."""
    log_request(request)

    try:
        current_user = await get_current_user_from_session(request, db)

        if not current_user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        if current_user.email_verified:
            return templates.TemplateResponse(
                request,
                "auth/partials/success.html",
                {
                    "title": "Already Verified",
                    "message": "Your email is already verified!",
                    "action_text": "Go to Dashboard",
                    "action_url": "/dashboard",
                },
            )

        # Invalidate old verification tokens
        await invalidate_user_tokens(db, current_user.id, "email_verification")

        # Create new verification token
        verification_token = await create_verification_token(db, current_user.id)

        # Send verification email
        email_service = get_email_service()
        if email_service:
            await email_service.send_verification_email(
                to_email=current_user.email,
                name=current_user.display_name,
                token=verification_token,
            )

        # Show success message briefly, then redirect to homepage
        # Use JavaScript redirect instead of HTMX to avoid nested content bug
        return templates.TemplateResponse(
            request,
            "auth/partials/success_redirect.html",
            {
                "title": "Email Sent",
                "message": "Verification email sent! Please check your inbox.",
                "redirect_url": "/",
            },
        )

    except Exception as e:
        log_error(e, request, context="resend_verification")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to resend verification email"},
        )


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Display the forgot password request form."""
    log_request(request)
    return templates.TemplateResponse(request, "auth/forgot_password.html", {})


@router.post("/forgot-password-form", response_class=HTMLResponse)
async def forgot_password_form(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Process forgot password request and send reset email."""
    log_request(request, {"email": email})

    try:
        # Normalize email
        normalized_email = email.strip().lower()

        # Look up user by email
        result = await db.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()

        # Always return success to avoid revealing if email exists (security best practice)
        # But only send email if user exists
        if user:
            # Invalidate old password reset tokens
            await invalidate_user_tokens(db, user.id, "password_reset")

            # Create new password reset token (expires in 1 hour)
            reset_token = await create_password_reset_token(db, user.id)

            # Send password reset email
            email_service = get_email_service()
            if email_service:
                await email_service.send_password_reset_email(
                    to_email=normalized_email, name=user.display_name, token=reset_token
                )
                get_logger().info(f"Password reset email sent to {normalized_email}")

        # Always show success message (even if email doesn't exist)
        return templates.TemplateResponse(
            request,
            "auth/forgot_password.html",
            {
                "success": True,
                "message": "If an account exists with that email, you will receive password reset instructions shortly.",
            },
        )

    except Exception as e:
        log_error(e, request, context="forgot_password")
        return templates.TemplateResponse(
            request,
            "auth/forgot_password.html",
            {
                "error": "An error occurred. Please try again.",
            },
        )


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Display the password reset form if token is valid."""
    log_request(request)

    try:
        # Validate token
        user = await validate_token(db, token, "password_reset")

        if not user:
            get_logger().warning("Invalid or expired password reset token")
            return templates.TemplateResponse(
                request,
                "auth/reset_password.html",
                {
                    "error": True,
                    "message": "Invalid or expired reset link. Please request a new one.",
                    "token": None,
                },
            )

        # Token is valid, show reset form
        return templates.TemplateResponse(
            request,
            "auth/reset_password.html",
            {
                "token": token,
                "error": False,
            },
        )

    except Exception as e:
        log_error(e, request, context="reset_password_page")
        return templates.TemplateResponse(
            request,
            "auth/reset_password.html",
            {
                "error": True,
                "message": "An error occurred. Please try again.",
                "token": None,
            },
        )


@router.post("/reset-password-form", response_class=HTMLResponse)
async def reset_password_form(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Process password reset form submission."""
    log_request(request)

    try:
        # Validate token
        user = await validate_token(db, token, "password_reset")

        if not user:
            get_logger().warning("Invalid or expired password reset token")
            raise HTTPException(status_code=400, detail="Invalid or expired reset link")

        # Validate password strength
        if len(password) < 8:
            raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
        if not any(char.isdigit() for char in password):
            raise HTTPException(
                status_code=422, detail="Password must contain at least one number"
            )

        # Validate passwords match
        if password != confirm_password:
            raise HTTPException(status_code=422, detail="Passwords do not match")

        # Update password
        user.password_hash = get_password_hash(password)
        await db.commit()

        # Mark token as used
        await db.execute(
            update(Token)
            .where(Token.user_id == user.id)
            .where(Token.token_type == "password_reset")
            .where(Token.used_at.is_(None))
            .values(used_at=datetime.now(UTC))
        )
        await db.commit()

        get_logger().info(f"Password reset successful for user {user.id}")
        log_auth_event(
            "password_reset",
            user.email,
            True,
            request,
            user_id=str(user.id),
        )

        # Auto-login user after successful password reset
        session_id = await create_session(db, user.id)

        response = templates.TemplateResponse(
            request,
            "auth/reset_password.html",
            {
                "success": True,
                "message": "Password reset successful! You are now logged in.",
            },
        )

        # Set session cookie
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=IS_PRODUCTION,
            samesite="lax",
            max_age=86400,  # 24 hours
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        log_error(e, request, context="reset_password")
        log_auth_event(
            "password_reset",
            "unknown",
            False,
            request,
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail="An error occurred during password reset")


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the change password form for authenticated users."""
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    # Get CSRF token for form
    session_id = request.cookies.get("session_id")
    csrf_token = await get_csrf_token(session_id)

    return templates.TemplateResponse(
        request,
        "auth/change_password.html",
        {"current_user": current_user, "csrf_token": csrf_token},
    )


@router.post("/change-password-form", response_class=HTMLResponse)
async def change_password_form(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_new_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Process password change form submission for authenticated users."""
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    # Get CSRF token for error responses
    session_id = request.cookies.get("session_id")
    csrf_token = await get_csrf_token(session_id)

    try:
        # Verify current password
        if not verify_password(current_password, current_user.password_hash):
            return templates.TemplateResponse(
                request,
                "auth/change_password.html",
                {
                    "current_user": current_user,
                    "csrf_token": csrf_token,
                    "error": "Current password is incorrect",
                },
                status_code=422,
            )

        # Validate new password strength
        if len(new_password) < 8:
            return templates.TemplateResponse(
                request,
                "auth/change_password.html",
                {
                    "current_user": current_user,
                    "csrf_token": csrf_token,
                    "error": "New password must be at least 8 characters long",
                },
                status_code=422,
            )

        if not any(char.isdigit() for char in new_password):
            return templates.TemplateResponse(
                request,
                "auth/change_password.html",
                {
                    "current_user": current_user,
                    "csrf_token": csrf_token,
                    "error": "New password must contain at least one number",
                },
                status_code=422,
            )

        # Validate passwords match
        if new_password != confirm_new_password:
            return templates.TemplateResponse(
                request,
                "auth/change_password.html",
                {
                    "current_user": current_user,
                    "csrf_token": csrf_token,
                    "error": "New passwords do not match",
                },
                status_code=422,
            )

        # Check that new password is different from current
        if verify_password(new_password, current_user.password_hash):
            return templates.TemplateResponse(
                request,
                "auth/change_password.html",
                {
                    "current_user": current_user,
                    "csrf_token": csrf_token,
                    "error": "New password must be different from your current password",
                },
                status_code=422,
            )

        # Update password
        current_user.password_hash = get_password_hash(new_password)
        await db.commit()

        get_logger().info(f"Password changed successfully for user {current_user.id}")
        log_auth_event(
            "password_change",
            current_user.email,
            True,
            request,
            user_id=str(current_user.id),
        )

        # Rotate session for security
        old_session_id = request.cookies.get("session_id")
        if old_session_id:
            from app.auth.session import rotate_session

            new_session_id = await rotate_session(db, old_session_id)

            response = templates.TemplateResponse(
                request,
                "auth/change_password.html",
                {
                    "success": True,
                    "message": "Your password has been changed successfully.",
                    "current_user": current_user,
                },
            )
            response.set_cookie(
                key="session_id",
                value=new_session_id,
                httponly=True,
                secure=IS_PRODUCTION,
                samesite="lax",
                max_age=86400,
            )
            return response

        return templates.TemplateResponse(
            request,
            "auth/change_password.html",
            {
                "success": True,
                "message": "Your password has been changed successfully.",
                "current_user": current_user,
            },
        )

    except Exception as e:
        log_error(e, request, context="change_password")
        log_auth_event(
            "password_change",
            current_user.email,
            False,
            request,
            user_id=str(current_user.id),
            error_message=str(e),
        )
        return templates.TemplateResponse(
            request,
            "auth/change_password.html",
            {
                "current_user": current_user,
                "csrf_token": csrf_token,
                "error": "An error occurred while changing your password. Please try again.",
            },
            status_code=500,
        )


@router.get("/user/export-data")
async def export_user_data(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Export all user data in JSON format (GDPR Article 20 compliance).

    Returns all personal data associated with the authenticated user:
    - User profile information
    - All scrolls (published and drafts)
    - Active sessions

    Returns:
        JSONResponse with user data in structured format
    """
    current_user = await get_current_user_from_session(request, db)

    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Get user data
    user_data = {
        "email": current_user.email,
        "display_name": current_user.display_name,
        "email_verified": current_user.email_verified,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }

    # Get all user's scrolls
    from app.models.scroll import Scroll

    result = await db.execute(select(Scroll).where(Scroll.user_id == current_user.id))
    scrolls = result.scalars().all()

    scrolls_data = []
    for scroll in scrolls:
        scrolls_data.append(
            {
                "title": scroll.title,
                "authors": scroll.authors,
                "abstract": scroll.abstract,
                "keywords": scroll.keywords,
                "license": scroll.license,
                "status": scroll.status,
                "url_hash": scroll.url_hash,
                "content_hash": scroll.content_hash,
                "doi": scroll.doi,
                "doi_status": scroll.doi_status,
                "doi_minted_at": scroll.doi_minted_at.isoformat()
                if scroll.doi_minted_at
                else None,
                "created_at": scroll.created_at.isoformat() if scroll.created_at else None,
                "updated_at": scroll.updated_at.isoformat() if scroll.updated_at else None,
                "published_at": scroll.published_at.isoformat() if scroll.published_at else None,
            }
        )

    # Get active sessions
    result = await db.execute(
        select(Session).where(
            Session.user_id == current_user.id,
            Session.expires_at > datetime.now(UTC),
        )
    )
    sessions = result.scalars().all()

    sessions_data = []
    for session in sessions:
        sessions_data.append(
            {
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "expires_at": session.expires_at.isoformat() if session.expires_at else None,
            }
        )

    return JSONResponse(
        {
            "user": user_data,
            "scrolls": scrolls_data,
            "sessions": sessions_data,
        }
    )


# Test-only endpoint for E2E tests
@router.post("/test-verify-user")
async def test_verify_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Test-only endpoint to verify users during E2E testing.

    WARNING: This endpoint is only available during E2E testing and should
    never be exposed in production.
    """
    # Check at runtime, not import time
    if os.getenv("E2E_TESTING", "").lower() not in ("true", "1", "yes"):
        raise HTTPException(status_code=404, detail="Not found")

    try:
        body = await request.json()
        email = body.get("email")

        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        # Find and verify user
        result = await db.execute(select(User).where(User.email == email.strip().lower()))
        user = result.scalar_one_or_none()

        if user:
            user.email_verified = True
            await db.commit()
            return {"success": True, "message": "User verified"}
        else:
            return {"success": False, "message": "User not found"}

    except Exception as e:
        get_logger().error(f"Error in test-verify-user: {e}")
        raise HTTPException(status_code=500, detail="Internal error")
