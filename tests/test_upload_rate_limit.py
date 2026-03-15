"""Tests for per-user upload rate limiting."""

import time
from unittest.mock import patch

import pytest

from app.routes.scrolls import (
    UPLOAD_RATE_LIMIT,
    UPLOAD_RATE_WINDOW,
    _check_upload_rate_limit,
    _record_upload,
    _upload_timestamps,
)


@pytest.fixture(autouse=True)
def reset_upload_rate_limiter():
    """Reset the in-memory upload rate limiter between tests."""
    _upload_timestamps.clear()
    yield
    _upload_timestamps.clear()


class TestUploadRateLimitFunction:
    """Unit tests for the upload rate limit check function."""

    def test_allows_first_upload(self):
        assert _check_upload_rate_limit("user-1") is True

    def test_allows_up_to_limit(self):
        for _ in range(UPLOAD_RATE_LIMIT - 1):
            _record_upload("user-1")
        assert _check_upload_rate_limit("user-1") is True

    def test_blocks_at_limit(self):
        for _ in range(UPLOAD_RATE_LIMIT):
            _record_upload("user-1")
        assert _check_upload_rate_limit("user-1") is False

    def test_different_users_independent(self):
        for _ in range(UPLOAD_RATE_LIMIT):
            _record_upload("user-1")
        assert _check_upload_rate_limit("user-1") is False
        assert _check_upload_rate_limit("user-2") is True

    def test_expired_timestamps_cleared(self):
        base = time.monotonic()
        _upload_timestamps["user-1"] = [base - UPLOAD_RATE_WINDOW - 10] * UPLOAD_RATE_LIMIT
        assert _check_upload_rate_limit("user-1") is True

    def test_rate_limit_is_5_per_hour(self):
        assert UPLOAD_RATE_LIMIT == 5
        assert UPLOAD_RATE_WINDOW == 3600

    def test_bypassed_during_e2e_testing(self):
        for _ in range(UPLOAD_RATE_LIMIT):
            _record_upload("user-1")
        with patch("app.routes.scrolls.IS_E2E_TESTING", True):
            assert _check_upload_rate_limit("user-1") is True


@pytest.mark.asyncio
class TestUploadFormRateLimit:
    """Integration tests for rate limiting on the /upload-form endpoint."""

    async def test_upload_form_blocked_after_limit(
        self, authenticated_client, test_user, test_subject
    ):
        for _ in range(UPLOAD_RATE_LIMIT):
            _record_upload(str(test_user.id))

        response = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Test",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Abstract",
                "license": "cc-by-4.0",
                "confirm_rights": "on",
                "action": "publish",
            },
        )
        assert response.status_code == 429

    async def test_upload_form_allowed_within_limit(
        self, authenticated_client, test_user, test_subject
    ):
        response = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Test",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Abstract",
                "license": "cc-by-4.0",
                "confirm_rights": "on",
                "action": "publish",
            },
        )
        assert response.status_code != 429


@pytest.mark.asyncio
class TestUploadHtmlRateLimit:
    """Integration tests for rate limiting on the /upload/html endpoint."""

    async def test_upload_html_blocked_after_limit(
        self, authenticated_client, test_user, test_subject
    ):
        for _ in range(UPLOAD_RATE_LIMIT):
            _record_upload(str(test_user.id))

        html_content = b"<html><body><h1>Test</h1></body></html>"
        response = await authenticated_client.post(
            "/upload/html",
            data={
                "title": "Test",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Abstract",
                "license": "cc-by-4.0",
                "keywords": "",
                "action": "publish",
            },
            files={"file": ("test.html", html_content, "text/html")},
        )
        assert response.status_code == 429
