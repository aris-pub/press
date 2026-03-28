"""Tests for ORCID OAuth2 authentication flow."""

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.auth.utils import get_password_hash
from app.models.user import User

FAKE_ORCID = "0000-0002-1234-5678"
FAKE_ORCID_2 = "0000-0002-9999-0001"


@pytest.fixture(autouse=True)
def orcid_env(monkeypatch):
    """Set ORCID env vars and reset module-level state for each test."""
    monkeypatch.setenv("ORCID_CLIENT_ID", "APP-TESTCLIENTID")
    monkeypatch.setenv("ORCID_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("ORCID_BASE_URL", "https://sandbox.orcid.org")

    import app.routes.orcid as orcid_mod
    from app import templates_config

    monkeypatch.setattr(orcid_mod, "ORCID_CLIENT_ID", "APP-TESTCLIENTID")
    monkeypatch.setattr(orcid_mod, "ORCID_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(orcid_mod, "ORCID_BASE_URL", "https://sandbox.orcid.org")
    monkeypatch.setattr(templates_config, "ORCID_CLIENT_ID", "APP-TESTCLIENTID")
    templates_config.templates.env.globals["orcid_client_id"] = "APP-TESTCLIENTID"
    orcid_mod._pending_states.clear()
    yield
    orcid_mod._pending_states.clear()
    templates_config.templates.env.globals["orcid_client_id"] = templates_config.ORCID_CLIENT_ID


@pytest_asyncio.fixture
async def orcid_user(test_db):
    """A user who already has an ORCID linked."""
    user = User(
        email="orcid-linked@example.com",
        password_hash=get_password_hash("password123"),
        display_name="ORCID User",
        email_verified=True,
        orcid_id=FAKE_ORCID,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def passwordless_orcid_user(test_db):
    """A user created via ORCID login (no real password)."""
    user = User(
        email="orcid-only@example.com",
        password_hash="!orcid-only",
        display_name="ORCID Only User",
        email_verified=True,
        orcid_id=FAKE_ORCID_2,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


def _mock_orcid_token_response(orcid_id=FAKE_ORCID, name="Jane Doe"):
    """Build a mock httpx response for ORCID token exchange."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "fake-access-token",
        "token_type": "bearer",
        "orcid": orcid_id,
        "name": name,
    }
    return mock_resp


def _mock_orcid_token_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.json.return_value = {"error": "invalid_grant"}
    return mock_resp


@pytest.mark.asyncio
class TestOrcidRedirect:
    """GET /auth/orcid should redirect to ORCID authorize URL."""

    async def test_redirects_to_orcid(self, client):
        resp = await client.get("/auth/orcid", follow_redirects=False)
        assert resp.status_code == 302

        location = resp.headers["location"]
        parsed = urlparse(location)
        assert "orcid.org" in parsed.netloc
        assert parsed.path == "/oauth/authorize"

        params = parse_qs(parsed.query)
        assert params["response_type"] == ["code"]
        assert params["scope"] == ["/authenticate"]
        assert "redirect_uri" in params
        assert "state" in params
        assert "client_id" in params

    async def test_state_param_is_random(self, client):
        """Each redirect should generate a unique state."""
        resp1 = await client.get("/auth/orcid", follow_redirects=False)
        resp2 = await client.get("/auth/orcid", follow_redirects=False)

        state1 = parse_qs(urlparse(resp1.headers["location"]).query)["state"][0]
        state2 = parse_qs(urlparse(resp2.headers["location"]).query)["state"][0]
        assert state1 != state2


@pytest.mark.asyncio
class TestOrcidCallback:
    """GET /auth/orcid/callback tests."""

    async def test_rejects_missing_state(self, client):
        resp = await client.get("/auth/orcid/callback?code=abc", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["location"]

    async def test_rejects_invalid_state(self, client):
        # First, hit /auth/orcid to set a state in session
        await client.get("/auth/orcid", follow_redirects=False)

        resp = await client.get(
            "/auth/orcid/callback?code=abc&state=wrong-state", follow_redirects=False
        )
        assert resp.status_code == 302
        assert "/login" in resp.headers["location"]

    async def test_rejects_missing_code(self, client):
        # Get valid state
        redir = await client.get("/auth/orcid", follow_redirects=False)
        state = parse_qs(urlparse(redir.headers["location"]).query)["state"][0]

        resp = await client.get(
            f"/auth/orcid/callback?state={state}", follow_redirects=False
        )
        assert resp.status_code == 302
        assert "/login" in resp.headers["location"]

    async def test_login_existing_orcid_user(self, client, orcid_user, test_db):
        """Callback with known ORCID logs in existing user."""
        redir = await client.get("/auth/orcid", follow_redirects=False)
        state = parse_qs(urlparse(redir.headers["location"]).query)["state"][0]

        mock_resp = _mock_orcid_token_response(orcid_id=FAKE_ORCID)
        with patch("app.routes.orcid.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.post = AsyncMock(return_value=mock_resp)

            resp = await client.get(
                f"/auth/orcid/callback?code=valid-code&state={state}",
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["location"]
        assert "session_id" in resp.cookies

    async def test_creates_new_user_for_unknown_orcid(self, client, test_db):
        """Callback with unknown ORCID creates a new account."""
        redir = await client.get("/auth/orcid", follow_redirects=False)
        state = parse_qs(urlparse(redir.headers["location"]).query)["state"][0]

        mock_resp = _mock_orcid_token_response(orcid_id="0000-0003-0000-0001", name="New Researcher")
        with patch("app.routes.orcid.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.post = AsyncMock(return_value=mock_resp)

            resp = await client.get(
                f"/auth/orcid/callback?code=valid-code&state={state}",
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["location"]

        # Verify user was created
        result = await test_db.execute(
            select(User).where(User.orcid_id == "0000-0003-0000-0001")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.display_name == "New Researcher"
        assert user.email_verified is True

    async def test_links_orcid_when_logged_in(self, authenticated_client, test_user, test_db):
        """Callback when logged in links ORCID to current account."""
        redir = await authenticated_client.get("/auth/orcid", follow_redirects=False)
        state = parse_qs(urlparse(redir.headers["location"]).query)["state"][0]

        mock_resp = _mock_orcid_token_response(orcid_id="0000-0003-5555-6666", name="Ignored Name")
        with patch("app.routes.orcid.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.post = AsyncMock(return_value=mock_resp)

            resp = await authenticated_client.get(
                f"/auth/orcid/callback?code=valid-code&state={state}",
                follow_redirects=False,
            )

        assert resp.status_code == 302

        # Verify ORCID was linked
        await test_db.refresh(test_user)
        assert test_user.orcid_id == "0000-0003-5555-6666"

    async def test_token_exchange_failure(self, client):
        """Callback handles ORCID token exchange failure."""
        redir = await client.get("/auth/orcid", follow_redirects=False)
        state = parse_qs(urlparse(redir.headers["location"]).query)["state"][0]

        mock_resp = _mock_orcid_token_error()
        with patch("app.routes.orcid.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.post = AsyncMock(return_value=mock_resp)

            resp = await client.get(
                f"/auth/orcid/callback?code=bad-code&state={state}",
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "/login" in resp.headers["location"]

    async def test_duplicate_orcid_link_rejected(self, client, orcid_user, test_db):
        """Cannot link an ORCID that already belongs to another user."""
        # Create and authenticate a second user
        from app.auth.session import create_session

        user2 = User(
            email="user2@example.com",
            password_hash=get_password_hash("password123"),
            display_name="User Two",
            email_verified=True,
        )
        test_db.add(user2)
        await test_db.commit()
        await test_db.refresh(user2)

        session_id = await create_session(test_db, user2.id)
        client.cookies.set("session_id", session_id)

        redir = await client.get("/auth/orcid", follow_redirects=False)
        state = parse_qs(urlparse(redir.headers["location"]).query)["state"][0]

        # Try to link orcid_user's ORCID
        mock_resp = _mock_orcid_token_response(orcid_id=FAKE_ORCID)
        with patch("app.routes.orcid.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.post = AsyncMock(return_value=mock_resp)

            resp = await client.get(
                f"/auth/orcid/callback?code=valid-code&state={state}",
                follow_redirects=False,
            )

        assert resp.status_code == 302
        # Should redirect with an error, not link
        assert "/dashboard" in resp.headers["location"] or "/login" in resp.headers["location"]

        # ORCID should NOT be linked to user2
        await test_db.refresh(user2)
        assert user2.orcid_id is None


@pytest.mark.asyncio
class TestOrcidUnlink:
    """GET /auth/orcid/unlink tests."""

    async def test_unlink_requires_auth(self, client):
        resp = await client.get("/auth/orcid/unlink", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["location"]

    async def test_unlink_removes_orcid(self, authenticated_client, test_user, test_db):
        """Unlink removes orcid_id when user has a password."""
        test_user.orcid_id = FAKE_ORCID
        await test_db.commit()

        resp = await authenticated_client.get("/auth/orcid/unlink", follow_redirects=False)
        assert resp.status_code == 302

        await test_db.refresh(test_user)
        assert test_user.orcid_id is None

    async def test_unlink_blocked_without_password(self, client, passwordless_orcid_user, test_db):
        """Cannot unlink ORCID if user has no password (would be locked out)."""
        from app.auth.session import create_session

        session_id = await create_session(test_db, passwordless_orcid_user.id)
        client.cookies.set("session_id", session_id)

        resp = await client.get("/auth/orcid/unlink", follow_redirects=False)
        assert resp.status_code == 302
        # ORCID should still be linked
        await test_db.refresh(passwordless_orcid_user)
        assert passwordless_orcid_user.orcid_id == FAKE_ORCID_2


@pytest.mark.asyncio
class TestOrcidUI:
    """ORCID buttons appear on login/register pages and dashboard."""

    async def test_login_page_shows_orcid_button(self, client):
        resp = await client.get("/login")
        assert resp.status_code == 200
        body = resp.text
        assert "/auth/orcid" in body
        assert "Sign in with ORCID" in body

    async def test_register_page_shows_orcid_button(self, client):
        resp = await client.get("/register")
        assert resp.status_code == 200
        body = resp.text
        assert "/auth/orcid" in body
        assert "Sign up with ORCID" in body

    async def test_dashboard_shows_link_orcid(self, authenticated_client, test_user):
        """Dashboard shows 'Link ORCID' when user has no ORCID linked."""
        resp = await authenticated_client.get("/dashboard")
        assert resp.status_code == 200
        assert "Link ORCID" in resp.text

    async def test_dashboard_shows_linked_orcid(self, authenticated_client, test_user, test_db):
        """Dashboard shows linked ORCID iD and unlink button."""
        test_user.orcid_id = FAKE_ORCID
        await test_db.commit()

        resp = await authenticated_client.get("/dashboard")
        assert resp.status_code == 200
        assert FAKE_ORCID in resp.text
        assert "Unlink ORCID" in resp.text
