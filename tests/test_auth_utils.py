import pytest
from datetime import datetime, timezone, timedelta
from app.auth.utils import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token
)

class TestPasswordHashing:
    """Test password hashing utilities."""
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "test_password_123"
        hashed = get_password_hash(password)
        
        # Hash should be different from original password
        assert hashed != password
        assert len(hashed) > 50  # bcrypt hashes are long
        
        # Verification should work
        assert verify_password(password, hashed) is True
        
        # Wrong password should fail
        assert verify_password("wrong_password", hashed) is False
    
    def test_different_passwords_different_hashes(self):
        """Test that same password produces different hashes each time."""
        password = "same_password"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # Hashes should be different (due to salt)
        assert hash1 != hash2
        
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

class TestJWTTokens:
    """Test JWT token creation and verification."""
    
    def test_create_access_token(self):
        """Test access token creation."""
        data = {"sub": "user123", "email": "test@example.com"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 100  # JWT tokens are quite long
        
        # Verify token
        payload = verify_token(token, "access")
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"
        
        # Check expiration is set
        assert "exp" in payload
        assert "iat" in payload
    
    def test_create_refresh_token(self):
        """Test refresh token creation."""
        data = {"sub": "user123", "email": "test@example.com"}
        token = create_refresh_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 100
        
        # Verify token
        payload = verify_token(token, "refresh")
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "refresh"
    
    def test_token_type_validation(self):
        """Test that token type is validated correctly."""
        data = {"sub": "user123"}
        access_token = create_access_token(data)
        refresh_token = create_refresh_token(data)
        
        # Access token should not verify as refresh token
        assert verify_token(access_token, "refresh") is None
        
        # Refresh token should not verify as access token
        assert verify_token(refresh_token, "access") is None
        
        # But they should verify with correct types
        assert verify_token(access_token, "access") is not None
        assert verify_token(refresh_token, "refresh") is not None
    
    def test_invalid_token(self):
        """Test handling of invalid tokens."""
        invalid_tokens = [
            "invalid.token.here",
            "not-a-jwt-at-all",
            "",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid",
        ]
        
        for invalid_token in invalid_tokens:
            assert verify_token(invalid_token, "access") is None
            assert verify_token(invalid_token, "refresh") is None
    
    def test_token_timestamps_are_utc(self):
        """Test that token timestamps are in UTC."""
        data = {"sub": "user123"}
        token = create_access_token(data)
        payload = verify_token(token, "access")
        
        # Convert timestamps back to datetime
        iat = datetime.fromtimestamp(payload["iat"], timezone.utc)
        exp = datetime.fromtimestamp(payload["exp"], timezone.utc)
        
        # Check they're recent and in UTC
        now = datetime.now(timezone.utc)
        assert abs((now - iat).total_seconds()) < 5  # Within 5 seconds
        assert exp > now  # Expiration is in the future
        assert iat.tzinfo == timezone.utc
        assert exp.tzinfo == timezone.utc
    
    def test_access_token_expiration_time(self):
        """Test that access token has correct expiration time."""
        data = {"sub": "user123"}
        token = create_access_token(data)
        payload = verify_token(token, "access")
        
        iat = datetime.fromtimestamp(payload["iat"], timezone.utc)
        exp = datetime.fromtimestamp(payload["exp"], timezone.utc)
        
        # Should expire in 30 minutes (default setting)
        expected_duration = timedelta(minutes=30)
        actual_duration = exp - iat
        
        # Allow some tolerance for execution time
        assert abs(actual_duration - expected_duration).total_seconds() < 5
    
    def test_refresh_token_expiration_time(self):
        """Test that refresh token has correct expiration time."""
        data = {"sub": "user123"}
        token = create_refresh_token(data)
        payload = verify_token(token, "refresh")
        
        iat = datetime.fromtimestamp(payload["iat"], timezone.utc)
        exp = datetime.fromtimestamp(payload["exp"], timezone.utc)
        
        # Should expire in 7 days (default setting)
        expected_duration = timedelta(days=7)
        actual_duration = exp - iat
        
        # Allow some tolerance for execution time
        assert abs(actual_duration - expected_duration).total_seconds() < 5