"""Main FastAPI application entry point.

This module initializes the Preview Press application, a modern HTML-native preprint
server for academic research documents written in web-native formats.

"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import create_tables
from app.routes import auth, main, previews


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Handles startup and shutdown events for the FastAPI application.
    Creates database tables on startup if they don't exist.
    """
    # Startup
    await create_tables()
    yield
    # Shutdown (if needed)


app = FastAPI(
    title="Press - Modern Preprint Server",
    description="HTML-native academic document preprint server",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(main.router)
app.include_router(auth.router)
app.include_router(previews.router)
