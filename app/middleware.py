"""Middleware for request/response logging and monitoring."""

import asyncio
from collections import defaultdict
import time
from typing import Callable

from fastapi import Request, Response
import sentry_sdk
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import get_logger
from app.security.nonce import get_nonce_from_request

# Rate limiting constants
DEFAULT_REQUESTS_PER_MINUTE = 300
DEFAULT_BURST_REQUESTS = 50
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

        # Set Sentry context for request tracking
        sentry_sdk.set_tag("http.method", request.method)
        sentry_sdk.set_tag("http.path", request.url.path)
        sentry_sdk.set_context(
            "request",
            {
                "url": str(request.url),
                "user_agent": request.headers.get("user-agent"),
                "referer": request.headers.get("referer"),
            },
        )

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

            # Set Sentry response context
            sentry_sdk.set_tag("http.status_code", response.status_code)
            sentry_sdk.set_context(
                "response", {"status_code": response.status_code, "process_time": process_time}
            )

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
        # Skip HTTPS redirect for health checks, E2E testing, and local development
        import os

        if os.getenv("E2E_TESTING", "").lower() in ("true", "1", "yes"):
            return await call_next(request)

        # Skip HTTPS redirect in development
        if os.getenv("ENVIRONMENT", "development") != "production":
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
        # Only set X-Frame-Options if not already set (e.g., by /paper endpoint)
        if "X-Frame-Options" not in response.headers:
            response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Add HSTS header only for HTTPS responses
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Add CSP header with context-aware script protection
        # Skip if response already has CSP (e.g., from /paper endpoint)
        if "Content-Security-Policy" in response.headers:
            return response

        # Exclude /paper endpoint - it sets its own CSP with frame-ancestors
        is_scroll_page = (
            request.url.path.startswith("/scroll/")
            and not request.url.path.endswith("/raw")
            and not request.url.path.endswith("/paper")
        )

        if is_scroll_page:
            # Strict CSP with strict-dynamic for scroll pages (user content)
            nonce = get_nonce_from_request(request)
            if nonce:
                csp = (
                    "default-src 'self'; "
                    f"script-src 'self' 'strict-dynamic' 'nonce-{nonce}' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
                    "style-src 'self' 'unsafe-inline' data: https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                    "img-src 'self' data: https:; "
                    "font-src 'self' data: https://fonts.gstatic.com; "
                    "connect-src 'self'; "
                    "frame-src 'self';"
                )
            else:
                # Fallback for scroll pages without nonce (shouldn't happen)
                csp = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
                    "style-src 'self' 'unsafe-inline' data: https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                    "img-src 'self' data: https:; "
                    "font-src 'self' data: https://fonts.gstatic.com; "
                    "connect-src 'self'; "
                    "frame-src 'self';"
                )
        else:
            # Standard CSP for static pages (homepage, auth, etc) - no nonces needed
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://unpkg.com https://challenges.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data:; "
                "font-src 'self' https://fonts.gstatic.com; "
                "connect-src 'self'; "
                "frame-src 'self';"
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

            # Track rate limiting in Sentry
            sentry_sdk.set_tag("rate_limited", True)
            sentry_sdk.set_context(
                "rate_limit",
                {"client_ip": client_ip, "path": request.url.path, "method": request.method},
            )

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


class EmailVerificationMiddleware(BaseHTTPMiddleware):
    """Middleware to block unverified users from protected routes."""

    # Routes that don't require email verification
    ALLOWED_PATHS = {
        "/",
        "/login",
        "/login-form",
        "/register",
        "/register-form",
        "/logout",
        "/verify-email",
        "/resend-verification",
        "/forgot-password",
        "/forgot-password-form",
        "/reset-password",
        "/reset-password-form",
        "/dashboard",
        "/scroll",  # Public scroll viewing
        "/static",
        "/brand",  # Brand assets (logos, etc.)
        "/favicon.ico",
        "/health",
        "/csrf-token",  # CSRF token endpoint
        "/user/export-data",  # GDPR data export
        "/account",  # Account deletion
        "/partials",  # HTMX partials for dynamic content
        "/api",  # Public API endpoints
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check if user is verified before allowing access to protected routes."""
        from fastapi.responses import RedirectResponse

        from app.auth.session import get_current_user_from_session
        from app.database import get_db

        path = request.url.path

        # Allow static files and public routes
        # For "/" we need exact match, for others (like "/static") we use prefix match
        is_allowed = path == "/" or any(
            path.startswith(allowed) and allowed != "/" for allowed in self.ALLOWED_PATHS
        )
        if is_allowed:
            return await call_next(request)

        # For all other routes, check if user is authenticated and verified
        # Get database session - respect test overrides
        import inspect

        from main import app as fastapi_app

        if get_db in fastapi_app.dependency_overrides:
            db_gen = fastapi_app.dependency_overrides[get_db]()
            # Handle both sync and async generators
            if inspect.isasyncgen(db_gen):
                db = await anext(db_gen)
            else:
                db = next(db_gen)
        else:
            db_gen = get_db()
            db = await anext(db_gen)
        try:
            user = await get_current_user_from_session(request, db)

            # If user is logged in but not verified, block access
            if user and not user.email_verified:
                get_logger().info(f"Blocked unverified user {user.id} from {path}")
                # Redirect with message parameter so homepage can show verification notice
                return RedirectResponse(url="/?verification_required=1", status_code=302)

        except Exception as e:
            get_logger().error(f"Error in email verification middleware: {e}", exc_info=True)
        finally:
            try:
                # Handle cleanup for both sync and async generators
                if inspect.isasyncgen(db_gen):
                    await db_gen.aclose()
                else:
                    # Close sync generator
                    try:
                        next(db_gen)
                    except StopIteration:
                        pass
            except (StopAsyncIteration, StopIteration):
                pass

        return await call_next(request)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Middleware to validate CSRF tokens on state-changing requests."""

    # HTTP methods that require CSRF protection
    PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    # Routes exempt from CSRF protection
    # Includes unauthenticated forms (login, register) which use other protections (rate limiting)
    EXEMPT_PATHS = {
        "/health",
        "/login-form",
        "/register-form",
        "/forgot-password-form",
        "/reset-password-form",
        "/logout",  # Low-risk action, session-protected
        "/resend-verification",  # Low-risk action, session-protected
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate CSRF token for protected methods."""

        from app.auth.csrf import validate_csrf_token

        # Skip CSRF check for safe methods
        if request.method not in self.PROTECTED_METHODS:
            return await call_next(request)

        # Skip CSRF check for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Get session ID from cookie
        session_id = request.cookies.get("session_id")

        # Skip CSRF validation for unauthenticated requests (no session)
        # CSRF protection only applies to authenticated users
        if not session_id:
            return await call_next(request)

        # Get CSRF token from form data or headers
        csrf_token = None
        if request.method in {"POST", "PUT", "PATCH"}:
            # For form submissions, we need to read the body to check the CSRF token
            # But we must preserve it for the route handler to re-read
            try:
                # Read the raw body bytes
                body = await request.body()

                # Parse form data to get CSRF token
                content_type_header = request.headers.get("Content-Type", "")

                if "multipart/form-data" in content_type_header:
                    # Extract CSRF token from multipart body using regex
                    # This is a simple extraction that looks for the csrf_token field
                    import re

                    try:
                        # Look for pattern: name="csrf_token"\r\n\r\n<token_value>\r\n
                        body_str = body.decode("utf-8", errors="ignore")
                        csrf_pattern = r'name="csrf_token"[^\r\n]*\r\n\r\n([^\r\n]+)'
                        match = re.search(csrf_pattern, body_str)

                        if match:
                            csrf_token = match.group(1).strip()

                        # Make body readable again
                        request._body = body
                    except Exception as parse_error:
                        get_logger().warning(
                            f"Failed to extract CSRF from multipart: {parse_error}"
                        )
                        # Fallback to header check
                        csrf_token = request.headers.get("X-CSRF-Token")
                elif "application/x-www-form-urlencoded" in content_type_header:
                    # Parse URL-encoded form to extract CSRF token
                    from urllib.parse import parse_qs

                    form_data = parse_qs(body.decode())
                    csrf_token = form_data.get("csrf_token", [None])[0]

                    # Make body readable again by wrapping it in BytesIO
                    request._body = body
                else:
                    # Not a form, check headers
                    csrf_token = request.headers.get("X-CSRF-Token")

            except Exception as e:
                get_logger().warning(f"Error reading form for CSRF validation: {e}")
                # Not a form submission, check headers
                csrf_token = request.headers.get("X-CSRF-Token")
        elif request.method == "DELETE":
            # For DELETE requests, check headers
            csrf_token = request.headers.get("X-CSRF-Token")

        # Validate CSRF token
        is_valid = await validate_csrf_token(session_id, csrf_token)

        if not is_valid:
            get_logger().warning(
                f"CSRF validation failed for {request.method} {request.url.path} "
                f"from {request.client.host}"
            )
            return Response(
                content="CSRF validation failed. Please refresh the page and try again.",
                status_code=403,
                media_type="text/plain",
            )

        # CSRF token is valid, continue with request
        return await call_next(request)


class StaticFilesCacheMiddleware(BaseHTTPMiddleware):
    """Middleware to add caching headers for static files."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add Cache-Control headers to static file responses.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/route handler

        Returns:
            The HTTP response with caching headers added for static files
        """
        response = await call_next(request)

        # Add caching headers for static files
        if request.url.path.startswith("/static"):
            # Cache static files for 1 hour
            response.headers["Cache-Control"] = "public, max-age=3600"
            response.headers["Vary"] = "Accept-Encoding"
        elif request.url.path == "/robots.txt" or request.url.path == "/sitemap.xml":
            # Cache SEO files for 1 day
            response.headers["Cache-Control"] = "public, max-age=86400"

        return response
