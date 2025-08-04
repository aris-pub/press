"""Content Security Policy nonce generation and management.

This module provides cryptographically secure nonce generation for CSP headers
and request-scoped nonce storage for FastAPI applications.
"""

import base64
import secrets
from typing import Optional

from fastapi import Request


def generate_nonce() -> str:
    """Generate a cryptographically secure nonce for CSP.

    Creates a 32-byte random value encoded as base64 for use in CSP nonce
    directives. Each nonce is cryptographically unique.

    Returns:
        str: Base64-encoded nonce suitable for CSP headers

    Example:
        >>> nonce = generate_nonce()
        >>> len(nonce)  # Base64 encoded 32 bytes
        44
        >>> nonce != generate_nonce()  # Always unique
        True
    """
    random_bytes = secrets.token_bytes(32)
    return base64.b64encode(random_bytes).decode("ascii")


def store_nonce_in_request(request: Request, nonce: str) -> None:
    """Store nonce in FastAPI request state.

    Stores the generated nonce in the request's state object for access
    by other middleware, route handlers, and templates.

    Args:
        request: FastAPI request object
        nonce: The generated nonce string

    Example:
        >>> from fastapi import Request
        >>> request = Request(...)
        >>> nonce = generate_nonce()
        >>> store_nonce_in_request(request, nonce)
        >>> assert hasattr(request.state, 'csp_nonce')
    """
    request.state.csp_nonce = nonce


def get_nonce_from_request(request: Request) -> Optional[str]:
    """Retrieve nonce from FastAPI request state.

    Gets the nonce that was stored in the request state by the nonce
    middleware. Returns None if no nonce has been set.

    Args:
        request: FastAPI request object

    Returns:
        Optional[str]: The nonce string if present, None otherwise

    Example:
        >>> nonce = get_nonce_from_request(request)
        >>> if nonce:
        ...     print(f"CSP nonce: {nonce}")
    """
    return getattr(request.state, "csp_nonce", None)


def is_valid_nonce(nonce: str) -> bool:
    """Validate that a string is a properly formatted nonce.

    Checks that the nonce is a valid base64 string of the expected length
    (44 characters for 32-byte random data).

    Args:
        nonce: String to validate as a nonce

    Returns:
        bool: True if the nonce is properly formatted

    Example:
        >>> valid_nonce = generate_nonce()
        >>> is_valid_nonce(valid_nonce)
        True
        >>> is_valid_nonce("invalid")
        False
    """
    if not isinstance(nonce, str):
        return False

    # Base64 encoded 32 bytes should be 44 characters (with padding)
    if len(nonce) != 44:
        return False

    try:
        # Try to decode - should be valid base64
        decoded = base64.b64decode(nonce)
        # Should decode to exactly 32 bytes
        return len(decoded) == 32
    except Exception:
        return False
