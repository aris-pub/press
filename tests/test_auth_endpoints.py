import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models.user import User

pytestmark = pytest.mark.asyncio

class TestUserRegistration:
    """Test user registration endpoint."""
    
    async def test_register_new_user(self, client: AsyncClient, test_db):
        """Test successful user registration."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "display_name": "New User"
        }
        
        response = await client.post("/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        
        # Check response data
        assert data["email"] == user_data["email"]
        assert data["display_name"] == user_data["display_name"]
        assert data["email_verified"] is False
        assert "id" in data
        assert "created_at" in data
        assert "password" not in data  # Password should not be returned
        
        # Verify user was created in database
        result = await test_db.execute(select(User).where(User.email == user_data["email"]))
        db_user = result.scalar_one_or_none()
        assert db_user is not None
        assert db_user.email == user_data["email"]
        assert db_user.display_name == user_data["display_name"]
    
    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        """Test registration with existing email fails."""
        user_data = {
            "email": test_user.email,  # Same email as existing user
            "password": "securepassword123",
            "display_name": "Another User"
        }
        
        response = await client.post("/auth/register", json=user_data)
        
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]
    
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email format."""
        user_data = {
            "email": "not-an-email",
            "password": "securepassword123",
            "display_name": "Test User"
        }
        
        response = await client.post("/auth/register", json=user_data)
        
        assert response.status_code == 422  # Validation error
    
    async def test_register_missing_fields(self, client: AsyncClient):
        """Test registration with missing required fields."""
        incomplete_data = {
            "email": "test@example.com"
            # Missing password and display_name
        }
        
        response = await client.post("/auth/register", json=incomplete_data)
        
        assert response.status_code == 422
    
    async def test_register_empty_password(self, client: AsyncClient):
        """Test registration with empty password."""
        user_data = {
            "email": "test@example.com",
            "password": "",
            "display_name": "Test User"
        }
        
        response = await client.post("/auth/register", json=user_data)
        
        assert response.status_code == 422

class TestUserLogin:
    """Test user login endpoint."""
    
    async def test_login_success(self, client: AsyncClient, test_user):
        """Test successful login."""
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        response = await client.post("/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        
        # Tokens should be non-empty strings
        assert len(data["access_token"]) > 100
        assert len(data["refresh_token"]) > 100
        assert data["access_token"] != data["refresh_token"]
    
    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        """Test login with wrong password."""
        login_data = {
            "email": test_user.email,
            "password": "wrongpassword"
        }
        
        response = await client.post("/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]
    
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent email."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "somepassword"
        }
        
        response = await client.post("/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]
    
    async def test_login_invalid_email_format(self, client: AsyncClient):
        """Test login with invalid email format."""
        login_data = {
            "email": "not-an-email",
            "password": "somepassword"
        }
        
        response = await client.post("/auth/login", json=login_data)
        
        assert response.status_code == 422
    
    async def test_login_missing_fields(self, client: AsyncClient):
        """Test login with missing fields."""
        incomplete_data = {
            "email": "test@example.com"
            # Missing password
        }
        
        response = await client.post("/auth/login", json=incomplete_data)
        
        assert response.status_code == 422

class TestTokenRefresh:
    """Test token refresh endpoint."""
    
    async def test_refresh_token_success(self, client: AsyncClient, test_user):
        """Test successful token refresh."""
        # First login to get tokens
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        login_response = await client.post("/auth/login", json=login_data)
        tokens = login_response.json()
        
        # Use refresh token to get new tokens
        refresh_data = {
            "refresh_token": tokens["refresh_token"]
        }
        
        response = await client.post("/auth/refresh", json=refresh_data)
        
        assert response.status_code == 200
        new_tokens = response.json()
        
        # Check response structure
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        assert new_tokens["token_type"] == "bearer"
        
        # New tokens should be different from old ones
        assert new_tokens["access_token"] != tokens["access_token"]
        assert new_tokens["refresh_token"] != tokens["refresh_token"]
    
    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Test refresh with invalid token."""
        refresh_data = {
            "refresh_token": "invalid.token.here"
        }
        
        response = await client.post("/auth/refresh", json=refresh_data)
        
        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]
    
    async def test_refresh_with_access_token(self, client: AsyncClient, test_user):
        """Test refresh with access token instead of refresh token."""
        # Login to get tokens
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        login_response = await client.post("/auth/login", json=login_data)
        tokens = login_response.json()
        
        # Try to use access token as refresh token
        refresh_data = {
            "refresh_token": tokens["access_token"]  # Wrong token type
        }
        
        response = await client.post("/auth/refresh", json=refresh_data)
        
        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]
    
    async def test_refresh_missing_token(self, client: AsyncClient):
        """Test refresh with missing token."""
        response = await client.post("/auth/refresh", json={})
        
        assert response.status_code == 422

class TestProtectedEndpoint:
    """Test protected /auth/me endpoint."""
    
    async def test_get_current_user_success(self, client: AsyncClient, auth_headers, test_user):
        """Test getting current user info with valid token."""
        response = await client.get("/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check user data
        assert data["email"] == test_user.email
        assert data["display_name"] == test_user.display_name
        assert data["email_verified"] == test_user.email_verified
        assert "id" in data
        assert "created_at" in data
        assert "password" not in data
    
    async def test_get_current_user_no_token(self, client: AsyncClient):
        """Test protected endpoint without token."""
        response = await client.get("/auth/me")
        
        assert response.status_code == 403  # Forbidden (no auth header)
    
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test protected endpoint with invalid token."""
        headers = {"Authorization": "Bearer invalid.token.here"}
        
        response = await client.get("/auth/me", headers=headers)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]
    
    async def test_get_current_user_wrong_token_type(self, client: AsyncClient, test_user):
        """Test protected endpoint with refresh token instead of access token."""
        # Login to get tokens
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        login_response = await client.post("/auth/login", json=login_data)
        tokens = login_response.json()
        
        # Use refresh token instead of access token
        headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
        
        response = await client.get("/auth/me", headers=headers)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]
    
    async def test_get_current_user_malformed_header(self, client: AsyncClient):
        """Test protected endpoint with malformed authorization header."""
        headers = {"Authorization": "NotBearer token"}
        
        response = await client.get("/auth/me", headers=headers)
        
        assert response.status_code == 403