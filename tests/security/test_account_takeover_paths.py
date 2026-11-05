"""Paths a script running with a reader's session could use to take over or destroy an account.

Author papers are served from Press's own origin, so until they are sandboxed a script in a
paper runs with the logged-in reader's session. It can read any Press page and fetch a CSRF
token from /csrf-token. These tests pin down that such a script cannot:

- read the reader's session ID (which is the login cookie),
- delete the reader's account without access to their email inbox,
- unlink their ORCID from another site with a plain link,
- log them out without a CSRF token,

and that the legitimate flows still work.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.auth.csrf import get_csrf_token
from app.auth.session import create_session
from app.auth.tokens import (
    create_account_deletion_token,
    create_password_reset_token,
    create_verification_token,
    hash_token,
)
from app.models.scroll import Scroll
from app.models.session import Session
from app.models.token import Token
from app.models.user import User
from main import app
from tests.conftest import create_content_addressable_scroll

pytestmark = pytest.mark.asyncio

FAKE_ORCID = "0000-0002-1234-5678"


class FakeEmailService:
    """Records deletion emails instead of sending them."""

    def __init__(self, succeed=True):
        self.succeed = succeed
        self.sent = []

    async def send_account_deletion_email(self, to_email, name, token):
        self.sent.append({"to": to_email, "name": name, "token": token})
        return self.succeed


@pytest.fixture
def email_service(monkeypatch):
    service = FakeEmailService()
    monkeypatch.setattr("app.routes.auth.get_email_service", lambda: service)
    return service


@pytest_asyncio.fixture
async def raw_client(client):
    """A client that never adds CSRF tokens, like a script that did not fetch one.

    Depends on `client` so the test database override is in place.
    """
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as ac:
        yield ac


async def _login(http_client, db, user):
    session_id = await create_session(db, user.id)
    http_client.cookies.set("session_id", session_id)
    return session_id


async def _user_exists(db, user_id):
    result = await db.execute(
        select(User).where(User.id == user_id).execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none() is not None


async def _deletion_tokens(db, user_id):
    result = await db.execute(
        select(Token)
        .where(Token.user_id == user_id, Token.token_type == "account_deletion")
        .execution_options(populate_existing=True)
    )
    return result.scalars().all()


@pytest_asyncio.fixture
async def orcid_only_user(test_db):
    user = User(
        email="orcid-only@example.com",
        password_hash="!orcid-only",
        display_name="ORCID Only User",
        email_verified=True,
        orcid_id="0000-0003-0000-0001",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(test_db):
    from app.auth.utils import get_password_hash

    user = User(
        email="other@example.com",
        password_hash=get_password_hash("otherpassword123"),
        display_name="Other User",
        email_verified=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


# Session IDs in the data export


class TestExportDoesNotLeakSessions:
    async def test_export_contains_no_session_id_key(self, raw_client, test_db, test_user):
        await _login(raw_client, test_db, test_user)
        response = await raw_client.get("/user/export-data")
        assert response.status_code == 200

        def keys(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    yield k
                    yield from keys(v)
            elif isinstance(obj, list):
                for item in obj:
                    yield from keys(item)

        assert "session_id" not in set(keys(response.json()))

    async def test_no_session_value_appears_anywhere_in_export(
        self, raw_client, test_db, test_user
    ):
        """Every live session of the user, not only the current one, stays out of the export."""
        other_sessions = [await create_session(test_db, test_user.id) for _ in range(3)]
        current = await _login(raw_client, test_db, test_user)

        response = await raw_client.get("/user/export-data")
        assert response.status_code == 200
        for session_id in [current, *other_sessions]:
            assert session_id not in response.text

    async def test_export_still_lists_session_dates(self, raw_client, test_db, test_user):
        await create_session(test_db, test_user.id)
        await _login(raw_client, test_db, test_user)

        sessions = (await raw_client.get("/user/export-data")).json()["sessions"]
        assert len(sessions) == 2
        for entry in sessions:
            assert set(entry) == {"created_at", "expires_at"}

    async def test_export_does_not_leak_password_hash_or_tokens(
        self, raw_client, test_db, test_user
    ):
        reset_token = await create_password_reset_token(test_db, test_user.id)
        await _login(raw_client, test_db, test_user)

        text = (await raw_client.get("/user/export-data")).text
        assert test_user.password_hash not in text
        assert reset_token not in text
        assert hash_token(reset_token) not in text


# ORCID unlink


class TestOrcidUnlink:
    async def test_get_does_not_unlink(self, raw_client, test_db, test_user):
        test_user.orcid_id = FAKE_ORCID
        await test_db.commit()
        await _login(raw_client, test_db, test_user)

        response = await raw_client.get("/auth/orcid/unlink", follow_redirects=False)
        assert response.status_code == 405
        await test_db.refresh(test_user)
        assert test_user.orcid_id == FAKE_ORCID

    async def test_post_without_csrf_is_rejected(self, raw_client, test_db, test_user):
        test_user.orcid_id = FAKE_ORCID
        await test_db.commit()
        await _login(raw_client, test_db, test_user)

        response = await raw_client.post("/auth/orcid/unlink", follow_redirects=False)
        assert response.status_code == 403
        await test_db.refresh(test_user)
        assert test_user.orcid_id == FAKE_ORCID

    async def test_post_with_wrong_csrf_is_rejected(self, raw_client, test_db, test_user):
        test_user.orcid_id = FAKE_ORCID
        await test_db.commit()
        await _login(raw_client, test_db, test_user)

        response = await raw_client.post(
            "/auth/orcid/unlink", data={"csrf_token": "0" * 64}, follow_redirects=False
        )
        assert response.status_code == 403
        await test_db.refresh(test_user)
        assert test_user.orcid_id == FAKE_ORCID

    async def test_csrf_token_of_another_session_is_rejected(self, raw_client, test_db, test_user):
        test_user.orcid_id = FAKE_ORCID
        await test_db.commit()
        other_session = await create_session(test_db, test_user.id)
        await _login(raw_client, test_db, test_user)

        response = await raw_client.post(
            "/auth/orcid/unlink",
            data={"csrf_token": await get_csrf_token(other_session)},
            follow_redirects=False,
        )
        assert response.status_code == 403
        await test_db.refresh(test_user)
        assert test_user.orcid_id == FAKE_ORCID

    async def test_post_with_csrf_unlinks(self, raw_client, test_db, test_user):
        test_user.orcid_id = FAKE_ORCID
        await test_db.commit()
        session_id = await _login(raw_client, test_db, test_user)

        response = await raw_client.post(
            "/auth/orcid/unlink",
            data={"csrf_token": await get_csrf_token(session_id)},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "orcid=unlinked" in response.headers["location"]
        await test_db.refresh(test_user)
        assert test_user.orcid_id is None

    async def test_passwordless_user_still_cannot_unlink(
        self, raw_client, test_db, orcid_only_user
    ):
        session_id = await _login(raw_client, test_db, orcid_only_user)

        response = await raw_client.post(
            "/auth/orcid/unlink",
            data={"csrf_token": await get_csrf_token(session_id)},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "orcid_no_password" in response.headers["location"]
        await test_db.refresh(orcid_only_user)
        assert orcid_only_user.orcid_id == "0000-0003-0000-0001"

    async def test_dashboard_uses_a_post_form_with_token(self, raw_client, test_db, test_user):
        test_user.orcid_id = FAKE_ORCID
        await test_db.commit()
        session_id = await _login(raw_client, test_db, test_user)

        html = (await raw_client.get("/dashboard")).text
        assert 'href="/auth/orcid/unlink"' not in html
        assert 'action="/auth/orcid/unlink"' in html
        start = html.rindex("<form", 0, html.index('action="/auth/orcid/unlink"'))
        form = html[start : html.index("</form>", start)]
        assert 'method="POST"' in form
        assert f'name="csrf_token" value="{await get_csrf_token(session_id)}"' in form


# Account deletion


class TestOldDeleteRouteIsGone:
    async def test_delete_account_with_valid_csrf_does_nothing(
        self, raw_client, test_db, test_user
    ):
        """The attack the audit found: fetch /csrf-token, then DELETE /account."""
        await _login(raw_client, test_db, test_user)
        token = (await raw_client.get("/csrf-token")).json()["csrf_token"]

        response = await raw_client.delete("/account", headers={"X-CSRF-Token": token})
        assert response.status_code in (404, 405)
        assert await _user_exists(test_db, test_user.id)


class TestDeletionRequest:
    async def test_requires_login(self, raw_client, email_service):
        response = await raw_client.post("/account/delete-request")
        assert response.status_code == 401
        assert email_service.sent == []

    async def test_requires_csrf(self, raw_client, test_db, test_user, email_service):
        await _login(raw_client, test_db, test_user)
        response = await raw_client.post("/account/delete-request")
        assert response.status_code == 403
        assert email_service.sent == []
        assert await _deletion_tokens(test_db, test_user.id) == []

    async def test_sends_link_and_deletes_nothing(
        self, raw_client, test_db, test_user, email_service
    ):
        session_id = await _login(raw_client, test_db, test_user)
        response = await raw_client.post(
            "/account/delete-request", headers={"X-CSRF-Token": await get_csrf_token(session_id)}
        )
        assert response.status_code == 200
        assert response.json() == {"success": True, "email": test_user.email}

        assert len(email_service.sent) == 1
        assert email_service.sent[0]["to"] == test_user.email
        assert await _user_exists(test_db, test_user.id)
        result = await test_db.execute(select(Session).where(Session.session_id == session_id))
        assert result.scalar_one_or_none() is not None

    async def test_token_is_stored_hashed_and_expires_in_an_hour(
        self, raw_client, test_db, test_user, email_service
    ):
        session_id = await _login(raw_client, test_db, test_user)
        await raw_client.post(
            "/account/delete-request", headers={"X-CSRF-Token": await get_csrf_token(session_id)}
        )
        plain = email_service.sent[0]["token"]
        tokens = await _deletion_tokens(test_db, test_user.id)
        assert len(tokens) == 1
        assert tokens[0].token == hash_token(plain)
        assert tokens[0].token != plain
        expires = tokens[0].expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        assert timedelta(minutes=55) < expires - datetime.now(UTC) <= timedelta(hours=1)

    async def test_response_does_not_contain_the_token(
        self, raw_client, test_db, test_user, email_service
    ):
        """A script that triggers the request must not learn the link."""
        session_id = await _login(raw_client, test_db, test_user)
        response = await raw_client.post(
            "/account/delete-request", headers={"X-CSRF-Token": await get_csrf_token(session_id)}
        )
        assert email_service.sent[0]["token"] not in response.text

    async def test_new_request_invalidates_old_link(
        self, raw_client, test_db, test_user, email_service
    ):
        session_id = await _login(raw_client, test_db, test_user)
        headers = {"X-CSRF-Token": await get_csrf_token(session_id)}
        await raw_client.post("/account/delete-request", headers=headers)
        await raw_client.post("/account/delete-request", headers=headers)
        first, second = email_service.sent[0]["token"], email_service.sent[1]["token"]

        response = await raw_client.post("/account/delete-confirm", data={"token": first})
        assert response.status_code == 400
        assert await _user_exists(test_db, test_user.id)

        response = await raw_client.post(
            "/account/delete-confirm", data={"token": second}, follow_redirects=False
        )
        assert response.status_code == 303
        assert not await _user_exists(test_db, test_user.id)

    async def test_no_email_service_means_no_token(
        self, raw_client, test_db, test_user, monkeypatch
    ):
        monkeypatch.setattr("app.routes.auth.get_email_service", lambda: None)
        session_id = await _login(raw_client, test_db, test_user)
        response = await raw_client.post(
            "/account/delete-request", headers={"X-CSRF-Token": await get_csrf_token(session_id)}
        )
        assert response.status_code == 503
        assert await _deletion_tokens(test_db, test_user.id) == []
        assert await _user_exists(test_db, test_user.id)

    async def test_failed_send_is_reported(self, raw_client, test_db, test_user, monkeypatch):
        failing = FakeEmailService(succeed=False)
        monkeypatch.setattr("app.routes.auth.get_email_service", lambda: failing)
        session_id = await _login(raw_client, test_db, test_user)
        response = await raw_client.post(
            "/account/delete-request", headers={"X-CSRF-Token": await get_csrf_token(session_id)}
        )
        assert response.status_code == 502
        assert await _user_exists(test_db, test_user.id)


class TestDeletionConfirmPage:
    async def test_opening_the_link_deletes_nothing(self, raw_client, test_db, test_user):
        """Mail scanners and link previews open links. Only the POST may delete."""
        plain = await create_account_deletion_token(test_db, test_user.id)
        response = await raw_client.get(f"/account/delete-confirm?token={plain}")
        assert response.status_code == 200
        assert test_user.email in response.text
        assert 'action="/account/delete-confirm"' in response.text
        assert await _user_exists(test_db, test_user.id)
        assert len(await _deletion_tokens(test_db, test_user.id)) == 1

    @pytest.mark.parametrize("token", ["", "not-a-token", "x" * 43])
    async def test_bad_link_shows_error_and_no_form(self, raw_client, token):
        response = await raw_client.get(f"/account/delete-confirm?token={token}")
        assert response.status_code == 200
        assert "invalid or expired" in response.text
        assert 'action="/account/delete-confirm"' not in response.text


class TestDeletionConfirm:
    async def test_valid_token_deletes_account_and_keeps_scrolls(
        self, raw_client, test_db, test_user, test_subject
    ):
        scroll = await create_content_addressable_scroll(test_db, test_user, test_subject)
        session_id = await create_session(test_db, test_user.id)
        await create_password_reset_token(test_db, test_user.id)
        plain = await create_account_deletion_token(test_db, test_user.id)
        user_id, scroll_id = test_user.id, scroll.id

        response = await raw_client.post(
            "/account/delete-confirm", data={"token": plain}, follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/?message=account_deleted"

        assert not await _user_exists(test_db, user_id)
        result = await test_db.execute(select(Session).where(Session.session_id == session_id))
        assert result.scalar_one_or_none() is None
        result = await test_db.execute(select(Token).where(Token.user_id == user_id))
        assert result.scalars().all() == []
        result = await test_db.execute(
            select(Scroll).where(Scroll.id == scroll_id).execution_options(populate_existing=True)
        )
        kept = result.scalar_one()
        assert kept.user_id is None
        assert kept.status == "published"

    async def test_works_without_being_logged_in(self, raw_client, test_db, test_user):
        plain = await create_account_deletion_token(test_db, test_user.id)
        assert "session_id" not in raw_client.cookies
        response = await raw_client.post(
            "/account/delete-confirm", data={"token": plain}, follow_redirects=False
        )
        assert response.status_code == 303
        assert not await _user_exists(test_db, test_user.id)

    async def test_works_while_logged_in_without_csrf(self, raw_client, test_db, test_user):
        """The link may be opened in the browser that holds the session."""
        await _login(raw_client, test_db, test_user)
        plain = await create_account_deletion_token(test_db, test_user.id)
        response = await raw_client.post(
            "/account/delete-confirm", data={"token": plain}, follow_redirects=False
        )
        assert response.status_code == 303
        assert not await _user_exists(test_db, test_user.id)
        assert 'session_id=""' in response.headers.get("set-cookie", "")

    async def test_token_works_once(self, raw_client, test_db, test_user, other_user):
        plain = await create_account_deletion_token(test_db, test_user.id)
        first = await raw_client.post(
            "/account/delete-confirm", data={"token": plain}, follow_redirects=False
        )
        assert first.status_code == 303
        second = await raw_client.post("/account/delete-confirm", data={"token": plain})
        assert second.status_code == 400
        assert await _user_exists(test_db, other_user.id)

    async def test_expired_token_is_rejected(self, raw_client, test_db, test_user):
        plain = await create_account_deletion_token(test_db, test_user.id)
        token = (await _deletion_tokens(test_db, test_user.id))[0]
        token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await test_db.commit()

        response = await raw_client.post("/account/delete-confirm", data={"token": plain})
        assert response.status_code == 400
        assert await _user_exists(test_db, test_user.id)

    async def test_used_token_is_rejected(self, raw_client, test_db, test_user):
        plain = await create_account_deletion_token(test_db, test_user.id)
        token = (await _deletion_tokens(test_db, test_user.id))[0]
        token.used_at = datetime.now(UTC)
        await test_db.commit()

        response = await raw_client.post("/account/delete-confirm", data={"token": plain})
        assert response.status_code == 400
        assert await _user_exists(test_db, test_user.id)

    @pytest.mark.parametrize("maker", [create_password_reset_token, create_verification_token])
    async def test_other_token_types_cannot_delete(self, raw_client, test_db, test_user, maker):
        plain = await maker(test_db, test_user.id)
        response = await raw_client.post("/account/delete-confirm", data={"token": plain})
        assert response.status_code == 400
        assert await _user_exists(test_db, test_user.id)

    @pytest.mark.parametrize("data", [{}, {"token": ""}, {"token": "garbage"}])
    async def test_missing_or_garbage_token_is_rejected(
        self, raw_client, test_db, test_user, data
    ):
        response = await raw_client.post("/account/delete-confirm", data=data)
        assert response.status_code == 400
        assert await _user_exists(test_db, test_user.id)

    async def test_token_deletes_only_its_own_account(
        self, raw_client, test_db, test_user, other_user
    ):
        plain = await create_account_deletion_token(test_db, test_user.id)
        other_session = await create_session(test_db, other_user.id)

        await raw_client.post("/account/delete-confirm", data={"token": plain})
        assert not await _user_exists(test_db, test_user.id)
        assert await _user_exists(test_db, other_user.id)
        result = await test_db.execute(select(Session).where(Session.session_id == other_session))
        assert result.scalar_one_or_none() is not None

    async def test_passwordless_orcid_account_can_be_deleted(
        self, raw_client, test_db, orcid_only_user, email_service
    ):
        session_id = await _login(raw_client, test_db, orcid_only_user)
        response = await raw_client.post(
            "/account/delete-request", headers={"X-CSRF-Token": await get_csrf_token(session_id)}
        )
        assert response.status_code == 200
        plain = email_service.sent[0]["token"]
        response = await raw_client.post(
            "/account/delete-confirm", data={"token": plain}, follow_redirects=False
        )
        assert response.status_code == 303
        assert not await _user_exists(test_db, orcid_only_user.id)


class TestDeletionEmail:
    async def test_link_points_at_confirm_page(self):
        from app.emails.templates import get_account_deletion_email

        html, text = get_account_deletion_email("Ada", "tok123", "https://scroll.press")
        link = "https://scroll.press/account/delete-confirm?token=tok123"
        assert link in html
        assert link in text

    async def test_display_name_is_escaped_in_html(self):
        from app.emails.templates import get_account_deletion_email

        html, _ = get_account_deletion_email(
            '<img src=x onerror="alert(1)">', "tok", "https://scroll.press"
        )
        assert "<img src=x" not in html
        assert "&lt;img src=x" in html

    async def test_copy_has_no_dashes_or_semicolons(self):
        from app.emails.templates import get_account_deletion_email

        html, text = get_account_deletion_email("Ada", "tok", "https://scroll.press")
        for char in ("—", "–"):
            assert char not in html and char not in text
        assert ";" not in text


# Logout


class TestLogoutNeedsCsrf:
    async def test_logout_without_csrf_is_rejected_and_session_survives(
        self, raw_client, test_db, test_user
    ):
        session_id = await _login(raw_client, test_db, test_user)
        response = await raw_client.post("/logout", follow_redirects=False)
        assert response.status_code == 403
        result = await test_db.execute(select(Session).where(Session.session_id == session_id))
        assert result.scalar_one_or_none() is not None

    async def test_logout_with_csrf_works(self, raw_client, test_db, test_user):
        session_id = await _login(raw_client, test_db, test_user)
        response = await raw_client.post(
            "/logout",
            data={"csrf_token": await get_csrf_token(session_id)},
            follow_redirects=False,
        )
        assert response.status_code == 302
        result = await test_db.execute(select(Session).where(Session.session_id == session_id))
        assert result.scalar_one_or_none() is None

    async def test_logout_without_a_session_still_redirects(self, raw_client):
        response = await raw_client.post("/logout", follow_redirects=False)
        assert response.status_code == 302

    async def test_pages_never_contain_the_readers_csrf_token(
        self, raw_client, test_db, test_user
    ):
        """Pages may be cached and shared between readers, so the navbar must not carry it."""
        session_id = await _login(raw_client, test_db, test_user)
        token = await get_csrf_token(session_id)
        for path in ["/", "/about", "/how-it-works", "/docs/quick-start"]:
            response = await raw_client.get(path)
            assert response.status_code == 200, path
            assert 'action="/logout"' in response.text, path
            assert token not in response.text, path

    async def test_logout_script_is_on_every_page_with_the_button(
        self, raw_client, test_db, test_user
    ):
        await _login(raw_client, test_db, test_user)
        html = (await raw_client.get("/")).text
        assert "getAttribute('action') !== '/logout'" in html
        assert "fetch('/csrf-token'" in html
