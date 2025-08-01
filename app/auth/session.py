"""Session management for authentication."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session
from app.models.user import User


async def create_session(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Create a new session and return session ID."""
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    db_session = Session(
        session_id=session_id,
        user_id=user_id,
        expires_at=expires_at
    )
    db.add(db_session)
    await db.commit()
    return session_id


async def _get_user_id_from_session_id(db: AsyncSession, session_id: str) -> uuid.UUID | None:
    """Get user ID from session ID, return None if expired/invalid."""
    if not session_id:
        return None

    try:
        # Get session and check if it's not expired
        result = await db.execute(
            select(Session).where(
                Session.session_id == session_id,
                Session.expires_at > datetime.now(timezone.utc)
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return None
            
        return session.user_id
    except Exception:
        return None


async def delete_session(db: AsyncSession, session_id: str):
    """Delete a session."""
    if not session_id:
        return
        
    try:
        await db.execute(delete(Session).where(Session.session_id == session_id))
        await db.commit()
    except Exception:
        pass  # Ignore errors when deleting sessions


async def cleanup_expired_sessions(db: AsyncSession):
    """Clean up expired sessions (lazy cleanup)."""
    try:
        await db.execute(
            delete(Session).where(Session.expires_at <= datetime.now(timezone.utc))
        )
        await db.commit()
    except Exception:
        pass  # Ignore cleanup errors


async def get_current_user_from_session(request: Request, db: AsyncSession) -> User | None:
    """Get current user from session cookie."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    # Clean up expired sessions on each lookup (lazy cleanup)
    await cleanup_expired_sessions(db)
    
    user_id = await _get_user_id_from_session_id(db, session_id)
    if not user_id:
        return None

    try:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    except Exception:
        return None
