"""Tests for the retry logic in scripts/aris_atproto_bot.py."""

import importlib.util
from pathlib import Path

import httpx
import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "aris_atproto_bot.py"
_spec = importlib.util.spec_from_file_location("aris_atproto_bot", _SCRIPT)
bot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bot)

URL = "https://pds.invalid/xrpc/com.atproto.repo.listRecords"


@pytest.fixture
def fake_http(monkeypatch):
    """Replace httpx.request with a queue of canned outcomes; return the call log."""
    monkeypatch.setattr(bot, "RETRY_WAITS", (0, 0, 0))
    outcomes: list = []
    calls: list = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url))
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(outcome, request=httpx.Request(method, url))

    monkeypatch.setattr(bot.httpx, "request", fake_request)
    return outcomes, calls


def test_retries_5xx_then_succeeds(fake_http):
    outcomes, calls = fake_http
    outcomes.extend([500, 503, 200])
    assert bot._request("GET", URL).status_code == 200
    assert len(calls) == 3


def test_retries_transport_error_then_succeeds(fake_http):
    outcomes, calls = fake_http
    outcomes.extend([httpx.ConnectError("reset"), 200])
    assert bot._request("GET", URL).status_code == 200
    assert len(calls) == 2


def test_does_not_retry_4xx(fake_http):
    outcomes, calls = fake_http
    outcomes.extend([401])
    assert bot._request("POST", URL).status_code == 401
    assert len(calls) == 1


def test_returns_last_5xx_after_all_attempts(fake_http):
    outcomes, calls = fake_http
    outcomes.extend([500, 500, 500, 502])
    assert bot._request("GET", URL).status_code == 502
    assert len(calls) == len(bot.RETRY_WAITS) + 1


def test_raises_transport_error_after_all_attempts(fake_http):
    outcomes, calls = fake_http
    outcomes.extend([httpx.ReadTimeout("slow")] * 4)
    with pytest.raises(httpx.ReadTimeout):
        bot._request("GET", URL)
    assert len(calls) == 4


def test_load_existing_survives_one_500(monkeypatch):
    """The failure from run 41473725932: listRecords returned 500 once."""
    monkeypatch.setattr(bot, "RETRY_WAITS", (0, 0, 0))
    responses = [
        httpx.Response(500),
        httpx.Response(200, json={"records": [{"uri": "at://did/c/abc", "value": {"x": 1}}]}),
    ]

    def fake_request(method, url, **kwargs):
        resp = responses.pop(0)
        resp.request = httpx.Request(method, url)
        return resp

    monkeypatch.setattr(bot.httpx, "request", fake_request)
    assert bot.load_existing("jwt", "did:plc:x", "pub.aris.scroll") == {"abc": {"x": 1}}
