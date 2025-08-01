"""Authentication routes for registration, login, and logout."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import create_session, delete_session, get_current_user_from_session
from app.auth.utils import get_password_hash, verify_password
from app.database import get_db
from app.logging_config import get_logger, log_auth_event, log_error, log_request
from app.models.user import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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
    try:
        log_request(request, extra_data={"email": email, "display_name": display_name})

        # Validate input
        if not email or not email.strip():
            raise ValueError("Email is required")
        if not display_name or not display_name.strip():
            raise ValueError("Display name is required")
        if not password or len(password) < 1:
            raise ValueError("Password is required")
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
                    "form_data": {"email": email, "display_name": display_name, "agree_terms": agree_terms},
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

        # Create session and auto-login user
        session_id = await create_session(db, db_user.id)

        log_auth_event("register", normalized_email, True, request, user_id=str(db_user.id))

        # Return success partial with automatic login
        response = templates.TemplateResponse(
            request,
            "auth/partials/success.html",
            {
                "title": "Account Created!",
                "message": f"Welcome to Press, {db_user.display_name}!",
                "action_text": "Go to Dashboard",
                "action_url": "/",
            },
        )

        # Set session cookie
        response.set_cookie("session_id", session_id, httponly=True, secure=False, samesite="lax")

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
                "form_data": {"email": email, "display_name": display_name, "agree_terms": agree_terms},
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
        response.set_cookie("session_id", session_id, httponly=True, secure=False, samesite="lax")

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
