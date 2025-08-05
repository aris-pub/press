"""Main FastAPI application entry point.

This module initializes the Scroll Press application, a modern HTML-native preprint
server for academic research documents written in web-native formats.

"""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.exception_handlers import (
    internal_server_error_handler,
    not_found_handler,
    rate_limit_handler,
)
from app.logging_config import get_logger
from app.middleware import LoggingMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware
from app.routes import auth, main, scrolls
from app.security.nonce_middleware import NonceMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Handles startup and shutdown events for the FastAPI application.
    Creates database tables on startup if they don't exist.
    """
    # Startup
    logger = get_logger()
    logger.info("Starting Scroll Press application")

    # Skip database operations during startup to avoid Supabase pgbouncer prepared statement issues

    yield
    # Shutdown (if needed)
    logger.info("Shutting down Scroll Press application")


app = FastAPI(
    title="Press - Modern Preprint Server",
    description="HTML-native academic document preprint server",
    version="0.1.0",
    lifespan=lifespan,
)

# Add middleware (order matters - last added runs first)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware)
# Nonce middleware must run before SecurityHeadersMiddleware to generate nonces
app.add_middleware(NonceMiddleware)

# Disable rate limiting during tests
is_testing = os.getenv("TESTING", "").lower() in ("true", "1", "yes")
rate_limit_enabled = not is_testing
app.add_middleware(RateLimitMiddleware, enabled=rate_limit_enabled)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Exception handlers
app.add_exception_handler(404, not_found_handler)
app.add_exception_handler(429, rate_limit_handler)
app.add_exception_handler(500, internal_server_error_handler)
app.add_exception_handler(Exception, internal_server_error_handler)


# Health check endpoint for monitoring
@app.get("/health")
def health_check():
    """Fast health check endpoint for load balancers and monitoring."""
    return {"status": "ok", "service": "scroll-press"}


# Include routers
app.include_router(main.router)
app.include_router(auth.router)
app.include_router(scrolls.router)
