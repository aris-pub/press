"""Tests for Sentry alert configuration and abuse pattern detection."""

from unittest.mock import patch

import pytest

from app.sentry_config import (
    RATE_LIMIT_REPORT_INTERVAL_SECONDS,
    before_send,
    report_rapid_uploads,
    report_rate_limit_hit,
    reset_rate_limit_reporting,
)


class TestBeforeSend:
    """Tests for the Sentry before_send filter."""

    def test_filters_testing_events(self):
        event = {"level": "error", "exception": {"values": [{"type": "ValueError"}]}}
        result = before_send(event, {}, environment="testing")
        assert result is None

    def test_passes_production_events(self):
        event = {"level": "error", "exception": {"values": [{"type": "ValueError"}]}}
        result = before_send(event, {}, environment="production")
        assert result == event

    def test_filters_404_errors(self):
        event = {
            "level": "error",
            "exception": {"values": [{"type": "HTTPException", "value": "404 Not Found"}]},
        }
        result = before_send(event, {}, environment="production")
        assert result is None

    def test_passes_500_errors(self):
        event = {
            "level": "error",
            "exception": {
                "values": [{"type": "HTTPException", "value": "500 Internal Server Error"}]
            },
        }
        result = before_send(event, {}, environment="production")
        assert result == event

    def test_passes_non_exception_events(self):
        event = {"level": "info", "message": "Test message"}
        result = before_send(event, {}, environment="production")
        assert result == event

    def test_passes_development_events(self):
        event = {"level": "error", "exception": {"values": [{"type": "RuntimeError"}]}}
        result = before_send(event, {}, environment="development")
        assert result == event

    def test_handles_missing_exception_values(self):
        event = {"level": "error", "exception": {}}
        result = before_send(event, {}, environment="production")
        assert result == event

    def test_handles_empty_exception_values(self):
        event = {"level": "error", "exception": {"values": []}}
        result = before_send(event, {}, environment="production")
        assert result == event


class TestReportRateLimitHit:
    """Tests for rate limit abuse reporting to Sentry.

    Every event here bills against the Sentry error quota, so the suppression is
    the point of these tests, not an optimisation detail.
    """

    @pytest.fixture(autouse=True)
    def _clean_state(self):
        reset_rate_limit_reporting()
        yield
        reset_rate_limit_reporting()

    @patch("app.sentry_config.sentry_sdk")
    def test_reports_the_first_hit_from_an_ip(self, mock_sentry):
        report_rate_limit_hit(client_ip="1.2.3.4", path="/upload-form", method="POST")

        mock_sentry.capture_message.assert_called_once()
        call_args = mock_sentry.capture_message.call_args
        assert "Rate limit hit" in call_args[0][0]
        assert "1.2.3.4" in call_args[0][0]
        assert call_args[1]["level"] == "warning"

    @patch("app.sentry_config.sentry_sdk")
    def test_groups_one_issue_per_ip(self, mock_sentry):
        report_rate_limit_hit(client_ip="1.2.3.4", path="/upload", method="POST")

        assert mock_sentry.capture_message.call_args[1]["fingerprint"] == [
            "rate-limit-abuse",
            "1.2.3.4",
        ]

    @patch("app.sentry_config.sentry_sdk")
    def test_suppresses_repeat_hits_within_the_window(self, mock_sentry):
        for i in range(500):
            report_rate_limit_hit(client_ip="1.2.3.4", path=f"/probe{i}", method="GET", now=1000.0 + i)

        assert mock_sentry.capture_message.call_count == 1

    @patch("app.sentry_config.sentry_sdk")
    def test_each_ip_gets_its_own_window(self, mock_sentry):
        report_rate_limit_hit(client_ip="1.2.3.4", path="/a", method="GET", now=1000.0)
        report_rate_limit_hit(client_ip="5.6.7.8", path="/a", method="GET", now=1000.0)
        report_rate_limit_hit(client_ip="1.2.3.4", path="/b", method="GET", now=1001.0)

        assert mock_sentry.capture_message.call_count == 2

    @patch("app.sentry_config.sentry_sdk")
    def test_reports_again_once_the_window_closes(self, mock_sentry):
        report_rate_limit_hit(client_ip="1.2.3.4", path="/a", method="GET", now=1000.0)
        report_rate_limit_hit(
            client_ip="1.2.3.4",
            path="/b",
            method="GET",
            now=1000.0 + RATE_LIMIT_REPORT_INTERVAL_SECONDS,
        )

        assert mock_sentry.capture_message.call_count == 2

    @patch("app.sentry_config.sentry_sdk")
    def test_the_next_event_carries_what_was_suppressed(self, mock_sentry):
        report_rate_limit_hit(client_ip="1.2.3.4", path="/.env", method="GET", now=1000.0)
        for i in range(99):
            report_rate_limit_hit(
                client_ip="1.2.3.4", path=f"/probe{i % 7}", method="GET", now=1001.0 + i
            )
        report_rate_limit_hit(
            client_ip="1.2.3.4",
            path="/stripe.yaml",
            method="GET",
            now=1000.0 + RATE_LIMIT_REPORT_INTERVAL_SECONDS,
        )

        context = mock_sentry.set_context.call_args[0][1]
        assert context["blocked_since_last_report"] == 100
        assert context["distinct_paths_since_last_report"] == 8
        assert context["latest_path"] == "/stripe.yaml"


class TestReportRapidUploads:
    """Tests for rapid upload abuse reporting to Sentry."""

    @patch("app.sentry_config.sentry_sdk")
    def test_reports_rapid_uploads(self, mock_sentry):
        report_rapid_uploads(user_id="user-123", upload_count=5, window_seconds=3600)

        mock_sentry.capture_message.assert_called_once()
        call_args = mock_sentry.capture_message.call_args
        assert "Rapid upload" in call_args[0][0]
        assert call_args[1]["level"] == "warning"

    @patch("app.sentry_config.sentry_sdk")
    def test_includes_user_context(self, mock_sentry):
        report_rapid_uploads(user_id="user-456", upload_count=10, window_seconds=3600)

        mock_sentry.set_user.assert_called_once_with({"id": "user-456"})


class TestStorageThresholdReport:
    """Tests for storage consumption threshold reporting."""

    @patch("app.sentry_config.sentry_sdk")
    def test_reports_storage_threshold(self, mock_sentry):
        from app.sentry_config import report_storage_threshold

        report_storage_threshold(user_id="user-789", total_bytes=524288000, scroll_count=50)

        mock_sentry.capture_message.assert_called_once()
        call_args = mock_sentry.capture_message.call_args
        assert "Storage threshold" in call_args[0][0]
        assert call_args[1]["level"] == "warning"
