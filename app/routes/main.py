"""Main application routes (landing page, etc.)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_current_user_from_session
from app.database import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the application landing page.

    Shows the main homepage of Preview Press with different content and navigation
    options based on user authentication status. Anonymous users see registration
    prompts while authenticated users see upload options.

    """
    current_user = await get_current_user_from_session(request, db)
    return templates.TemplateResponse(request, "index.html", {"current_user": current_user})
