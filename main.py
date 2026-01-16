"""Main FastAPI application entry point.

This module initializes the Scroll Press application, a modern HTML-native preprint
server for academic research documents written in web-native formats.

"""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.exception_handlers import (
    internal_server_error_handler,
    not_found_handler,
    rate_limit_handler,
)
from app.logging_config import get_logger
from app.middleware import (
    CSRFMiddleware,
    EmailVerificationMiddleware,
    HTTPSRedirectMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    StaticFilesCacheMiddleware,
)
from app.routes import auth, main, scrolls
from app.security.nonce_middleware import NonceMiddleware

# Initialize Sentry for error tracking and performance monitoring
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    environment = os.getenv("ENVIRONMENT", "development")

    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
            AsyncioIntegration(),
        ],
        # Performance monitoring - sample rates by environment
        traces_sample_rate=1.0 if environment == "development" else 0.1,  # 10% in production
        profiles_sample_rate=1.0 if environment == "development" else 0.1,  # 10% in production
        # Environment and release tracking
        environment=environment,
        release=os.getenv("GIT_COMMIT", "dev"),
        # Error handling configuration
        attach_stacktrace=True,
        send_default_pii=False,  # GDPR compliance - no user emails/IPs in errors
        max_breadcrumbs=50,
        # Filter out test events
        before_send=lambda event, hint: event if environment != "testing" else None,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Handles startup and shutdown events for the FastAPI application.
    Creates database tables on startup if they don't exist.
    """
    # Startup
    logger = get_logger()
    logger.info("Starting Scroll Press application")

    # Validate Zenodo configuration
    from app.integrations.zenodo import get_zenodo_client

    zenodo_client = get_zenodo_client()
    if zenodo_client is None:
        logger.warning(
            "Zenodo API token not configured or is a placeholder. "
            "DOI minting will be disabled. Set ZENODO_API_TOKEN to enable."
        )
    else:
        logger.info("Zenodo client initialized successfully")
        await zenodo_client.close()

    # Skip database operations during startup to avoid Supabase pgbouncer prepared statement issues
    # But ensure database connectivity in CI/testing environments
    if os.getenv("TESTING") == "1":
        from app.database import Base, engine

        # Import all models to ensure they're registered with Base.metadata
        from app.models.scroll import Scroll, Subject  # noqa: F401
        from app.models.user import User  # noqa: F401

        # Verify database connectivity and tables exist
        try:
            async with engine.begin() as conn:
                # Check if tables exist, create if they don't
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables verified/created successfully")
        except Exception as e:
            logger.error(f"Database setup failed: {e}")

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
app.add_middleware(StaticFilesCacheMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(EmailVerificationMiddleware)
# Nonce middleware must run before SecurityHeadersMiddleware to generate nonces
app.add_middleware(NonceMiddleware)

# Only add HTTPS redirect in production (when DATABASE_URL contains a remote host)
database_url = os.getenv("DATABASE_URL", "")
is_production = "supabase.com" in database_url or "amazonaws.com" in database_url
if is_production:
    # HTTPS redirect should be one of the first to run (added last)
    app.add_middleware(HTTPSRedirectMiddleware)

# Disable rate limiting during tests
is_testing = os.getenv("TESTING", "").lower() in ("true", "1", "yes")
rate_limit_enabled = not is_testing
app.add_middleware(RateLimitMiddleware, enabled=rate_limit_enabled)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount brand assets
brand_paths = [
    "brand",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "brand")
]

brand_dir = None
for path in brand_paths:
    if os.path.exists(path):
        brand_dir = path
        break

if brand_dir:
    app.mount("/brand", StaticFiles(directory=brand_dir), name="brand")

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
