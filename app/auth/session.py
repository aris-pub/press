"""Session management for authentication."""

import secrets
import time

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

# Simple in-memory session store
sessions = {}


def create_session(user_id: int) -> str:
    """Create a new session and return session ID."""
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {"user_id": user_id, "created_at": time.time()}
    return session_id


def _get_user_id_from_session_id(session_id: str) -> int | None:
    """Get user ID from session ID, return None if expired/invalid."""
    if not session_id or session_id not in sessions:
        return None

    session_data = sessions[session_id]
    # Sessions expire after 24 hours
    if time.time() - session_data["created_at"] > 86400:
        del sessions[session_id]
        return None

    return session_data["user_id"]


def delete_session(session_id: str):
    """Delete a session."""
    if session_id in sessions:
        del sessions[session_id]


async def get_current_user_from_session(request: Request, db: AsyncSession) -> User | None:
    """Get current user from session cookie."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    user_id = _get_user_id_from_session_id(session_id)
    if not user_id:
        return None

    try:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    except Exception:
        return None
