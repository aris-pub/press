import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

class TestFormPages:
    """Test form page rendering."""
    
    async def test_register_page(self, client: AsyncClient):
        """Test registration page loads correctly."""
        response = await client.get("/register")
        
        assert response.status_code == 200
        content = response.text
        assert "Create Your Account" in content
        assert "hx-post=\"/register-form\"" in content
        assert "name=\"email\"" in content
        assert "name=\"display_name\"" in content
        assert "name=\"password\"" in content
    
    async def test_login_page(self, client: AsyncClient):
        """Test login page loads correctly."""
        response = await client.get("/login")
        
        assert response.status_code == 200
        content = response.text
        assert "Welcome Back" in content
        assert "hx-post=\"/login-form\"" in content
        assert "name=\"email\"" in content
        assert "name=\"password\"" in content

class TestRegistrationForm:
    """Test registration form submission."""
    
    async def test_register_form_success(self, client: AsyncClient, test_db):
        """Test successful registration via form."""
        form_data = {
            "email": "newuser@example.com",
            "display_name": "New User",
            "password": "securepassword123"
        }
        
        response = await client.post("/register-form", data=form_data)
        
        assert response.status_code == 200
        content = response.text
        assert "Account Created!" in content
        assert "Welcome to Press, New User!" in content
        assert "Go to Dashboard" in content
    
    async def test_register_form_duplicate_email(self, client: AsyncClient, test_user):
        """Test registration with existing email."""
        form_data = {
            "email": test_user.email,
            "display_name": "Another User",
            "password": "password123"
        }
        
        response = await client.post("/register-form", data=form_data)
        
        assert response.status_code == 422
        content = response.text
        assert "Email already registered" in content
        assert "register-form-container" in content
    
    async def test_register_form_duplicate_email_preserves_form_data(self, client: AsyncClient, test_user):
        """Test that duplicate email error preserves the user's form data."""
        form_data = {
            "email": test_user.email,  # This email already exists
            "display_name": "Another User",
            "password": "password123"
        }
        
        response = await client.post("/register-form", data=form_data)
        
        assert response.status_code == 422
        content = response.text
        
        # Should show error message
        assert "Email already registered" in content
        
        # Should preserve the form data that the user entered
        assert f'value="{test_user.email}"' in content  # Email should be pre-filled
        assert f'value="Another User"' in content  # Display name should be pre-filled
        
        # Password should NOT be pre-filled for security reasons
        assert 'type="password"' in content
        assert 'value=""' in content or 'value=' not in content.split('type="password"')[1].split('>')[0]
        
        # Should still be in the registration form container for HTMX swapping
        assert 'id="register-form-container"' in content
    
    async def test_register_form_duplicate_email_case_insensitive(self, client: AsyncClient, test_user):
        """Test that duplicate email detection is case insensitive."""
        form_data = {
            "email": test_user.email.upper(),  # Same email but uppercase
            "display_name": "Another User", 
            "password": "password123"
        }
        
        response = await client.post("/register-form", data=form_data)
        
        assert response.status_code == 422
        content = response.text
        assert "Email already registered" in content
    
    async def test_register_form_missing_fields(self, client: AsyncClient):
        """Test registration with missing fields."""
        form_data = {
            "email": "test@example.com",
            "display_name": "",
            "password": "password123"
        }
        
        response = await client.post("/register-form", data=form_data)
        
        assert response.status_code == 422
        content = response.text
        assert "Display name is required" in content
    
    async def test_register_form_empty_password(self, client: AsyncClient):
        """Test registration with empty password."""
        form_data = {
            "email": "test@example.com",
            "display_name": "Test User",
            "password": ""
        }
        
        response = await client.post("/register-form", data=form_data)
        
        assert response.status_code == 422
        content = response.text
        assert "Password is required" in content

class TestLoginForm:
    """Test login form submission."""
    
    async def test_login_form_success(self, client: AsyncClient, test_user):
        """Test successful login via form."""
        form_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        response = await client.post("/login-form", data=form_data)
        
        assert response.status_code == 200
        content = response.text
        assert "Welcome Back!" in content
        assert f"Successfully signed in as {test_user.display_name}" in content
        assert "Go to Dashboard" in content
    
    async def test_login_form_wrong_password(self, client: AsyncClient, test_user):
        """Test login with wrong password."""
        form_data = {
            "email": test_user.email,
            "password": "wrongpassword"
        }
        
        response = await client.post("/login-form", data=form_data)
        
        assert response.status_code == 422
        content = response.text
        assert "Incorrect email or password" in content
        assert "login-form-container" in content
    
    async def test_login_form_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent email."""
        form_data = {
            "email": "nonexistent@example.com",
            "password": "somepassword"
        }
        
        response = await client.post("/login-form", data=form_data)
        
        assert response.status_code == 422
        content = response.text
        assert "Incorrect email or password" in content
    
    async def test_login_form_missing_fields(self, client: AsyncClient):
        """Test login with missing fields."""
        form_data = {
            "email": "",
            "password": "password123"
        }
        
        response = await client.post("/login-form", data=form_data)
        
        assert response.status_code == 422
        content = response.text
        assert "Email is required" in content
    
    async def test_login_form_case_insensitive_email(self, client: AsyncClient, test_user):
        """Test that login works with case insensitive email."""
        form_data = {
            "email": test_user.email.upper(),  # Same email but uppercase
            "password": "testpassword"
        }
        
        response = await client.post("/login-form", data=form_data)
        
        assert response.status_code == 200
        content = response.text
        assert "Welcome Back!" in content
        assert f"Successfully signed in as {test_user.display_name}" in content

class TestStaticFiles:
    """Test static file serving."""
    
    async def test_static_directory_works(self, client: AsyncClient):
        """Test that static file serving is set up correctly."""
        # Test that trying to access a non-existent static file returns 404
        response = await client.get("/static/nonexistent.css")
        assert response.status_code == 404

class TestLandingPageIntegration:
    """Test landing page integration with auth forms."""
    
    async def test_landing_page_has_auth_links(self, client: AsyncClient):
        """Test that landing page links to auth forms."""
        response = await client.get("/")
        
        assert response.status_code == 200
        content = response.text
        assert 'href="/login"' in content
        assert 'href="/register"' in content
    
    async def test_auth_pages_have_consistent_navbar(self, client: AsyncClient):
        """Test that auth pages have the same navbar as landing page."""
        # Test login page navbar
        login_response = await client.get("/login")
        assert login_response.status_code == 200
        login_content = login_response.text
        
        # Check for consistent navbar elements
        assert "Preview Press" in login_content
        assert "Browse" in login_content
        assert "Recent" in login_content
        assert "About" in login_content
        assert "Help" in login_content
        assert "auth-buttons" in login_content
        
        # Test register page navbar
        register_response = await client.get("/register")
        assert register_response.status_code == 200
        register_content = register_response.text
        
        # Check for consistent navbar elements
        assert "Preview Press" in register_content
        assert "Browse" in register_content
        assert "Recent" in register_content
        assert "About" in register_content
        assert "Help" in register_content
        assert "auth-buttons" in register_content
    
    async def test_auth_pages_have_footer(self, client: AsyncClient):
        """Test that auth pages have the same footer as landing page."""
        # Test login page footer
        login_response = await client.get("/login")
        assert login_response.status_code == 200
        login_content = login_response.text
        
        # Check for footer elements
        assert "About Preview Press" in login_content
        assert "Submit a Paper" in login_content
        assert "Discussion Forum" in login_content
        assert "Help Center" in login_content
        assert "© 2025 Preview Press" in login_content
        
        # Test register page footer
        register_response = await client.get("/register") 
        assert register_response.status_code == 200
        register_content = register_response.text
        
        # Check for footer elements
        assert "About Preview Press" in register_content
        assert "Submit a Paper" in register_content
        assert "Discussion Forum" in register_content
        assert "Help Center" in register_content
        assert "© 2025 Preview Press" in register_content

class TestAuthenticatedNavbar:
    """Test navbar behavior for authenticated users."""
    
    async def test_navbar_shows_correct_buttons_for_logged_in_user(self, client: AsyncClient, test_user):
        """Test that logged-in users see the correct navbar buttons."""
        # First login to get auth cookies
        form_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        login_response = await client.post("/login-form", data=form_data)
        assert login_response.status_code == 200
        
        # Extract cookies from login response
        cookies = login_response.cookies
        
        # Now visit homepage with auth cookies
        response = await client.get("/", cookies=cookies)
        assert response.status_code == 200
        content = response.text
        
        # Should show welcome message and authenticated buttons
        assert f"Welcome, {test_user.display_name}!" in content
        assert 'href="/upload"' in content  # Upload Preview should go to /upload
        assert 'href="/logout"' in content
        
        # Should NOT show login/register buttons
        assert 'href="/login"' not in content
        assert 'href="/register"' not in content
    
    async def test_navbar_shows_correct_buttons_for_anonymous_user(self, client: AsyncClient):
        """Test that anonymous users see the correct navbar buttons."""
        response = await client.get("/")
        assert response.status_code == 200
        content = response.text
        
        # Should show login/register buttons
        assert 'href="/login"' in content
        assert 'href="/register"' in content
        
        # Should NOT show welcome message or authenticated buttons
        assert "Welcome," not in content
        assert 'href="/upload"' not in content
        assert 'href="/logout"' not in content

class TestLogout:
    """Test logout functionality."""
    
    async def test_logout_clears_session_and_redirects(self, client: AsyncClient, test_user):
        """Test that logout clears the session and redirects to homepage."""
        # First login to get a session
        form_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        login_response = await client.post("/login-form", data=form_data)
        assert login_response.status_code == 200
        
        # Extract session cookie
        session_cookie = login_response.cookies.get("session_id")
        assert session_cookie is not None
        
        # Verify user is logged in by checking homepage
        homepage_response = await client.get("/", cookies={"session_id": session_cookie})
        assert f"Welcome, {test_user.display_name}!" in homepage_response.text
        
        # Now logout
        logout_response = await client.post("/logout", cookies={"session_id": session_cookie})
        
        # Should redirect to homepage (302 or similar redirect status)
        assert logout_response.status_code in [302, 303, 307, 308]
        assert logout_response.headers.get("location") == "/"
        
        # Session should be cleared - verify by trying to access homepage
        # The session should no longer work after logout
        post_logout_response = await client.get("/")
        assert f"Welcome, {test_user.display_name}!" not in post_logout_response.text
        assert 'href="/login"' in post_logout_response.text  # Should see login button
    
    async def test_logout_via_get_request_also_works(self, client: AsyncClient, test_user):
        """Test that logout also works via GET request for direct navigation."""
        # Login first
        form_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        login_response = await client.post("/login-form", data=form_data)
        session_cookie = login_response.cookies.get("session_id")
        
        # Logout via GET
        logout_response = await client.get("/logout", cookies={"session_id": session_cookie})
        
        # Should redirect and clear session
        assert logout_response.status_code in [302, 303, 307, 308]
        assert logout_response.headers.get("location") == "/"
        
        # Verify session is cleared by checking homepage
        post_logout_response = await client.get("/")
        assert f"Welcome, {test_user.display_name}!" not in post_logout_response.text
    
    async def test_after_logout_user_sees_anonymous_navbar(self, client: AsyncClient, test_user):
        """Test that after logout, user sees the anonymous navbar."""
        # Login first
        form_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        login_response = await client.post("/login-form", data=form_data)
        session_cookie = login_response.cookies.get("session_id")
        
        # Logout
        logout_response = await client.post("/logout", cookies={"session_id": session_cookie})
        
        # Follow the redirect to homepage
        homepage_response = await client.get("/")
        content = homepage_response.text
        
        # Should see anonymous navbar (no welcome message, login/register buttons)
        assert "Welcome," not in content
        assert 'href="/login"' in content
        assert 'href="/register"' in content
        assert 'href="/upload"' not in content
        assert 'href="/logout"' not in content
    
    async def test_logout_without_session_still_works(self, client: AsyncClient):
        """Test that logout gracefully handles users without sessions."""
        # Try to logout without being logged in
        logout_response = await client.post("/logout")
        
        # Should still redirect to homepage
        assert logout_response.status_code in [302, 303, 307, 308]
        assert logout_response.headers.get("location") == "/"

class TestAuthPageRedirects:
    """Test that logged-in users are redirected away from auth pages."""
    
    async def test_logged_in_user_redirected_from_login_page(self, client: AsyncClient, test_user):
        """Test that logged-in users are redirected from /login to dashboard."""
        # First login to get a session
        form_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        login_response = await client.post("/login-form", data=form_data)
        session_cookie = login_response.cookies.get("session_id")
        
        # Now try to access login page while logged in
        response = await client.get("/login", cookies={"session_id": session_cookie})
        
        # Should redirect to homepage/dashboard
        assert response.status_code in [302, 303, 307, 308]
        assert response.headers.get("location") == "/"
    
    async def test_logged_in_user_redirected_from_register_page(self, client: AsyncClient, test_user):
        """Test that logged-in users are redirected from /register to dashboard."""
        # First login to get a session
        form_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        login_response = await client.post("/login-form", data=form_data)
        session_cookie = login_response.cookies.get("session_id")
        
        # Now try to access register page while logged in
        response = await client.get("/register", cookies={"session_id": session_cookie})
        
        # Should redirect to homepage/dashboard
        assert response.status_code in [302, 303, 307, 308]
        assert response.headers.get("location") == "/"
    
    async def test_anonymous_user_can_access_login_page(self, client: AsyncClient):
        """Test that anonymous users can still access login page normally."""
        response = await client.get("/login")
        
        # Should show the login page (200 OK)
        assert response.status_code == 200
        assert "Welcome Back" in response.text
        assert "hx-post=\"/login-form\"" in response.text
    
    async def test_anonymous_user_can_access_register_page(self, client: AsyncClient):
        """Test that anonymous users can still access register page normally."""
        response = await client.get("/register")
        
        # Should show the register page (200 OK)
        assert response.status_code == 200
        assert "Create Your Account" in response.text
        assert "hx-post=\"/register-form\"" in response.text