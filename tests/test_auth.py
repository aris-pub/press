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
        "password": "newpassword",
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
        "password": "newpassword",
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
        "password": "newpassword",  
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

    # Verify HTMX attributes for automatic redirect
    assert 'hx-target="body"' in response.text
    assert 'hx-push-url="true"' in response.text
