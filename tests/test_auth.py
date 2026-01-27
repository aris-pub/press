"""Tests for authentication routes."""

from httpx import AsyncClient


async def test_login_page_get(client: AsyncClient):
    """Test GET /login shows login form."""
    response = await client.get("/login")
    assert response.status_code == 200
    assert "Login" in response.text


async def test_login_page_redirects_authenticated_user(authenticated_client: AsyncClient):
    """Test GET /login redirects authenticated users to homepage."""
    response = await authenticated_client.get("/login", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/"


async def test_register_page_get(client: AsyncClient):
    """Test GET /register shows registration form."""
    response = await client.get("/register")
    assert response.status_code == 200
    assert "Register" in response.text


async def test_register_page_redirects_authenticated_user(authenticated_client: AsyncClient):
    """Test GET /register redirects authenticated users to homepage."""
    response = await authenticated_client.get("/register", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/"


async def test_login_form_valid_credentials(client: AsyncClient, test_user):
    """Test POST /login-form with valid credentials."""
    login_data = {"email": test_user.email, "password": "testpassword"}

    response = await client.post("/login-form", data=login_data)
    assert response.status_code == 200
    assert "session_id" in response.cookies
    assert "Welcome" in response.text or "success" in response.text.lower()


async def test_login_form_invalid_credentials(client: AsyncClient, test_user):
    """Test POST /login-form with invalid credentials."""
    login_data = {"email": test_user.email, "password": "wrongpassword"}

    response = await client.post("/login-form", data=login_data)
    assert response.status_code == 422
    assert "Incorrect email or password" in response.text


async def test_register_form_valid_data(client: AsyncClient):
    """Test POST /register-form with valid data."""
    register_data = {
        "email": "newuser@example.com",
        "password": "newpassword1",
        "confirm_password": "newpassword1",
        "display_name": "New User",
        "agree_terms": "true",
    }

    response = await client.post("/register-form", data=register_data)
    assert response.status_code == 200
    assert "session_id" in response.cookies
    assert "Welcome" in response.text or "Account Created" in response.text


async def test_register_form_duplicate_email(client: AsyncClient, test_user):
    """Test POST /register-form with existing email."""
    register_data = {
        "email": test_user.email,
        "password": "newpassword1",
        "confirm_password": "newpassword1",
        "display_name": "New User",
        "agree_terms": "true",
    }

    response = await client.post("/register-form", data=register_data)
    assert response.status_code == 422
    assert "Email already registered" in response.text


async def test_register_form_missing_checkbox(client: AsyncClient):
    """Test POST /register-form validates checkbox is required."""
    register_data = {
        "email": "newuser@example.com",
        "password": "newpassword1",
        "confirm_password": "newpassword1",
        "display_name": "New User",
        # Missing agree_terms checkbox
    }

    response = await client.post("/register-form", data=register_data)
    assert response.status_code == 422
    assert "You must agree to the Terms of Service and Privacy Policy" in response.text


async def test_logout_post(authenticated_client: AsyncClient):
    """Test POST /logout clears session."""
    response = await authenticated_client.post("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/"

    # Check that session cookie is cleared
    set_cookie_header = response.headers.get("set-cookie", "")
    assert "session_id=" in set_cookie_header


async def test_protected_route_redirects_unauthenticated(client: AsyncClient):
    """Test that protected routes redirect unauthenticated users."""
    response = await client.get("/upload", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_protected_route_allows_authenticated(authenticated_client: AsyncClient):
    """Test that protected routes allow authenticated users."""
    response = await authenticated_client.get("/upload")
    assert response.status_code == 200
    assert "Upload" in response.text


async def test_login_success_redirects_to_dashboard(client: AsyncClient, test_user):
    """Test that successful login shows success message with dashboard redirect."""
    login_data = {"email": test_user.email, "password": "testpassword"}

    response = await client.post("/login-form", data=login_data)
    assert response.status_code == 200
    assert "session_id" in response.cookies

    # Check that success template includes dashboard redirect
    assert "Welcome Back!" in response.text
    assert "Redirecting to dashboard..." in response.text
    assert 'hx-get="/dashboard"' in response.text
    assert 'hx-trigger="load delay:1s"' in response.text


async def test_login_success_template_has_redirect_attributes(client: AsyncClient, test_user):
    """Test that login success template has correct HTMX redirect attributes."""
    login_data = {"email": test_user.email, "password": "testpassword"}

    response = await client.post("/login-form", data=login_data)
    assert response.status_code == 200

    # Verify HTMX attributes for automatic redirect (targets main content, not body)
    assert 'hx-target="#main-content"' in response.text
    assert 'hx-push-url="true"' in response.text


async def test_delete_account_unauthenticated(client: AsyncClient):
    """Test DELETE /account requires authentication."""
    response = await client.delete("/account")
    assert response.status_code == 401


async def test_delete_account_authenticated(authenticated_client: AsyncClient, test_user, test_db):
    """Test DELETE /account deletes user account successfully."""

    # Delete the account
    response = await authenticated_client.delete("/account")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "Account deleted successfully" in response.json()["message"]


async def test_delete_account_with_tokens(authenticated_client: AsyncClient, test_user, test_db):
    """Test DELETE /account deletes user and their tokens successfully.

    Regression test for bug where account deletion failed with ForeignKeyViolationError
    when user had verification or password reset tokens.
    """
    from sqlalchemy import select

    from app.auth.tokens import create_password_reset_token, create_verification_token
    from app.models.token import Token

    # Create both types of tokens for the user
    await create_verification_token(test_db, test_user.id)
    await create_password_reset_token(test_db, test_user.id)
    await test_db.commit()

    # Verify tokens exist
    result = await test_db.execute(select(Token).where(Token.user_id == test_user.id))
    tokens = result.scalars().all()
    assert len(tokens) == 2, "User should have 2 tokens before deletion"

    # Delete the account
    response = await authenticated_client.delete("/account")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    assert response.json()["success"] is True
    assert "Account deleted successfully" in response.json()["message"]

    # Verify tokens were deleted
    result = await test_db.execute(select(Token).where(Token.user_id == test_user.id))
    tokens_after = result.scalars().all()
    assert len(tokens_after) == 0, "All user tokens should be deleted with account"


async def test_register_form_passwords_dont_match(client: AsyncClient):
    """Test POST /register-form with mismatched passwords."""
    register_data = {
        "email": "newuser@example.com",
        "password": "password123",
        "confirm_password": "differentpassword",
        "display_name": "New User",
        "agree_terms": "true",
    }

    response = await client.post("/register-form", data=register_data)
    assert response.status_code == 422
    assert "Passwords do not match" in response.text


async def test_register_form_missing_confirm_password(client: AsyncClient):
    """Test POST /register-form with missing confirm_password field."""
    register_data = {
        "email": "newuser@example.com",
        "password": "password123",
        "display_name": "New User",
        "agree_terms": "true",
        # Missing confirm_password
    }

    response = await client.post("/register-form", data=register_data)
    assert response.status_code == 422
    assert "Password confirmation is required" in response.text


async def test_register_form_display_name_too_long(client: AsyncClient):
    """Test POST /register-form with display name over 200 characters."""
    long_name = "A" * 201  # 201 characters
    register_data = {
        "email": "newuser@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "display_name": long_name,
        "agree_terms": "true",
    }

    response = await client.post("/register-form", data=register_data)
    assert response.status_code == 422
    assert "Display name must be less than 200 characters" in response.text


async def test_register_form_display_name_whitespace_only(client: AsyncClient):
    """Test POST /register-form with display name that is only whitespace."""
    register_data = {
        "email": "newuser@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "display_name": "   \t\n   ",  # Only whitespace
        "agree_terms": "true",
    }

    response = await client.post("/register-form", data=register_data)
    assert response.status_code == 422
    assert "Display name cannot be empty" in response.text


async def test_register_form_display_name_empty_string(client: AsyncClient):
    """Test POST /register-form with empty display name."""
    register_data = {
        "email": "newuser@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "display_name": "",
        "agree_terms": "true",
    }

    response = await client.post("/register-form", data=register_data)
    assert response.status_code == 422
    assert "Display name is required" in response.text


async def test_register_form_display_name_valid_edge_cases(client: AsyncClient):
    """Test POST /register-form with valid edge case display names."""
    # Test minimum length (1 character)
    register_data = {
        "email": "user1@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "display_name": "A",
        "agree_terms": "true",
    }

    response = await client.post("/register-form", data=register_data)
    assert response.status_code == 200
    assert "session_id" in response.cookies

    # Test maximum length (200 characters)
    long_name = "A" * 200  # Exactly 200 characters
    register_data = {
        "email": "user2@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "display_name": long_name,
        "agree_terms": "true",
    }

    response = await client.post("/register-form", data=register_data)
    assert response.status_code == 200
    assert "session_id" in response.cookies
