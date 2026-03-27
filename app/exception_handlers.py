"""Global exception handlers for the FastAPI application."""

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import get_logger

logger = get_logger()
templates = Jinja2Templates(directory="app/templates")


async def not_found_handler(request: Request, exc: StarletteHTTPException) -> HTMLResponse | JSONResponse:
    """Handle 404 Not Found errors with custom template or JSON for API routes."""
    logger.warning(f"404 error: {request.url} - {exc.detail}")

    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": exc.detail})

    return templates.TemplateResponse(
        request=request, name="404.html", context={"message": exc.detail}, status_code=404
    )


async def rate_limit_handler(request: Request, exc: StarletteHTTPException) -> HTMLResponse:
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


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> HTMLResponse | JSONResponse:
    """Dispatch HTTP exceptions to the appropriate status-specific handler.

    Without this, the generic Exception handler catches HTTPException (since it's
    a subclass of Exception) and returns HTML error pages for all errors -- breaking
    asset serving where browsers expect CSS/JS/SVG content types.
    """
    if exc.status_code == 404:
        return await not_found_handler(request, exc)
    if exc.status_code == 429:
        return await rate_limit_handler(request, exc)
    if exc.status_code >= 500:
        return await internal_server_error_handler(request, exc)
    return HTMLResponse(content=str(exc.detail), status_code=exc.status_code)
