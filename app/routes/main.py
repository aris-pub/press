"""Main application routes (landing page, etc.)."""

import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_current_user_from_session
from app.database import get_db
from app.logging_config import get_logger, log_error, log_request
from app.models.preview import Preview, Subject

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the application landing page.

    Shows the main homepage of Preview Press with different content and navigation
    options based on user authentication status. Anonymous users see registration
    prompts while authenticated users see upload options.

    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if current_user:
        log_request(request, user_id=str(current_user.id))

    # Get subjects with preview counts
    subjects_result = await db.execute(
        select(Subject.name, func.count(Subject.id).label("preview_count"))
        .outerjoin(Subject.previews)
        .group_by(Subject.id, Subject.name)
        .order_by(Subject.name)
    )
    subjects = subjects_result.all()

    # Get recent published previews with subjects
    previews_result = await db.execute(
        select(Preview, Subject.name.label("subject_name"))
        .join(Subject)
        .where(Preview.status == "published")
        .order_by(Preview.created_at.desc())
        .limit(4)
    )
    previews = previews_result.all()

    return templates.TemplateResponse(
        request,
        "index.html",
        {"current_user": current_user, "subjects": subjects, "previews": previews},
    )


@router.get("/health")
async def health_check(request: Request, db: AsyncSession = Depends(get_db)):
    """Health check endpoint for monitoring and load balancers.

    Performs basic application health checks including:
    - Database connectivity
    - Basic application functionality

    Returns:
        dict: Health status with timestamp and component checks
    """
    log_request(request)
    start_time = time.time()

    try:
        # Test database connectivity
        await db.execute(text("SELECT 1"))

        # Test basic model queries
        result = await db.execute(select(func.count(Subject.id)))
        subject_count = result.scalar()

        result = await db.execute(select(func.count(Preview.id)))
        preview_count = result.scalar()

        response_time = round((time.time() - start_time) * 1000, 2)

        get_logger().info(f"Health check passed - response_time: {response_time}ms")

        return {
            "status": "healthy",
            "timestamp": time.time(),
            "response_time_ms": response_time,
            "components": {"database": "healthy", "models": "healthy"},
            "metrics": {"subject_count": subject_count, "preview_count": preview_count},
            "version": "0.1.0",
        }

    except Exception as e:
        response_time = round((time.time() - start_time) * 1000, 2)
        log_error(e, request, context="health_check")

        return {
            "status": "unhealthy",
            "timestamp": time.time(),
            "response_time_ms": response_time,
            "components": {"database": "unhealthy", "models": "unknown"},
            "error": str(e),
            "version": "0.1.0",
        }


@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the About page.

    Shows information about Preview Press, its mission, and features.
    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if current_user:
        log_request(request, user_id=str(current_user.id))

    return templates.TemplateResponse(request, "about.html", {"current_user": current_user})


@router.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the Contact page.

    Shows contact information and ways to get in touch with the Preview Press team.
    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if current_user:
        log_request(request, user_id=str(current_user.id))

    return templates.TemplateResponse(request, "contact.html", {"current_user": current_user})
