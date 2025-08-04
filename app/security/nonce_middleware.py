"""Content Security Policy nonce middleware for FastAPI.

This middleware generates unique nonces for each request and makes them
available to templates and other components.
"""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.security.nonce import generate_nonce, store_nonce_in_request


class NonceMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and inject CSP nonces into requests.

    This middleware:
    1. Generates a unique cryptographic nonce for each request
    2. Stores the nonce in the request state for access by other components
    3. Makes the nonce available to Jinja2 templates

    The nonce is used to implement Content Security Policy (CSP) script-src
    directives that allow only scripts with matching nonce attributes to execute.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Generate nonce and process request.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/route handler

        Returns:
            The HTTP response from downstream handlers
        """
        # Only generate nonces for scroll pages that need user content
        if self._needs_nonce(request):
            # Generate unique nonce for this request
            nonce = generate_nonce()
            # Store in request state for access by other components
            store_nonce_in_request(request, nonce)

        # Process the request
        response = await call_next(request)

        return response

    def _needs_nonce(self, request: Request) -> bool:
        """Check if this request needs a nonce.

        Only scroll view pages need nonces for user content security.
        Static pages like homepage, auth, etc. don't need nonces.
        """
        path = request.url.path
        # Only scroll view pages need nonces
        return path.startswith("/scroll/")
