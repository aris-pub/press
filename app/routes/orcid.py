"""ORCID OAuth2 authentication routes."""

import os
import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import create_session, get_current_user_from_session
from app.database import get_db
from app.logging_config import get_logger
from app.models.user import User

router = APIRouter(prefix="/auth/orcid")

IS_PRODUCTION = os.getenv("ENVIRONMENT") == "production"

ORCID_CLIENT_ID = os.getenv("ORCID_CLIENT_ID", "")
ORCID_CLIENT_SECRET = os.getenv("ORCID_CLIENT_SECRET", "")
ORCID_BASE_URL = os.getenv("ORCID_BASE_URL", "https://sandbox.orcid.org")

# Pending OAuth states: state_token -> True
# Short-lived, cleared on use. In production, use Redis/DB before horizontal scaling.
_pending_states: dict[str, bool] = {}


def _get_redirect_uri(request: Request) -> str:
    """Build the ORCID callback URI from the current request."""
    return str(request.url_for("orcid_callback"))


@router.get("", name="orcid_redirect")
async def orcid_redirect(request: Request):
    """Redirect to ORCID authorize URL with CSRF state."""
    state = secrets.token_urlsafe(32)
    _pending_states[state] = True

    redirect_uri = _get_redirect_uri(request)
    authorize_url = (
        f"{ORCID_BASE_URL}/oauth/authorize"
        f"?client_id={ORCID_CLIENT_ID}"
        f"&response_type=code"
        f"&scope=/authenticate"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )

    response = RedirectResponse(url=authorize_url, status_code=302)
    response.set_cookie(
        "orcid_state", state, httponly=True, secure=IS_PRODUCTION,
        samesite="lax", max_age=600,
    )
    return response


@router.get("/callback", name="orcid_callback")
async def orcid_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Handle ORCID OAuth2 callback."""
    logger = get_logger()

    # Validate state
    cookie_state = request.cookies.get("orcid_state")
    if not state or not cookie_state or state != cookie_state or state not in _pending_states:
        logger.warning("ORCID callback: invalid or missing state")
        return RedirectResponse(url="/login?error=orcid_state", status_code=302)

    _pending_states.pop(state, None)

    if not code:
        logger.warning("ORCID callback: missing code")
        return RedirectResponse(url="/login?error=orcid_missing_code", status_code=302)

    # Exchange code for token
    redirect_uri = _get_redirect_uri(request)
    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                f"{ORCID_BASE_URL}/oauth/token",
                data={
                    "client_id": ORCID_CLIENT_ID,
                    "client_secret": ORCID_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )

        if token_resp.status_code != 200:
            logger.error(f"ORCID token exchange failed: {token_resp.status_code}")
            return RedirectResponse(url="/login?error=orcid_token", status_code=302)

        token_data = token_resp.json()
    except Exception as e:
        logger.error(f"ORCID token exchange error: {e}")
        return RedirectResponse(url="/login?error=orcid_token", status_code=302)

    orcid_id = token_data.get("orcid")
    orcid_name = token_data.get("name", "")

    if not orcid_id:
        logger.error("ORCID token response missing orcid field")
        return RedirectResponse(url="/login?error=orcid_token", status_code=302)

    current_user = await get_current_user_from_session(request, db)

    if current_user:
        return await _link_orcid(db, current_user, orcid_id)

    return await _login_or_register(db, orcid_id, orcid_name)


async def _link_orcid(db: AsyncSession, user: User, orcid_id: str) -> RedirectResponse:
    """Link ORCID to an existing logged-in user."""
    logger = get_logger()

    # Check if ORCID is already taken by another user
    result = await db.execute(select(User).where(User.orcid_id == orcid_id))
    existing = result.scalar_one_or_none()
    if existing and existing.id != user.id:
        logger.warning(f"ORCID {orcid_id} already linked to user {existing.id}")
        return RedirectResponse(url="/dashboard?error=orcid_taken", status_code=302)

    user.orcid_id = orcid_id
    await db.commit()
    logger.info(f"Linked ORCID {orcid_id} to user {user.id}")
    return RedirectResponse(url="/dashboard?orcid=linked", status_code=302)


async def _login_or_register(
    db: AsyncSession, orcid_id: str, orcid_name: str,
) -> RedirectResponse:
    """Log in existing ORCID user or create a new account."""
    logger = get_logger()

    result = await db.execute(select(User).where(User.orcid_id == orcid_id))
    user = result.scalar_one_or_none()

    if user:
        session_id = await create_session(db, user.id)
        logger.info(f"ORCID login for user {user.id}")
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            "session_id", session_id, httponly=True,
            secure=IS_PRODUCTION, samesite="lax",
        )
        return response

    # Create new user
    # Generate a placeholder email using ORCID (users can update it later)
    placeholder_email = f"{orcid_id}@orcid.placeholder"
    display_name = orcid_name.strip() if orcid_name else f"ORCID User {orcid_id[-4:]}"

    new_user = User(
        email=placeholder_email,
        password_hash="!orcid-only",
        display_name=display_name,
        email_verified=True,
        orcid_id=orcid_id,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    session_id = await create_session(db, new_user.id)
    logger.info(f"Created new user {new_user.id} via ORCID {orcid_id}")

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        "session_id", session_id, httponly=True,
        secure=IS_PRODUCTION, samesite="lax",
    )
    return response


@router.get("/unlink", name="orcid_unlink")
async def orcid_unlink(request: Request, db: AsyncSession = Depends(get_db)):
    """Remove ORCID from the current user's account."""
    current_user = await get_current_user_from_session(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    logger = get_logger()

    # Block unlink if user has no password (would lock them out)
    if not current_user.password_hash or current_user.password_hash == "!orcid-only":
        logger.warning(f"User {current_user.id} tried to unlink ORCID without password")
        return RedirectResponse(url="/dashboard?error=orcid_no_password", status_code=302)

    current_user.orcid_id = None
    await db.commit()
    logger.info(f"Unlinked ORCID from user {current_user.id}")
    return RedirectResponse(url="/dashboard?orcid=unlinked", status_code=302)
