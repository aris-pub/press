"""Middleware for request/response logging and monitoring."""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import get_logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically log all HTTP requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/route handler

        Returns:
            The HTTP response
        """
        start_time = time.time()
        logger = get_logger()

        # Skip logging for health check endpoint to reduce noise
        if request.url.path == "/health":
            return await call_next(request)

        # Skip logging for static files
        if request.url.path.startswith("/static"):
            return await call_next(request)

        # Log the incoming request
        logger.info(f"Incoming request: {request.method} {request.url.path}")

        try:
            # Process the request
            response = await call_next(request)

            # Calculate response time
            process_time = time.time() - start_time

            # Log the response
            logger.info(
                f"Response: {request.method} {request.url.path} - "
                f"{response.status_code} - {process_time:.3f}s"
            )

            # Add response time header
            response.headers["X-Process-Time"] = str(process_time)

            return response

        except Exception as e:
            # Calculate response time even for errors
            process_time = time.time() - start_time

            # Log the error
            logger.error(
                f"Error processing request: {request.method} {request.url.path} - "
                f"{str(e)} - {process_time:.3f}s",
                exc_info=True,
            )

            # Re-raise the exception
            raise e


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/route handler

        Returns:
            The HTTP response with security headers
        """
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Add CSP header for basic protection
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data:; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self';"
        )
        response.headers["Content-Security-Policy"] = csp

        return response
