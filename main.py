from fastapi import FastAPI, Request, Form, HTTPException, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import ValidationError
import secrets
import time
from app.database import create_tables, get_db
from app.auth.utils import get_password_hash, verify_password
from app.models.user import User

# Simple in-memory session store
sessions = {}

def create_session(user_id: int) -> str:
    """Create a new session and return session ID."""
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "user_id": user_id,
        "created_at": time.time()
    }
    return session_id

def get_user_from_session(session_id: str) -> int | None:
    """Get user ID from session, return None if expired/invalid."""
    if not session_id or session_id not in sessions:
        return None
    
    session_data = sessions[session_id]
    # Sessions expire after 24 hours
    if time.time() - session_data["created_at"] > 86400:
        del sessions[session_id]
        return None
    
    return session_data["user_id"]

def delete_session(session_id: str):
    """Delete a session."""
    if session_id in sessions:
        del sessions[session_id]

async def get_current_user_from_session(request: Request, db: AsyncSession) -> User | None:
    """Get current user from session cookie."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    
    user_id = get_user_from_session(session_id)
    if not user_id:
        return None
    
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    except Exception:
        return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await create_tables()
    yield
    # Shutdown (if needed)

app = FastAPI(
    title="Press - Modern Preprint Server",
    description="HTML-native academic document preprint server",
    version="0.1.0",
    lifespan=lifespan
)

# JWT API routes removed - using session-based auth for web forms

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user_from_session(request, db)
    return templates.TemplateResponse(request, "index.html", {"current_user": current_user})

# Auth form pages
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user_from_session(request, db)
    
    # Redirect logged-in users to homepage
    if current_user:
        return RedirectResponse(url="/", status_code=302)
        
    return templates.TemplateResponse(request, "auth/register.html", {"current_user": current_user})

@app.get("/login", response_class=HTMLResponse)  
async def login_page(request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user_from_session(request, db)
    
    # Redirect logged-in users to homepage
    if current_user:
        return RedirectResponse(url="/", status_code=302)
        
    return templates.TemplateResponse(request, "auth/login.html", {"current_user": current_user})

# Form submission handlers
@app.post("/register-form", response_class=HTMLResponse)
async def register_form(
    request: Request,
    email: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Handle registration form submission with HTMX."""
    try:
        # Validate input
        if not email or not email.strip():
            raise ValueError("Email is required")
        if not display_name or not display_name.strip():
            raise ValueError("Display name is required")
        if not password or len(password) < 1:
            raise ValueError("Password is required")
        
        # Check if user already exists (case insensitive)
        normalized_email = email.strip().lower()
        result = await db.execute(select(User).where(User.email == normalized_email))
        if result.scalar_one_or_none():
            return templates.TemplateResponse(
                request, 
                "auth/partials/register_form.html", 
                {
                    "errors": ["Email already registered"],
                    "form_data": {"email": email, "display_name": display_name}
                },
                status_code=422
            )
        
        # Create new user
        hashed_password = get_password_hash(password)
        db_user = User(
            email=normalized_email,
            password_hash=hashed_password,
            display_name=display_name.strip()
        )
        
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        
        # Create session and auto-login user
        session_id = create_session(db_user.id)
        
        # Return success partial with automatic login
        response = templates.TemplateResponse(
            request, 
            "auth/partials/success.html", 
            {
                "title": "Account Created!",
                "message": f"Welcome to Press, {db_user.display_name}!",
                "action_text": "Go to Dashboard",
                "action_url": "/"
            }
        )
        
        # Set session cookie
        response.set_cookie("session_id", session_id, httponly=True, secure=False, samesite="lax")
        
        return response
        
    except Exception as e:
        error_message = str(e) if str(e) else "Registration failed. Please try again."
        return templates.TemplateResponse(
            request, 
            "auth/partials/register_form.html", 
            {
                "errors": [error_message],
                "form_data": {"email": email, "display_name": display_name}
            },
            status_code=422
        )

@app.post("/login-form", response_class=HTMLResponse)
async def login_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Handle login form submission with HTMX."""
    try:
        # Validate input
        if not email or not email.strip():
            raise ValueError("Email is required")
        if not password:
            raise ValueError("Password is required")
        
        # Get user from database (case insensitive)
        normalized_email = email.strip().lower()
        result = await db.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(password, user.password_hash):
            return templates.TemplateResponse(
                request, 
                "auth/partials/login_form.html", 
                {
                    "errors": ["Incorrect email or password"],
                    "form_data": {"email": email}
                },
                status_code=422
            )
        
        # Create session
        session_id = create_session(user.id)
        
        # Return success partial
        response = templates.TemplateResponse(
            request, 
            "auth/partials/success.html", 
            {
                "title": "Welcome Back!",
                "message": f"Successfully signed in as {user.display_name}",
                "action_text": "Go to Dashboard", 
                "action_url": "/"
            }
        )
        
        # Set session cookie
        response.set_cookie("session_id", session_id, httponly=True, secure=False, samesite="lax")
        
        return response
        
    except Exception as e:
        error_message = str(e) if str(e) else "Login failed. Please try again."
        return templates.TemplateResponse(
            request, 
            "auth/partials/login_form.html", 
            {
                "errors": [error_message],
                "form_data": {"email": email}
            },
            status_code=422
        )

# Logout handlers
@app.post("/logout")
@app.get("/logout")
async def logout(request: Request):
    """Handle logout - works for both GET and POST requests."""
    # Get current session ID
    session_id = request.cookies.get("session_id")
    
    # Delete session from store if it exists
    if session_id:
        delete_session(session_id)
    
    # Create redirect response to homepage
    response = RedirectResponse(url="/", status_code=302)
    
    # Clear the session cookie
    response.delete_cookie("session_id")
    
    return response