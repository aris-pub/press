"""Main FastAPI application entry point.

This module initializes the Scroll Press application, a modern HTML-native preprint
server for academic research documents written in web-native formats.

"""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import create_tables
from app.logging_config import get_logger
from app.middleware import LoggingMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware
from app.routes import auth, main, scrolls


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Handles startup and shutdown events for the FastAPI application.
    Creates database tables on startup if they don't exist.
    """
    # Startup
    logger = get_logger()
    logger.info("Starting Scroll Press application")
    await create_tables()
    logger.info("Database tables created/verified")
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

# Disable rate limiting during tests
is_testing = os.getenv("TESTING", "").lower() in ("true", "1", "yes")
rate_limit_enabled = not is_testing
app.add_middleware(RateLimitMiddleware, enabled=rate_limit_enabled)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(main.router)
app.include_router(auth.router)
app.include_router(scrolls.router)
