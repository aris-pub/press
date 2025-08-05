"""Global exception handlers for the FastAPI application."""

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.logging_config import get_logger

logger = get_logger()
templates = Jinja2Templates(directory="app/templates")


async def not_found_handler(request: Request, exc: HTTPException) -> HTMLResponse:
    """Handle 404 Not Found errors with custom template."""
    logger.warning(f"404 error: {request.url} - {exc.detail}")

    return templates.TemplateResponse(
        request=request, name="404.html", context={"message": exc.detail}, status_code=404
    )


async def rate_limit_handler(request: Request, exc: HTTPException) -> HTMLResponse:
    """Handle 429 Too Many Requests errors with custom template."""
    logger.warning(
        f"Rate limit exceeded: {request.client.host if request.client else 'unknown'} - {request.url}"
    )

    return templates.TemplateResponse(
        request=request, name="429.html", context={}, status_code=429
    )


async def internal_server_error_handler(request: Request, exc: Exception) -> HTMLResponse:
    """Handle 500 Internal Server Error with custom template."""
    logger.error(f"Internal server error: {request.url} - {str(exc)}", exc_info=True)

    return templates.TemplateResponse(
        request=request, name="500.html", context={}, status_code=500
    )
