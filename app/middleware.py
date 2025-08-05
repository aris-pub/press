"""Middleware for request/response logging and monitoring."""

import asyncio
from collections import defaultdict
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import get_logger
from app.security.nonce import get_nonce_from_request

# Rate limiting constants
DEFAULT_REQUESTS_PER_MINUTE = 60
DEFAULT_BURST_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60
BURST_WINDOW_SECONDS = 10
CLEANUP_INTERVAL_SECONDS = 300
RATE_LIMIT_STATUS_CODE = 429
RATE_LIMIT_RETRY_AFTER_SECONDS = 60


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


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to redirect HTTP requests to HTTPS."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Redirect HTTP to HTTPS.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/route handler

        Returns:
            Redirect response to HTTPS or normal response
        """
        # Skip HTTPS redirect for health checks and E2E testing
        import os

        if os.getenv("E2E_TESTING", "").lower() in ("true", "1", "yes"):
            return await call_next(request)
            
        # Skip HTTPS redirect for internal health checks
        if request.url.path == "/health":
            return await call_next(request)

        # Check if request is HTTP (not HTTPS)
        if (
            request.url.scheme == "http"
            and not request.headers.get("x-forwarded-proto") == "https"
        ):
            # Build HTTPS URL
            https_url = request.url.replace(scheme="https")
            # Add basic security headers to redirect response
            headers = {
                "location": str(https_url),
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
            }
            return Response(status_code=301, headers=headers)

        # If this is an HTTPS request (via proxy), let it continue to SecurityHeadersMiddleware
        # which will add HSTS header

        return await call_next(request)


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

        # Add HSTS header only for HTTPS responses
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Add CSP header with context-aware script protection
        is_scroll_page = request.url.path.startswith("/scroll/") and not request.url.path.endswith(
            "/raw"
        )

        if is_scroll_page:
            # Strict CSP with strict-dynamic for scroll pages (user content)
            nonce = get_nonce_from_request(request)
            if nonce:
                csp = (
                    "default-src 'self'; "
                    f"script-src 'self' 'strict-dynamic' 'nonce-{nonce}' 'unsafe-inline'; "
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                    "img-src 'self' data:; "
                    "font-src 'self' https://fonts.gstatic.com; "
                    "connect-src 'self';"
                )
            else:
                # Fallback for scroll pages without nonce (shouldn't happen)
                csp = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline'; "
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                    "img-src 'self' data:; "
                    "font-src 'self' https://fonts.gstatic.com; "
                    "connect-src 'self';"
                )
        else:
            # Standard CSP for static pages (homepage, auth, etc) - no nonces needed
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


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to implement in-memory rate limiting."""

    def __init__(
        self,
        app,
        requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
        burst_requests: int = DEFAULT_BURST_REQUESTS,
        enabled: bool = True,
    ):
        """Initialize rate limiter.

        Args:
            app: FastAPI application
            requests_per_minute: Sustained requests per minute per IP
            burst_requests: Burst requests allowed in 10 seconds
            enabled: Whether rate limiting is enabled (disabled for testing)
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_requests = burst_requests
        self.enabled = enabled

        # In-memory storage: {ip: [timestamps]}
        self.request_counts: defaultdict = defaultdict(list)
        self.cleanup_task = None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limits and process request.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/route handler

        Returns:
            The HTTP response or 429 rate limit exceeded
        """
        # Skip rate limiting if disabled or for health checks and static files
        if (
            not self.enabled
            or request.url.path == "/health"
            or request.url.path.startswith("/static")
        ):
            return await call_next(request)

        # Get client IP (handles proxy headers)
        client_ip = self._get_client_ip(request)
        current_time = time.time()

        # Start cleanup task if not running
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_old_requests())

        # Check rate limits
        if self._is_rate_limited(client_ip, current_time):
            logger = get_logger()
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")

            # Add rate limit headers
            response = Response(
                content="Rate limit exceeded. Please try again later.",
                status_code=RATE_LIMIT_STATUS_CODE,
                media_type="text/plain",
            )
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["Retry-After"] = str(RATE_LIMIT_RETRY_AFTER_SECONDS)

            return response

        # Record this request
        self.request_counts[client_ip].append(current_time)

        # Process request
        response = await call_next(request)

        # Add rate limit headers to successful responses
        remaining = self._get_remaining_requests(client_ip, current_time)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address, handling proxy headers."""
        # Check proxy headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fall back to direct connection IP
        return request.client.host

    def _is_rate_limited(self, client_ip: str, current_time: float) -> bool:
        """Check if client is rate limited."""
        timestamps = self.request_counts[client_ip]

        # Remove old timestamps (older than 1 minute)
        minute_ago = current_time - RATE_LIMIT_WINDOW_SECONDS
        timestamps[:] = [ts for ts in timestamps if ts > minute_ago]

        # Check sustained rate (requests per minute)
        if len(timestamps) >= self.requests_per_minute:
            return True

        # Check burst rate (requests in last 10 seconds)
        ten_seconds_ago = current_time - BURST_WINDOW_SECONDS
        recent_requests = [ts for ts in timestamps if ts > ten_seconds_ago]
        if len(recent_requests) >= self.burst_requests:
            return True

        return False

    def _get_remaining_requests(self, client_ip: str, current_time: float) -> int:
        """Get remaining requests for client in current minute."""
        timestamps = self.request_counts[client_ip]
        minute_ago = current_time - RATE_LIMIT_WINDOW_SECONDS
        recent_count = len([ts for ts in timestamps if ts > minute_ago])
        return max(0, self.requests_per_minute - recent_count)

    async def _cleanup_old_requests(self):
        """Periodically clean up old request timestamps to prevent memory leaks."""
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                current_time = time.time()
                minute_ago = current_time - RATE_LIMIT_WINDOW_SECONDS

                # Clean up old timestamps and empty IP entries
                for client_ip in list(self.request_counts.keys()):
                    timestamps = self.request_counts[client_ip]
                    timestamps[:] = [ts for ts in timestamps if ts > minute_ago]

                    # Remove empty entries to prevent memory leaks
                    if not timestamps:
                        del self.request_counts[client_ip]

                logger = get_logger()
                logger.debug(f"Rate limit cleanup: tracking {len(self.request_counts)} IPs")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger = get_logger()
                logger.error(f"Rate limit cleanup error: {e}")
