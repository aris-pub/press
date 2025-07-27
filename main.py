"""Main FastAPI application entry point.

This module initializes the Preview Press application, a modern HTML-native preprint
server for academic research documents written in web-native formats.

"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import create_tables
from app.logging_config import get_logger
from app.middleware import LoggingMiddleware, SecurityHeadersMiddleware
from app.routes import auth, main, previews


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Handles startup and shutdown events for the FastAPI application.
    Creates database tables on startup if they don't exist.
    """
    # Startup
    logger = get_logger()
    logger.info("Starting Preview Press application")
    await create_tables()
    logger.info("Database tables created/verified")
    yield
    # Shutdown (if needed)
    logger.info("Shutting down Preview Press application")


app = FastAPI(
    title="Press - Modern Preprint Server",
    description="HTML-native academic document preprint server",
    version="0.1.0",
    lifespan=lifespan,
)

# Add middleware (order matters - last added runs first)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(main.router)
app.include_router(auth.router)
app.include_router(previews.router)
