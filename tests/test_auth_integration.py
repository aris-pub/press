import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models.user import User
from app.auth.utils import verify_token

pytestmark = pytest.mark.asyncio

class TestAuthIntegration:
    """Integration tests for complete authentication flows."""
    
    async def test_complete_registration_and_login_flow(self, client: AsyncClient, test_db):
        """Test complete flow: register -> login -> access protected resource."""
        # Step 1: Register a new user
        user_data = {
            "email": "integration@example.com",
            "password": "securepassword123",
            "display_name": "Integration Test User"
        }
        
        register_response = await client.post("/auth/register", json=user_data)
        assert register_response.status_code == 201
        registered_user = register_response.json()
        
        # Step 2: Login with the new user
        login_data = {
            "email": user_data["email"],
            "password": user_data["password"]
        }
        
        login_response = await client.post("/auth/login", json=login_data)
        assert login_response.status_code == 200
        tokens = login_response.json()
        
        # Step 3: Access protected resource
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        me_response = await client.get("/auth/me", headers=headers)
        assert me_response.status_code == 200
        
        user_info = me_response.json()
        assert user_info["email"] == user_data["email"]
        assert user_info["display_name"] == user_data["display_name"]
        assert user_info["id"] == registered_user["id"]
    
    async def test_token_refresh_flow(self, client: AsyncClient, test_user):
        """Test complete token refresh flow."""
        # Step 1: Login to get initial tokens
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        login_response = await client.post("/auth/login", json=login_data)
        original_tokens = login_response.json()
        
        # Step 2: Use access token to access protected resource
        headers = {"Authorization": f"Bearer {original_tokens['access_token']}"}
        me_response = await client.get("/auth/me", headers=headers)
        assert me_response.status_code == 200
        
        # Step 3: Refresh tokens
        refresh_data = {"refresh_token": original_tokens["refresh_token"]}
        refresh_response = await client.post("/auth/refresh", json=refresh_data)
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        
        # Step 4: Use new access token
        new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
        me_response_2 = await client.get("/auth/me", headers=new_headers)
        assert me_response_2.status_code == 200
        
        # Should get the same user info
        user_info_1 = me_response.json()
        user_info_2 = me_response_2.json()
        assert user_info_1["id"] == user_info_2["id"]
        assert user_info_1["email"] == user_info_2["email"]
        
        # Old access token should still work (until it expires)
        old_headers = {"Authorization": f"Bearer {original_tokens['access_token']}"}
        me_response_3 = await client.get("/auth/me", headers=old_headers)
        assert me_response_3.status_code == 200
    
    async def test_multiple_refreshes(self, client: AsyncClient, test_user):
        """Test multiple consecutive token refreshes."""
        # Initial login
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        login_response = await client.post("/auth/login", json=login_data)
        tokens = login_response.json()
        
        # Perform multiple refreshes
        for i in range(3):
            refresh_data = {"refresh_token": tokens["refresh_token"]}
            refresh_response = await client.post("/auth/refresh", json=refresh_data)
            assert refresh_response.status_code == 200
            
            new_tokens = refresh_response.json()
            
            # Each refresh should produce new tokens
            assert new_tokens["access_token"] != tokens["access_token"]
            assert new_tokens["refresh_token"] != tokens["refresh_token"]
            
            # New tokens should work
            headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
            me_response = await client.get("/auth/me", headers=headers)
            assert me_response.status_code == 200
            
            # Update tokens for next iteration
            tokens = new_tokens
    
    async def test_concurrent_user_sessions(self, client: AsyncClient, test_db):
        """Test multiple users can be authenticated simultaneously."""
        # Create two users
        users_data = [
            {
                "email": "user1@example.com",
                "password": "password123",
                "display_name": "User One"
            },
            {
                "email": "user2@example.com", 
                "password": "password456",
                "display_name": "User Two"
            }
        ]
        
        tokens_list = []
        
        # Register and login both users
        for user_data in users_data:
            # Register
            register_response = await client.post("/auth/register", json=user_data)
            assert register_response.status_code == 201
            
            # Login
            login_data = {
                "email": user_data["email"],
                "password": user_data["password"]
            }
            login_response = await client.post("/auth/login", json=login_data)
            assert login_response.status_code == 200
            tokens_list.append(login_response.json())
        
        # Both users should be able to access their info simultaneously
        for i, tokens in enumerate(tokens_list):
            headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            me_response = await client.get("/auth/me", headers=headers)
            assert me_response.status_code == 200
            
            user_info = me_response.json()
            assert user_info["email"] == users_data[i]["email"]
            assert user_info["display_name"] == users_data[i]["display_name"]
    
    async def test_user_persistence_across_requests(self, client: AsyncClient, test_user):
        """Test that user data persists correctly across multiple requests."""
        # Login
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        login_response = await client.post("/auth/login", json=login_data)
        tokens = login_response.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        
        # Make multiple requests to /auth/me
        for _ in range(5):
            response = await client.get("/auth/me", headers=headers)
            assert response.status_code == 200
            
            user_data = response.json()
            assert user_data["email"] == test_user.email
            assert user_data["display_name"] == test_user.display_name
            assert user_data["email_verified"] == test_user.email_verified
            
            # User ID should be consistent
            assert "id" in user_data
    
    async def test_token_payload_consistency(self, client: AsyncClient, test_user):
        """Test that token payloads contain consistent user information."""
        # Login
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        login_response = await client.post("/auth/login", json=login_data)
        tokens = login_response.json()
        
        # Verify token payloads
        access_payload = verify_token(tokens["access_token"], "access")
        refresh_payload = verify_token(tokens["refresh_token"], "refresh")
        
        assert access_payload is not None
        assert refresh_payload is not None
        
        # Both tokens should have same user info
        assert access_payload["sub"] == refresh_payload["sub"]
        assert access_payload["email"] == refresh_payload["email"]
        assert access_payload["sub"] == str(test_user.id)
        assert access_payload["email"] == test_user.email
        
        # But different types and expiration times
        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"
        assert access_payload["exp"] < refresh_payload["exp"]  # Access expires first
    
    async def test_authentication_error_scenarios(self, client: AsyncClient):
        """Test various authentication error scenarios in sequence."""
        # 1. Try protected endpoint without auth
        response = await client.get("/auth/me")
        assert response.status_code == 403
        
        # 2. Try with malformed token
        headers = {"Authorization": "Bearer malformed.token"}
        response = await client.get("/auth/me", headers=headers)
        assert response.status_code == 401
        
        # 3. Try login with non-existent user
        login_data = {
            "email": "nonexistent@example.com",
            "password": "somepassword"
        }
        response = await client.post("/auth/login", json=login_data)
        assert response.status_code == 401
        
        # 4. Try refresh with invalid token
        refresh_data = {"refresh_token": "invalid.refresh.token"}
        response = await client.post("/auth/refresh", json=refresh_data)
        assert response.status_code == 401
        
        # 5. Try register with duplicate email
        user_data = {
            "email": "test@example.com",
            "password": "password123",
            "display_name": "Test User"
        }
        
        # First registration should succeed
        response1 = await client.post("/auth/register", json=user_data)
        assert response1.status_code == 201
        
        # Second registration with same email should fail
        response2 = await client.post("/auth/register", json=user_data)
        assert response2.status_code == 400