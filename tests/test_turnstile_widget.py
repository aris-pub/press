"""Tests for the register-page Turnstile widget defenses.

When Turnstile is configured but the widget fails to produce a token, the form
must not allow submission. Issue #43 (Abhay Gupta) showed a real user hitting
the empty-token failure mode with no recovery path; these tests lock in the
defensive UX: disabled submit until token, no duplicate hidden input, visible
interactive widget, error callbacks wired to surface failures.
"""

import pytest
from httpx import AsyncClient

from app.templates_config import templates


@pytest.fixture(autouse=True)
def reset_turnstile_global():
    """Snapshot and restore the Jinja global between tests so test order does not
    leak state. Jinja env.globals is module-level shared state.
    """
    original = templates.env.globals.get("turnstile_site_key", "")
    yield
    templates.env.globals["turnstile_site_key"] = original


async def _get_register(client: AsyncClient, site_key: str = "0xTESTSITEKEY") -> str:
    templates.env.globals["turnstile_site_key"] = site_key
    resp = await client.get("/register")
    assert resp.status_code == 200
    return resp.text


async def test_submit_button_disabled_when_turnstile_configured(client: AsyncClient):
    """A: submit button must start disabled so users cannot submit before the
    Turnstile callback fires. Without this guard the user submits an empty
    cf-turnstile-response and the server returns 422 with no recovery.
    """
    body = await _get_register(client, site_key="0xTESTSITEKEY")

    # Find the submit button by its loading-text marker.
    button_start = body.find("Create Account")
    assert button_start != -1, "Create Account button not found"
    # Find the opening tag of the button. Search backwards for "<button".
    tag_start = body.rfind("<button", 0, button_start)
    assert tag_start != -1, "<button tag not found before Create Account label"
    tag_end = body.find(">", tag_start)
    button_tag = body[tag_start : tag_end + 1]

    assert "disabled" in button_tag, (
        f"submit button must be disabled by default when Turnstile is configured; got: {button_tag}"
    )


async def test_submit_button_not_disabled_when_turnstile_not_configured(
    client: AsyncClient,
):
    """When Turnstile is not configured, there is no captcha to wait for, so
    the submit button must not be disabled.
    """
    body = await _get_register(client, site_key="")

    # When turnstile is not configured the static container/error divs should
    # be absent — this is a sanity check that our template gating worked.
    assert 'id="turnstile-container"' not in body, (
        "turnstile-container should not render when site key is empty; "
        "if this fails the template did not see the empty site key"
    )

    # Find the submit button by its stable id.
    tag_start = body.find('id="register-submit"')
    assert tag_start != -1, "register-submit button not found"
    tag_open = body.rfind("<button", 0, tag_start)
    tag_close = body.find(">", tag_start)
    button_tag = body[tag_open : tag_close + 1]

    assert "disabled" not in button_tag, (
        f"submit button must NOT be disabled when Turnstile is not configured; got: {button_tag}"
    )


async def test_no_duplicate_static_turnstile_token_input(client: AsyncClient):
    """B: the form must not pre-render its own <input id="turnstile-token">.
    Turnstile injects its own hidden cf-turnstile-response input inside the
    widget container; pre-rendering ours created two inputs with the same
    name and depended on a JS callback to keep them in sync.
    """
    body = await _get_register(client, site_key="0xTESTSITEKEY")
    assert 'id="turnstile-token"' not in body, (
        "static #turnstile-token input must be removed; Turnstile owns its own input"
    )


async def test_render_uses_visible_interactive_mode(client: AsyncClient):
    """C: the explicit render must force a visible interactive widget so the
    user is never stuck in invisible mode that silently fails to validate.
    """
    body = await _get_register(client, site_key="0xTESTSITEKEY")
    assert "appearance: 'always'" in body, (
        "render config must set appearance: 'always' to force visible widget"
    )
    assert "size: 'normal'" in body, (
        "render config must set size: 'normal' to force interactive widget"
    )


async def test_render_wires_error_and_expired_callbacks(client: AsyncClient):
    """A (extension): the widget must wire error/expired/timeout callbacks so
    failures surface to the user and re-disable the submit button.
    """
    body = await _get_register(client, site_key="0xTESTSITEKEY")
    assert "'error-callback'" in body, "error-callback must be wired"
    assert "'expired-callback'" in body, "expired-callback must be wired"
    assert "'timeout-callback'" in body, "timeout-callback must be wired"


async def test_failure_messaging_div_present(client: AsyncClient):
    """A (extension): a visible alert region must exist so error-callback can
    surface the failure (instead of submitting blank and getting a generic 422).
    """
    body = await _get_register(client, site_key="0xTESTSITEKEY")
    assert 'id="turnstile-error"' in body, (
        "page must contain a #turnstile-error element so failures are visible to the user"
    )


async def test_render_guards_against_undefined_turnstile_api(client: AsyncClient):
    """When Brave shields, uBlock, etc. block the Turnstile API script entirely,
    the global `turnstile` is undefined. renderTurnstile must check for this
    and surface a visible error instead of throwing a ReferenceError (which
    happens silently inside the htmx:afterSettle handler and leaves the user
    with a disabled submit button and no explanation).
    """
    body = await _get_register(client, site_key="0xTESTSITEKEY")
    assert "typeof turnstile" in body, (
        "renderTurnstile must check typeof turnstile === 'undefined' before "
        "calling turnstile.render, so a blocked CF API surfaces a real error"
    )


async def test_fallback_timer_for_blocked_script(client: AsyncClient):
    """When the CF API script is blocked at the network level, htmx:afterSettle
    may not fire (e.g. on a non-boosted direct page load), so the typeof check
    alone isn't enough. A fallback timer must fire after a few seconds and
    surface the error if turnstile is still undefined.
    """
    body = await _get_register(client, site_key="0xTESTSITEKEY")
    assert "setTimeout" in body, (
        "page must set a fallback timer so blocked-script users see an error"
    )
