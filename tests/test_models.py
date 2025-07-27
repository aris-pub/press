"""Tests for core business logic and models."""

import time
from sqlalchemy import select

from app.auth.session import create_session, _get_user_id_from_session_id, delete_session, sessions
from app.auth.utils import get_password_hash, verify_password
from app.models.preview import Preview, Subject


class TestPasswordUtils:
    """Test password hashing and verification."""
    
    def test_get_password_hash(self):
        """Test password hashing."""
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 50  # bcrypt hashes are long
        assert hashed.startswith("$2b$")  # bcrypt prefix
    
    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "testpassword123"
        wrong_password = "wrongpassword"
        hashed = get_password_hash(password)
        
        assert verify_password(wrong_password, hashed) is False


class TestSessionManagement:
    """Test session creation, validation, and cleanup."""
    
    def setup_method(self):
        """Clear sessions before each test."""
        sessions.clear()
    
    def test_create_session(self):
        """Test session creation."""
        user_id = 123
        session_id = create_session(user_id)
        
        assert session_id is not None
        assert len(session_id) > 20  # URL-safe token should be long
        assert session_id in sessions
        assert sessions[session_id]["user_id"] == user_id
        assert "created_at" in sessions[session_id]
    
    def test_get_user_id_from_valid_session(self):
        """Test getting user ID from valid session."""
        user_id = 123
        session_id = create_session(user_id)
        
        retrieved_user_id = _get_user_id_from_session_id(session_id)
        assert retrieved_user_id == user_id
    
    def test_get_user_id_from_invalid_session(self):
        """Test getting user ID from invalid session."""
        retrieved_user_id = _get_user_id_from_session_id("invalid_session_id")
        assert retrieved_user_id is None
    
    def test_get_user_id_from_expired_session(self):
        """Test getting user ID from expired session."""
        user_id = 123
        session_id = create_session(user_id)
        
        # Manually set session to be expired (older than 24 hours)
        sessions[session_id]["created_at"] = time.time() - (24 * 3600 + 1)
        
        retrieved_user_id = _get_user_id_from_session_id(session_id)
        assert retrieved_user_id is None
        assert session_id not in sessions  # Should be cleaned up
    
    def test_delete_session(self):
        """Test session deletion."""
        user_id = 123
        session_id = create_session(user_id)
        
        assert session_id in sessions
        delete_session(session_id)
        assert session_id not in sessions
    
    def test_delete_nonexistent_session(self):
        """Test deleting non-existent session doesn't crash."""
        delete_session("nonexistent_session_id")  # Should not raise exception


class TestPreviewModel:
    """Test Preview model business logic."""
    
    async def test_preview_publish_method(self, test_db, test_user):
        """Test Preview.publish() method."""
        # Create a subject
        subject = Subject(name="Test Subject", description="Test description")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)
        
        # Create a draft preview
        preview = Preview(
            title="Test Preview",
            authors="Test Author",
            abstract="Test abstract",
            html_content="<h1>Test Content</h1>",
            user_id=test_user.id,
            subject_id=subject.id,
            status="draft"
        )
        test_db.add(preview)
        await test_db.commit()
        await test_db.refresh(preview)
        
        # Test initial state
        assert preview.status == "draft"
        assert preview.preview_id is None
        assert preview.published_at is None
        
        # Publish the preview
        preview.publish()
        await test_db.commit()
        await test_db.refresh(preview)
        
        # Test published state
        assert preview.status == "published"
        assert preview.preview_id is not None
        assert len(preview.preview_id) == 8  # Should be 8-character ID
        assert preview.published_at is not None
    
    async def test_preview_publish_idempotent(self, test_db, test_user):
        """Test that publishing already published preview is idempotent."""
        # Create a subject
        subject = Subject(name="Test Subject", description="Test description")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)
        
        # Create and publish preview
        preview = Preview(
            title="Test Preview",
            authors="Test Author",
            abstract="Test abstract", 
            html_content="<h1>Test Content</h1>",
            user_id=test_user.id,
            subject_id=subject.id,
            status="draft"
        )
        test_db.add(preview)
        await test_db.commit()
        
        # Publish once
        preview.publish()
        first_preview_id = preview.preview_id
        first_published_at = preview.published_at
        
        # Publish again
        preview.publish()
        
        # Should be unchanged
        assert preview.preview_id == first_preview_id
        assert preview.published_at == first_published_at
        assert preview.status == "published"
    
    async def test_preview_unique_ids(self, test_db, test_user):
        """Test that published previews get unique IDs."""
        # Create a subject
        subject = Subject(name="Test Subject", description="Test description")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)
        
        # Create and publish multiple previews
        previews = []
        for i in range(5):
            preview = Preview(
                title=f"Test Preview {i}",
                authors="Test Author",
                abstract="Test abstract",
                html_content="<h1>Test Content</h1>",
                user_id=test_user.id,
                subject_id=subject.id,
                status="draft"
            )
            test_db.add(preview)
            await test_db.commit()
            
            preview.publish()
            await test_db.commit()
            await test_db.refresh(preview)
            
            previews.append(preview)
        
        # Check all preview IDs are unique
        preview_ids = [p.preview_id for p in previews]
        assert len(set(preview_ids)) == len(preview_ids)  # All unique
        
        # Check all are 8 characters
        assert all(len(pid) == 8 for pid in preview_ids)