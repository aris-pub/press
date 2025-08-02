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
    
    # Log database URL for debugging
    db_url = os.getenv("DATABASE_URL", "not_set")
    logger.info(f"Using DATABASE_URL: {db_url}")
    
    await create_tables()
    logger.info("Database tables created/verified")
    
    # Verify database connection and check subjects
    try:
        from sqlalchemy import select, text

        from app.database import AsyncSessionLocal
        from app.models.scroll import Subject
        
        async with AsyncSessionLocal() as session:
            # Test basic connection
            await session.execute(text("SELECT 1"))
            logger.info("✓ Database connection verified")
            
            # Count subjects
            result = await session.execute(select(Subject))
            subjects = result.scalars().all()
            subject_count = len(subjects)
            logger.info(f"Found {subject_count} subjects in database")
            
            if subject_count > 0:
                subject_names = [s.name for s in subjects[:5]]  # First 5
                logger.info(f"First subjects: {subject_names}")
            else:
                logger.warning("⚠️  No subjects found in database - upload form may not work")
                
    except Exception as e:
        logger.error(f"❌ Database verification failed: {e}")
        logger.error("Upload functionality may not work properly")
    
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
