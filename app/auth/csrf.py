"""CSRF protection for forms."""

import secrets
from typing import Optional

# In-memory storage for CSRF tokens (session_id -> csrf_token)
_csrf_tokens: dict[str, str] = {}


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token.

    Returns:
        64-character hex string (32 bytes)
    """
    return secrets.token_hex(32)


async def get_csrf_token(session_id: str) -> Optional[str]:
    """Get the CSRF token for a session, generating one if it doesn't exist.

    Args:
        session_id: The session ID to get the token for

    Returns:
        The CSRF token, or None if session_id is None
    """
    if session_id is None:
        return None

    # Return existing token if it exists
    if session_id in _csrf_tokens:
        return _csrf_tokens[session_id]

    # Generate new token and store it
    token = generate_csrf_token()
    _csrf_tokens[session_id] = token
    return token


async def validate_csrf_token(session_id: str, submitted_token: Optional[str]) -> bool:
    """Validate a CSRF token against the session's stored token.

    Args:
        session_id: The session ID to validate against
        submitted_token: The token submitted with the form

    Returns:
        True if valid, False otherwise
    """
    if session_id is None or submitted_token is None:
        return False

    stored_token = _csrf_tokens.get(session_id)
    if stored_token is None:
        return False

    # Use constant-time comparison to prevent timing attacks
    return secrets.compare_digest(stored_token, submitted_token)


async def rotate_csrf_token(session_id: str) -> str:
    """Rotate (regenerate) the CSRF token for a session.

    Called after authentication state changes (login, logout, etc.)

    Args:
        session_id: The session ID to rotate the token for

    Returns:
        The new CSRF token
    """
    new_token = generate_csrf_token()
    _csrf_tokens[session_id] = new_token
    return new_token


async def delete_csrf_token(session_id: str) -> None:
    """Delete the CSRF token for a session.

    Called when a session is destroyed.

    Args:
        session_id: The session ID to delete the token for
    """
    _csrf_tokens.pop(session_id, None)
