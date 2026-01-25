"""Tests for core business logic and models."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import _get_user_id_from_session_id, create_session, delete_session
from app.auth.utils import get_password_hash, verify_password
from app.models.scroll import Scroll, Subject
from app.models.session import Session
from app.models.user import User
from tests.conftest import create_content_addressable_scroll


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

    @pytest.mark.asyncio
    async def test_create_session(self, test_db: AsyncSession, test_user: User):
        """Test session creation."""
        session_id = await create_session(test_db, test_user.id)

        assert session_id is not None
        assert len(session_id) > 20  # URL-safe token should be long

        # Verify session was created in database
        from sqlalchemy import select

        result = await test_db.execute(select(Session).where(Session.session_id == session_id))
        db_session = result.scalar_one_or_none()

        assert db_session is not None
        assert db_session.user_id == test_user.id
        # Handle both naive and timezone-aware datetimes
        now = datetime.now(timezone.utc)
        if db_session.expires_at.tzinfo is None:
            # If database returns naive datetime, compare with naive now
            now = datetime.now(timezone.utc).replace(tzinfo=None)
        assert db_session.expires_at > now

    @pytest.mark.asyncio
    async def test_get_user_id_from_valid_session(self, test_db: AsyncSession, test_user: User):
        """Test getting user ID from valid session."""
        session_id = await create_session(test_db, test_user.id)

        retrieved_user_id = await _get_user_id_from_session_id(test_db, session_id)
        assert retrieved_user_id == test_user.id

    @pytest.mark.asyncio
    async def test_get_user_id_from_invalid_session(self, test_db: AsyncSession):
        """Test getting user ID from invalid session."""
        retrieved_user_id = await _get_user_id_from_session_id(test_db, "invalid_session_id")
        assert retrieved_user_id is None

    @pytest.mark.asyncio
    async def test_get_user_id_from_expired_session(self, test_db: AsyncSession, test_user: User):
        """Test getting user ID from expired session."""
        # Create an expired session manually
        expired_session = Session(
            session_id="expired_session_id",
            user_id=test_user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired 1 hour ago
        )
        test_db.add(expired_session)
        await test_db.commit()

        retrieved_user_id = await _get_user_id_from_session_id(test_db, "expired_session_id")
        assert retrieved_user_id is None

    @pytest.mark.asyncio
    async def test_delete_session(self, test_db: AsyncSession, test_user: User):
        """Test session deletion."""
        session_id = await create_session(test_db, test_user.id)

        # Verify session exists
        from sqlalchemy import select

        result = await test_db.execute(select(Session).where(Session.session_id == session_id))
        assert result.scalar_one_or_none() is not None

        # Delete session
        await delete_session(test_db, session_id)

        # Verify session is gone
        result = await test_db.execute(select(Session).where(Session.session_id == session_id))
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self, test_db: AsyncSession):
        """Test deleting non-existent session doesn't crash."""
        await delete_session(test_db, "nonexistent_session_id")  # Should not raise exception


class TestScrollModel:
    """Test Scroll model business logic."""

    async def test_scroll_publish_method(self, test_db, test_user):
        """Test Scroll.publish() method."""
        from app.storage.content_processing import generate_permanent_url

        # Create a subject
        subject = Subject(name="Test Subject", description="Test description")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        # Generate content hash
        html_content = "<h1>Test Content</h1>"
        url_hash, content_hash, _ = await generate_permanent_url(html_content)

        # Create a preview scroll
        scroll = Scroll(
            title="Test Scroll",
            authors="Test Author",
            abstract="Test abstract",
            html_content=html_content,
            license="cc-by-4.0",
            content_hash=content_hash,
            url_hash=url_hash,
            status="preview",
            user_id=test_user.id,
            subject_id=subject.id,
        )
        test_db.add(scroll)
        await test_db.commit()
        await test_db.refresh(scroll)

        # Test initial state (preview)
        assert scroll.status == "preview"
        assert scroll.url_hash is not None  # Content-addressable scroll has url_hash
        assert len(scroll.url_hash) >= 12  # Should be 12+ character hash
        assert scroll.published_at is None

        # Publish the scroll
        scroll.publish()
        await test_db.commit()
        await test_db.refresh(scroll)

        # Test published state
        assert scroll.status == "published"
        assert scroll.url_hash is not None
        assert len(scroll.url_hash) >= 12  # Should be 12+ character hash
        assert scroll.published_at is not None

    async def test_scroll_publish_idempotent(self, test_db, test_user):
        """Test that publishing already published scroll is idempotent."""
        # Create a subject
        subject = Subject(name="Test Subject", description="Test description")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        # Create and publish scroll
        scroll = await create_content_addressable_scroll(
            test_db,
            test_user,
            subject,
            title="Test Scroll",
            authors="Test Author",
            abstract="Test abstract",
            html_content="<h1>Test Content</h1>",
            license="cc-by-4.0",
        )

        # Publish once
        scroll.publish()
        first_url_hash = scroll.url_hash
        first_published_at = scroll.published_at

        # Publish again
        scroll.publish()

        # Should be unchanged
        assert scroll.url_hash == first_url_hash
        assert scroll.published_at == first_published_at
        assert scroll.status == "published"

    async def test_scroll_unique_ids(self, test_db, test_user):
        """Test that published scrolls get unique IDs."""
        # Create a subject
        subject = Subject(name="Test Subject", description="Test description")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        # Create and publish multiple scrolls
        scrolls = []
        for i in range(5):
            scroll = await create_content_addressable_scroll(
                test_db,
                test_user,
                subject,
                title=f"Test Scroll {i}",
                authors="Test Author",
                abstract="Test abstract",
                html_content=f"<h1>Test Content {i}</h1>",  # Different content for each scroll
                license="cc-by-4.0",
            )
            await test_db.commit()

            scroll.publish()
            await test_db.commit()
            await test_db.refresh(scroll)

            scrolls.append(scroll)

        # Check all URL hashes are unique
        url_hashes = [s.url_hash for s in scrolls]
        assert len(set(url_hashes)) == len(url_hashes)  # All unique

        # Check all are 12+ characters (content-addressable hash prefixes)
        assert all(len(hash) >= 12 for hash in url_hashes)
