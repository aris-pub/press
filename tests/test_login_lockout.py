"""Failed logins are limited per account, not per IP.

The client IP behind Cloudflare and Fly comes from a header the client can set, so an
IP limit can be bypassed. A limit on the email being guessed cannot.
"""

from httpx import AsyncClient
import pytest_asyncio

from app.models.user import User
from app.routes import auth

CORRECT = "testpassword123"


async def _login(client: AsyncClient, email: str, password: str):
    return await client.post("/login-form", data={"email": email, "password": password})


async def _fail(client: AsyncClient, email: str, times: int):
    for _ in range(times):
        response = await _login(client, email, "wrong-password")
        assert response.status_code == 422


@pytest_asyncio.fixture
async def other_user(test_db):
    from app.auth.utils import get_password_hash

    user = User(
        email="other@example.com",
        password_hash=get_password_hash(CORRECT),
        display_name="Other User",
        email_verified=True,
    )
    test_db.add(user)
    await test_db.commit()
    return user


async def test_correct_password_rejected_after_too_many_failures(client, test_user):
    await _fail(client, test_user.email, auth.LOGIN_FAILURE_LIMIT)

    response = await _login(client, test_user.email, CORRECT)

    assert response.status_code == 422
    assert "session_id" not in response.cookies
    assert "Too many failed sign-in attempts" in response.text


async def test_failures_below_the_limit_do_not_lock(client, test_user):
    await _fail(client, test_user.email, auth.LOGIN_FAILURE_LIMIT - 1)

    response = await _login(client, test_user.email, CORRECT)

    assert response.status_code == 200
    assert "session_id" in response.cookies


async def test_lock_is_per_account(client, test_user, other_user):
    await _fail(client, test_user.email, auth.LOGIN_FAILURE_LIMIT)

    response = await _login(client, other_user.email, CORRECT)

    assert response.status_code == 200
    assert "session_id" in response.cookies


async def test_email_case_and_spaces_count_as_the_same_account(client, test_user):
    variants = [test_user.email.upper(), f"  {test_user.email}  "]
    for i in range(auth.LOGIN_FAILURE_LIMIT):
        await _fail(client, variants[i % 2], 1)

    response = await _login(client, test_user.email, CORRECT)

    assert "Too many failed sign-in attempts" in response.text


async def test_lock_ends_after_the_window(client, test_user, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: now[0])
    await _fail(client, test_user.email, auth.LOGIN_FAILURE_LIMIT)

    now[0] += auth.LOGIN_FAILURE_WINDOW + 1
    response = await _login(client, test_user.email, CORRECT)

    assert response.status_code == 200
    assert "session_id" in response.cookies


async def test_successful_login_clears_earlier_failures(client, test_user):
    await _fail(client, test_user.email, auth.LOGIN_FAILURE_LIMIT - 1)
    assert (await _login(client, test_user.email, CORRECT)).status_code == 200
    client.cookies.clear()

    await _fail(client, test_user.email, auth.LOGIN_FAILURE_LIMIT - 1)
    response = await _login(client, test_user.email, CORRECT)

    assert response.status_code == 200
